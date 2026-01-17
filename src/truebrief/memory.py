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

    def add_fact(self, text: str, source_url: str):
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
                    payload={"text": text, "source": source_url}
                )
            ]
        )

    def is_novel(self, text: str) -> Tuple[bool, float, str]:
        """
        Checks if the fact exists in memory.
        Returns: (is_novel, max_similarity, closest_match_text)
        """
        vector = self._vectorize(text)
        
        # Search Qdrant
        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=1,
            score_threshold=0.0
        ).points
        
        if not results:
            return True, 0.0, ""

        best_match = results[0]
        similarity = best_match.score
        match_text = best_match.payload.get("text", "")

        if similarity > SIMILARITY_THRESHOLD:
            return False, similarity, match_text # Old News
        
        return True, similarity, match_text # Novel

    def get_all_facts(self) -> List[dict]:
        """
        Retrieves all stored facts from Qdrant.
        """
        # scroll returns all points in the collection
        results, _ = self.client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        return [r.payload for r in results]

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
