# -*- coding: utf-8 -*-
import os
import oracledb
from mcp.server.fastmcp import FastMCP
from product_search import BuscaProdutoSimilar

buscador = BuscaProdutoSimilar()

mcp = FastMCP("InvoiceItemResolver")
# Configurações Oracle Wallet
WALLET_PATH = "/WALLET_PATH/Wallet_oradb23ai"  # Altere conforme seu ambiente
DB_ALIAS = "oradb23ai_high"                 # Alias definido no tnsnames.ora
USERNAME = "USER"                        # Usuário do banco
PASSWORD = "Password"                    # Senha do usuário
os.environ["TNS_ADMIN"] = WALLET_PATH


def executar_busca(query: str, params: dict = {}):
    try:
        connection = oracledb.connect(
            user=USERNAME,
            password=PASSWORD,
            dsn=DB_ALIAS,
            config_dir=WALLET_PATH,
            wallet_location=WALLET_PATH,
            wallet_password=PASSWORD
        )
        cursor = connection.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        connection.close()
        return results
    except Exception as e:
        print(f"[ERRO] Consulta falhou: {e}")
        return []

def executar_busca_ean(termos_busca):
    results = []

    try:
        connection = oracledb.connect(user=USERNAME, password=PASSWORD, dsn=DB_ALIAS, config_dir=WALLET_PATH, wallet_location=WALLET_PATH, wallet_password=PASSWORD)
        cursor = connection.cursor()

        query = """
                SELECT * FROM TABLE(fn_busca_avancada(:1))
                ORDER BY similaridade DESC \
                """
        cursor.execute(query, [termos_busca])

        for row in cursor:
            results.append({
                "codigo": row[0],
                "descricao": row[1],
                "similaridade": row[2]
            })

        cursor.close()
        connection.close()
    except Exception as e:
        return {"erro": str(e)}, 500

    return results
# --------------------- FERRAMENTAS MCP ---------------------
@mcp.tool()
def buscar_produto_vetorizado(descricao: str) -> dict:
    """Busca produto por descrição usando embeddings"""
    return buscador.buscar_produtos_similares(descricao)

@mcp.tool()
def resolve_ean(description: str) -> dict:
    """
    Resolve o código EAN do produto a partir da descrição
    """

    result = executar_busca_ean(description)

    if isinstance(result, list) and result:
        return {
            "ean": result[0]["codigo"],
            "descricao": result[0]["descricao"],
            "similaridade": result[0]["similaridade"]
        }
    else:
        return {"erro": "EAN não encontrado com os critérios fornecidos."}

@mcp.tool()
def buscar_notas_por_criterios(cliente: str = None, estado: str = None, preco: float = None, ean: str = None, margem: float = 0.05) -> list:
    """
    Busca notas fiscais de saída com base em cliente, estado, EAN e preço aproximado.
    Permite que um ou mais campos sejam omitidos.
    Enquanto não houver um EAN estabelecido, nao adianta usar este servico.
    """
    print("buscar_notas_por_criterios")

    query = """
            SELECT nf.numero_nf, nf.nome_cliente, nf.estado, nf.data_saida,
                   inf.numero_item, inf.codigo_ean, inf.descricao_produto, inf.valor_unitario
            FROM nota_fiscal nf
                     JOIN item_nota_fiscal inf ON nf.numero_nf = inf.numero_nf
            WHERE 1=1 
            """

    params = {}

    if cliente:
        query += " AND LOWER(nf.nome_cliente) LIKE LOWER(:cliente)"
        params["cliente"] = f"%{cliente}%"
    # if estado:
    query += " AND LOWER(nf.estado) = LOWER(:estado)"
    params["estado"] = estado
    if ean:
        query += " AND inf.codigo_ean = :ean"
        params["ean"] = ean
    if preco is not None:
        query += " AND inf.valor_unitario BETWEEN :preco_min AND :preco_max"
        params["preco_min"] = preco * (1 - margem)
        params["preco_max"] = preco * (1 + margem)

    # Executa a consulta com os parâmetros nomeados
    result = executar_busca(query, params)

    return [
        dict(zip(
            ["numero_nota", "nome_cliente", "estado", "data_saida", "numero_item", "codigo_ean", "descricao_produto", "valor_unitario"],
            row
        ))
        for row in result
    ]


# --------------------- EXECUÇÃO MCP ---------------------

if __name__ == "__main__":
    # Inicia o servidor MCP
    mcp.run(transport="stdio")