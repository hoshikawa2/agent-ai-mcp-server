# product_search.py

import faiss
import pickle
import difflib
import numpy as np
from rapidfuzz import fuzz
from langchain_community.embeddings import OCIGenAIEmbeddings


class BuscaProdutoSimilar:
    def __init__(
            self,
            faiss_index_path="faiss_index.bin",
            id_map_path="produto_id_map.pkl",
            top_k=5,
            distancia_minima=1.0,
            model_id="cohere.embed-english-light-v3.0",
            service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
            compartment_id="ocid1.compartment.oc1..aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            auth_profile="DEFAULT"
    ):
        print("📦 Carregando índice vetorial...")
        self.index = faiss.read_index(faiss_index_path)
        with open(id_map_path, "rb") as f:
            self.id_map = pickle.load(f)
        self.top_k = top_k
        self.distancia_minima = distancia_minima
        self.embedding = OCIGenAIEmbeddings(
            model_id=model_id,
            service_endpoint=service_endpoint,
            compartment_id=compartment_id,
            auth_profile=auth_profile
        )

    def _corrigir_input(self, input_usuario):
        descricoes = [p["descricao"] for p in self.id_map]
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
        consulta_emb = np.array([consulta_emb])
        distances, indices = self.index.search(consulta_emb, self.top_k)

        for i, dist in zip(indices[0], distances[0]):
            if dist < self.distancia_minima:
                match = self.id_map[i]
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
            for produto in self.id_map:
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