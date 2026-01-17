from qdrant_client import QdrantClient
client = QdrantClient(path="./storage_db")
print("Methods:", [m for m in dir(client) if not m.startswith("_")])
