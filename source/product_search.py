import os
import oracledb
import numpy as np
import difflib
from rapidfuzz import fuzz
from langchain_community.embeddings import OCIGenAIEmbeddings


class BuscaProdutoSimilar:
    def __init__(
            self,
            top_k=5,
            distancia_minima=1.0,
            model_id="cohere.embed-english-light-v3.0",
            service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
            compartment_id="ocid1.compartment.oc1..aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            auth_profile="DEFAULT",
            wallet_path="/WALLET_PATH/Wallet_oradb23ai",
            db_alias="oradb23ai_high",
            username="USER",
            password="Password"
    ):
        os.environ["TNS_ADMIN"] = wallet_path
        self.conn = oracledb.connect(
            user=username,
            password=password,
            dsn=db_alias,
            config_dir=wallet_path,
            wallet_location=wallet_path,
            wallet_password=password
        )
        self.top_k = top_k
        self.distancia_minima = distancia_minima
        self.embedding = OCIGenAIEmbeddings(
            model_id=model_id,
            service_endpoint=service_endpoint,
            compartment_id=compartment_id,
            auth_profile=auth_profile
        )

        print("📦 Carregando vetores do Oracle...")
        self._carregar_embeddings()

    def _carregar_embeddings(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, codigo, descricao, vetor FROM embeddings_produtos")
        self.vetores = []
        self.produtos = []
        for row in cursor.fetchall():
            id_, codigo, descricao, blob = row
            vetor = np.frombuffer(blob.read(), dtype=np.float32)
            self.vetores.append(vetor)
            self.produtos.append({
                "id": id_,
                "codigo": codigo,
                "descricao": descricao
            })
        self.vetores = np.array(self.vetores)

    def _corrigir_input(self, input_usuario):
        descricoes = [p["descricao"] for p in self.produtos]
        sugestoes = difflib.get_close_matches(input_usuario, descricoes, n=1, cutoff=0.6)
        return sugestoes[0] if sugestoes else input_usuario

    def buscar_produtos_similares(self, descricao_input):
        descricao_input = descricao_input.strip()
        descricao_corrigida = self._corrigir_input(descricao_input)

        resultados = {
            "consulta_original": descricao_input,
            "consulta_utilizada": descricao_corrigida,
            "semanticos": [],
            "fallback_fuzzy": []
        }

        consulta_emb = self.embedding.embed_query(descricao_corrigida)
        consulta_emb = np.array(consulta_emb)

        # Cálculo de distância euclidiana
        dists = np.linalg.norm(self.vetores - consulta_emb, axis=1)
        top_indices = np.argsort(dists)[:self.top_k]

        for idx in top_indices:
            dist = dists[idx]
            if dist < self.distancia_minima:
                match = self.produtos[idx]
                similaridade = 1 / (1 + dist)
                resultados["semanticos"].append({
                    "id": match["id"],
                    "codigo": match["codigo"],
                    "descricao": match["descricao"],
                    "similaridade": round(similaridade * 100, 2),
                    "distancia": round(dist, 4)
                })

        if not resultados["semanticos"]:
            melhores_fuzz = []
            for produto in self.produtos:
                score = fuzz.token_sort_ratio(descricao_corrigida, produto["descricao"])
                melhores_fuzz.append((produto, score))
            melhores_fuzz.sort(key=lambda x: x[1], reverse=True)

            for produto, score in melhores_fuzz[:self.top_k]:
                resultados["fallback_fuzzy"].append({
                    "id": produto["id"],
                    "codigo": produto["codigo"],
                    "descricao": produto["descricao"],
                    "score_fuzzy": round(score, 2)
                })

        return resultados