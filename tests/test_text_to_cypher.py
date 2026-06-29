import os
from llama_index.core import PropertyGraphIndex, Settings
from llama_index.llms.ollama import Ollama
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.indices.property_graph import TextToCypherRetriever

llm = Ollama(model="llama3.1", request_timeout=120.0, additional_kwargs={"num_ctx": 16384, "temperature": 0.0})
Settings.llm = llm

graph_store = Neo4jPropertyGraphStore(
    username="neo4j",
    password="Avyukt@TATA_RATAN2026",
    url="bolt://localhost:7687",
)

retriever = TextToCypherRetriever(graph_store, llm=llm)

query = "When was Tata Steel established?"
print("Generating Cypher for:", query)
nodes = retriever.retrieve(query)
for node in nodes:
    print(node.text)
