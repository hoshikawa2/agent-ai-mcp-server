import oracledb
import os
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import pickle

# === CONFIGURAÇÃO ORACLE COM WALLET ===
WALLET_PATH = "/WALLET_PATH/Wallet_oradb23ai"
DB_ALIAS = "oradb23ai_high"
USERNAME = "USER"
PASSWORD = "Password"

os.environ["TNS_ADMIN"] = WALLET_PATH

# === CONECTANDO USANDO oracledb (modo thin) ===
connection = oracledb.connect(user=USERNAME, password=PASSWORD, dsn=DB_ALIAS, config_dir=WALLET_PATH, wallet_location=WALLET_PATH, wallet_password=PASSWORD)

cursor = connection.cursor()

# === CONSULTA A TABELA DE PRODUTOS ===
cursor.execute("SELECT id, codigo, descricao FROM produtos")
rows = cursor.fetchall()

ids = []
descricoes = []

for row in rows:
    ids.append({"id": row[0], "codigo": row[1], "descricao": row[2]})
    descricoes.append(row[2])  # Usado no embedding

# === GERAÇÃO DE EMBEDDINGS COM SENTENCE TRANSFORMERS ===
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(descricoes, convert_to_numpy=True)

# === CRIAÇÃO DO ÍNDICE FAISS ===
dim = embeddings.shape[1]
index = faiss.IndexFlatL2(dim)
index.add(embeddings)

# === SALVANDO O ÍNDICE E O MAPA DE PRODUTOS ===
faiss.write_index(index, "faiss_index.bin")

with open("produto_id_map.pkl", "wb") as f:
    pickle.dump(ids, f)

print("✅ Vetores gerados e salvos com sucesso.")