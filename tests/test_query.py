from llama_index.core import PropertyGraphIndex, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

llm = Ollama(model="llama3.1", request_timeout=120.0, additional_kwargs={"num_ctx": 16384, "temperature": 0.0})
embed_model = OllamaEmbedding(model_name="nomic-embed-text", additional_kwargs={"num_ctx": 8192})

Settings.llm = llm
Settings.embed_model = embed_model

graph_store = Neo4jPropertyGraphStore(
    username="neo4j",
    password="Avyukt@TATA_RATAN2026",
    url="bolt://localhost:7687",
)

index = PropertyGraphIndex.from_existing(
    property_graph_store=graph_store,
    embed_model=embed_model,
)

from llama_index.core.indices.property_graph import VectorContextRetriever
retriever = VectorContextRetriever(graph_store, embed_model=embed_model, include_text=True)

query = "What are the key priorities or strategies mentioned for Tata Steel?"
nodes = retriever.retrieve(query)
print(f"Retrieved {len(nodes)} nodes.")
for n in nodes:
    print(n.text[:100])
