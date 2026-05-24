import os
import json
import chromadb
from sentence_transformers import SentenceTransformer
from api.models import AlertEvent, HistoricalMatch

class HistorianAgent:
    def __init__(self, chroma_path: str = None):
        path = chroma_path or os.getenv("CHROMA_PATH", "./data/chroma_db")
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection("incidents")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    async def search(self, alert: AlertEvent, top_k: int = 5) -> list[HistoricalMatch]:
        query = f"{alert.service} {alert.component} {alert.anomaly}"
        embedding = self.model.encode(query).tolist()
        
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["metadatas", "distances"]
        )
        
        matches = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            meta = results["metadatas"][0][i]
            
            similarity = max(0.0, 1.0 - (distance / 2.0))
            if similarity < 0.25:
                continue
                
            res_steps = meta["resolution_steps"]
            if isinstance(res_steps, str):
                try:
                    res_steps = json.loads(res_steps)
                except:
                    res_steps = [res_steps]

            match = HistoricalMatch(
                incident_id=results["ids"][0][i],
                title=meta["title"],
                description=meta["description"],
                root_cause=meta["root_cause"],
                resolution_steps=res_steps,
                severity=meta["severity"],
                time_to_resolve_minutes=int(meta["time_to_resolve_minutes"]),
                similarity_score=float(similarity)
            )
            matches.append(match)
            
        return sorted(matches, key=lambda x: x.similarity_score, reverse=True)

    async def ingest_resolved(self, incident: dict):
        doc = f"{incident['title']}. {incident['description']}. Root cause: {incident['root_cause']}"
        embedding = self.model.encode(doc).tolist()
        metadata = {k: str(v) if isinstance(v, (list, dict, bool)) else v for k, v in incident.items()}
        self.collection.add(
            documents=[doc],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[incident["id"]]
        )
