from sentence_transformers import SentenceTransformer
import faiss
import pickle

# === CARREGAR MODELO E ÍNDICE ===
model = SentenceTransformer('all-MiniLM-L6-v2')
index = faiss.read_index("faiss_index.bin")

with open("produto_id_map.pkl", "rb") as f:
    id_map = pickle.load(f)

# === CONSULTA DO USUÁRIO ===
descricao_input = "harry potter especial"
consulta_emb = model.encode([descricao_input], convert_to_numpy=True)

# === BUSCAR PRODUTOS MAIS SIMILARES ===
k = 5
distances, indices = index.search(consulta_emb, k)

# === EXIBIR RESULTADOS ===
print("\n🔍 Resultados similares:")
for i, dist in zip(indices[0], distances[0]):
    match = id_map[i]
    print(f"ID: {match['id']} | Código: {match['codigo']} | Produto: {match['descricao']} | Distância: {dist:.2f}")