import faiss
import pickle
import difflib
from rapidfuzz import fuzz
from langchain_community.embeddings import OCIGenAIEmbeddings
import numpy as np

# === CONFIGURAÇÕES ===
FAISS_INDEX_PATH = "faiss_index.bin"
ID_MAP_PATH = "produto_id_map.pkl"
TOP_K = 5
DISTANCIA_MINIMA = 1.0

# === EMBEDDING COM OCI GEN AI ===
embedding = OCIGenAIEmbeddings(
    model_id="cohere.embed-english-light-v3.0",
    service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
    compartment_id="ocid1.compartment.oc1..aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    auth_profile="DEFAULT"
)

# === CARREGA O ÍNDICE VETORIAL ===
print("📦 Carregando índice vetorial...")
index = faiss.read_index(FAISS_INDEX_PATH)
with open(ID_MAP_PATH, "rb") as f:
    id_map = pickle.load(f)

# === CORREÇÃO AUTOMÁTICA DO INPUT ===
def corrigir_input_mais_proximo(input_usuario, descricoes_existentes):
    sugestoes = difflib.get_close_matches(input_usuario, descricoes_existentes, n=1, cutoff=0.6)
    return sugestoes[0] if sugestoes else input_usuario

descricao_input = input("Digite a descrição do produto a buscar: ").strip()
descricoes = [p["descricao"] for p in id_map]
descricao_corrigida = corrigir_input_mais_proximo(descricao_input, descricoes)

if descricao_corrigida != descricao_input:
    print(f"🧠 Consulta sugerida: {descricao_corrigida}")
else:
    print(f"✅ Consulta original mantida: {descricao_input}")

# === GERA EMBEDDING COM OCI ===
consulta_emb = embedding.embed_query(descricao_corrigida)
consulta_emb = np.array([consulta_emb])  # FAISS espera um array 2D

# === BUSCA NO FAISS ===
distances, indices = index.search(consulta_emb, TOP_K)
bons_resultados = [d for d in distances[0] if d < DISTANCIA_MINIMA]

# === EXIBE RESULTADOS VETORIAIS ===
if bons_resultados:
    print("\n🔍 Resultados semânticos similares:")
    for i, dist in zip(indices[0], distances[0]):
        if dist >= DISTANCIA_MINIMA:
            continue
        match = id_map[i]
        similaridade = 1 / (1 + dist)
        print(f"ID: {match['id']} | Código: {match['codigo']} | Produto: {match['descricao']}")
        print(f"↳ Similaridade: {similaridade:.2%} | Distância: {dist:.4f}\n")
else:
    # === FALLBACK FUZZY ===
    print("\n⚠️ Nenhum resultado vetorial relevante. Buscando por similaridade textual (fuzzy)...\n")
    melhores_fuzz = []
    for produto in id_map:
        score = fuzz.token_sort_ratio(descricao_corrigida, produto["descricao"])
        melhores_fuzz.append((produto, score))

    melhores_fuzz.sort(key=lambda x: x[1], reverse=True)

    for produto, score in melhores_fuzz[:TOP_K]:
        print(f"ID: {produto['id']} | Código: {produto['codigo']} | Produto: {produto['descricao']}")
        print(f"↳ Similaridade (fuzzy): {score:.2f}%\n")