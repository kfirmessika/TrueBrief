from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding
import uuid
from typing import List, Tuple

# Configuration
COLLECTION_NAME = "truebrief_facts"
STORAGE_PATH = "c:/kfir/myFiles/Projects/Apps/TrueBrief/data/storage_db" 
MODEL_NAME = "BAAI/bge-small-en-v1.5"

SIMILARITY_THRESHOLD = 0.85

class FactLedger:
    """
    The FactLedger remembers everything.
    It uses Qdrant (Local) to store vectors of facts.
    """
    def __init__(self):
        print(f"🧠 Initializing Memory (Qdrant) at {STORAGE_PATH}...")
        self.client = QdrantClient(path=STORAGE_PATH)
        self.embedding_model = TextEmbedding(model_name=MODEL_NAME)
        
        # Ensure collection exists
        if not self.client.collection_exists(COLLECTION_NAME):
            print("   -> Creating new collection...")
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
        else:
            print("   -> Loaded existing collection.")

    def _vectorize(self, text: str) -> List[float]:
        # Embed returns a generator, convert to list
        return list(self.embedding_model.embed([text]))[0]

    def add_fact(self, text: str, source_url: str, published_date: str = "", topic_name: str = ""):
        """
        Stores a fact in the ledger.
        """
        vector = self._vectorize(text)
        point_id = str(uuid.uuid4()) # Unique ID for the point
        
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"text": text, "source": source_url, "published_date": published_date, "topic_name": topic_name}
                )
            ]
        )

    def is_novel(self, text: str, topic_name: str = None) -> Tuple[bool, float, dict]:
        """
        Checks if the fact exists in memory.
        Returns: (is_novel, max_similarity, closest_match_payload)
        """
        vector = self._vectorize(text)
        
        # --- MISSION 7.3: Hybrid Filter ---
        from qdrant_client.http import models
        query_filter = None
        if topic_name:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="topic_name",
                        match=models.MatchValue(value=topic_name)
                    )
                ]
            )
        
        # Search Qdrant
        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=1,
            query_filter=query_filter,
            score_threshold=0.0
        ).points
        
        if not results:
            return True, 0.0, ""

        best_match = results[0]
        similarity = best_match.score
        match_payload = best_match.payload or {}

        if similarity > SIMILARITY_THRESHOLD:
            return False, similarity, match_payload # Old News
        
        return True, similarity, match_payload # Novel

    def get_all_facts(self, topic_filter: str = None) -> List[dict]:
        """
        Retrieves all stored facts from Qdrant, optionally filtered by topic_name.
        """
        # scroll returns all points in the collection
        results, _ = self.client.scroll(
            collection_name=COLLECTION_NAME,
            limit=500,
            with_payload=True,
            with_vectors=False
        )
        all_payloads = [r.payload for r in results]
        if topic_filter:
            # Safely get topic_name, defaulting to empty string if old schema
            return [p for p in all_payloads if p.get("topic_name", "") == topic_filter]
        return all_payloads

    def delete_facts_by_topic(self, topic_name: str):
        """
        Deletes all facts matching the specific topic name.
        """
        results, _ = self.client.scroll(
            collection_name=COLLECTION_NAME,
            limit=500,
            with_payload=True,
            with_vectors=False
        )
        to_delete = [r.id for r in results if r.payload and r.payload.get("topic_name", "") == topic_name]
        if to_delete:
            self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=to_delete
            )

if __name__ == "__main__":
    # Builder's Manual Test
    ledger = FactLedger()
    
    print("\n--- Test 1: Add Fact ---")
    fact = "The sky is blue today."
    ledger.add_fact(fact, "http://nature.com")
    print(f"Added: {fact}")
    
    print("\n--- Test 2: Check Similarity (Should be High) ---")
    similar_fact = "The sky is very blue."
    novel, score, match = ledger.is_novel(similar_fact)
    print(f"Input: '{similar_fact}'")
    print(f"Is Novel: {novel} (Score: {score:.2f})")
    print(f"Match: '{match}'")

    print("\n--- Test 3: Check Novelty (Should be Low) ---")
    new_fact = "The stock market crashed."
    novel, score, match = ledger.is_novel(new_fact)
    print(f"Input: '{new_fact}'")
    print(f"Is Novel: {novel} (Score: {score:.2f})")
