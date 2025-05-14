import oracledb
import os
from sentence_transformers import SentenceTransformer
import numpy as np

# === CONFIGURAÇÃO ORACLE COM WALLET ===
WALLET_PATH = "/WALLET_PATH/Wallet_oradb23ai"
DB_ALIAS = "oradb23ai_high"
USERNAME = "USER"
PASSWORD = "Password"

os.environ["TNS_ADMIN"] = WALLET_PATH

# === CONECTANDO USANDO oracledb (modo thin) ===
connection = oracledb.connect(
    user=USERNAME,
    password=PASSWORD,
    dsn=DB_ALIAS,
    config_dir=WALLET_PATH,
    wallet_location=WALLET_PATH,
    wallet_password=PASSWORD
)

cursor = connection.cursor()

# === CONSULTA A TABELA DE PRODUTOS ===
cursor.execute("SELECT id, codigo, descricao FROM produtos")
rows = cursor.fetchall()

ids = []
descricoes = []

for row in rows:
    ids.append((row[0], row[1], row[2]))
    descricoes.append(row[2])

# === GERAÇÃO DOS EMBEDDINGS ===
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(descricoes, convert_to_numpy=True)

# === CRIAÇÃO DA TABELA DE EMBEDDINGS (caso não exista) ===
cursor.execute("""
               BEGIN
                   EXECUTE IMMEDIATE '
            CREATE TABLE embeddings_produtos (
                id NUMBER PRIMARY KEY,
                codigo VARCHAR2(100),
                descricao VARCHAR2(4000),
                vetor BLOB
            )';
               EXCEPTION
                   WHEN OTHERS THEN
                       IF SQLCODE != -955 THEN
                           RAISE;
                       END IF;
               END;
               """)

# === INSERÇÃO OU ATUALIZAÇÃO DOS DADOS ===
for (id_, codigo, descricao), vetor in zip(ids, embeddings):
    vetor_bytes = vetor.astype(np.float32).tobytes()
    cursor.execute("""
        MERGE INTO embeddings_produtos tgt
        USING (SELECT :id AS id FROM dual) src
        ON (tgt.id = src.id)
        WHEN MATCHED THEN
            UPDATE SET codigo = :codigo, descricao = :descricao, vetor = :vetor
        WHEN NOT MATCHED THEN
            INSERT (id, codigo, descricao, vetor)
            VALUES (:id, :codigo, :descricao, :vetor)
    """, {
        "id": id_,
        "codigo": codigo,
        "descricao": descricao,
        "vetor": vetor_bytes
    })

connection.commit()
cursor.close()
connection.close()

print("✅ Vetores gravados com sucesso no banco Oracle.")