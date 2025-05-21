import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models.oci_generative_ai import ChatOCIGenAI
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

from langgraph.graph import StateGraph
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import Runnable
from langchain_core.messages import HumanMessage, AIMessage

import phoenix as px
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
# Multiple Servers
from langchain_mcp_adapters.client import MultiServerMCPClient

# 1. Inicia o Phoenix (ele abre o servidor OTLP na porta 6006)
px.launch_app()

# 2. Configura o OpenTelemetry
resource = Resource(attributes={"service.name": "ollama_oraclegenai_trace"})
provider = TracerProvider(resource=resource)
trace.set_tracer_provider(provider)

# 3. Configura o exportador para mandar spans para o Phoenix
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces")
span_processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(span_processor)

# 4. Cria o tracer
tracer = trace.get_tracer(__name__)

class MemoryState:
    def __init__(self):
        self.messages = []

# Define the language model
llm = ChatOCIGenAI(
    model_id="cohere.command-r-08-2024",
    service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
    compartment_id="ocid1.compartment.oc1..aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    auth_profile="DEFAULT",
    model_kwargs={"temperature": 0.1, "top_p": 0.75, "max_tokens": 2000}
)

# Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", """Você é um agente responsável por resolver inconsistências em notas fiscais de devolução de clientes.
    Seu objetivo é encontrar a nota fiscal de **saída original da empresa**, 
    com base nas informações da **nota de devolução do cliente**.
    
    ### Importante:
    1. Use o servidor `InvoiceItemResolver` para todas as consultas.
    2. Primeiro, utilize a ferramenta de **busca vetorial ou fuzzy** para encontrar o **EAN mais provável**, 
    a partir da descrição fornecida pelo cliente. O atributo codigo vindo do resultado da lista de busca vetorial 
    pode ser entendida como EAN.
       - Ferramentas: `buscar_produto_vetorizado` ou `resolve_ean`
       - Retorne o EAN mais provável com sua descrição e grau de similaridade.
       Use resolve_ean para obter o EAN mais provável. Se retornar um dicionário com erro, interrompa a operação.
    3. Só após encontrar um EAN válido, use a ferramenta `buscar_notas_por_criterios` para procurar a nota fiscal de saída
     original.
       - Use o EAN junto com cliente, preço e local (estado) para fazer a busca.
    
    ### Exemplo de entrada:
    ```json
    {{
      "customer": "Cliente 43",
      "description": "Harry Poter",
      "price": 139.55,
      "location": "RJ"
    }}
    Se encontrar uma nota fiscal de saída correspondente, retorne:
        •	número da nota,
        •	cliente,
        •	estado,
        •	EAN,
        •	descrição do produto,
        •	preço unitário.
    
    Se não encontrar nenhuma correspondência, responda exatamente:
    “EAN não encontrado com os critérios fornecidos.”
    """),
    ("placeholder", "{messages}")
])

# Run the client with the MCP server
async def main():
    async with MultiServerMCPClient(
            {
                "InvoiceItemResolver": {
                    "command": "python",
                    "args": ["server_nf_items.py"],
                    "transport": "stdio",
                },
            }
    ) as client:
        tools = client.get_tools()
        if not tools:
            print("❌ No MCP tools were loaded. Please check if the server is running.")
            return

        print("🛠️ Loaded tools:", [t.name for t in tools])

        # Creating the LangGraph agent with in-memory state
        memory_state = MemoryState()

        agent_executor = create_react_agent(
            model=llm,
            tools=tools,
            prompt=prompt,
        )

        print("🤖 READY")
        while True:
            query = input("You: ")
            if query.lower() in ["quit", "exit"]:
                break
            if not query.strip():
                continue

            memory_state.messages.append(HumanMessage(content=query))
            try:
                result = await agent_executor.ainvoke({"messages": memory_state.messages})
                new_messages = result.get("messages", [])

                # Store new messages
                # memory_state.messages.extend(new_messages)
                memory_state.messages = []

                print("Assist:", new_messages[-1].content)

                formatted_messages = prompt.format_messages()

                # Convertendo cada mensagem em string
                formatted_messages_str = "\n".join([str(msg) for msg in formatted_messages])
                with tracer.start_as_current_span("Server NF Items") as span:
                    # Anexa o prompt e resposta como atributos no trace
                    span.set_attribute("llm.prompt", formatted_messages_str)
                    span.set_attribute("llm.response", new_messages[-1].content)
                    span.set_attribute("llm.model", "ocigenai")

                    executed_tools = []
                    if "intermediate_steps" in result:
                        for step in result["intermediate_steps"]:
                            tool_call = step.get("tool_input") or step.get("action")
                            if tool_call:
                                tool_name = tool_call.get("tool") or step.get("tool")
                                if tool_name:
                                    executed_tools.append(tool_name)

                    if not executed_tools:
                        executed_tools = [t.name for t in tools]  # fallback

                    span.set_attribute("llm.executed_tools", ", ".join(executed_tools))

            except Exception as e:
                print("Error:", e)

# Run the agent with asyncio
if __name__ == "__main__":
    asyncio.run(main())