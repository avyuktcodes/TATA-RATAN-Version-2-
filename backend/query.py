import os
import asyncio
import logging
import sys

# Enable verbose logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

from llama_index.core import PropertyGraphIndex, Settings
from llama_index.core.indices.property_graph import CustomPGRetriever, LLMSynonymRetriever
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

# 1. Initialize Engines
llm = Ollama(model="llama3.1", request_timeout=600.0, additional_kwargs={"num_ctx": 16384, "temperature": 0.0})
embed_model = OllamaEmbedding(model_name="nomic-embed-text", additional_kwargs={"num_ctx": 8192})

Settings.llm = llm
Settings.embed_model = embed_model

# 2. Connect to your existing Neo4j Database
print("Connecting to Neo4j...")
graph_store = Neo4jPropertyGraphStore(
    username="neo4j",
    password="Avyukt@TATA_RATAN2026",
    url="bolt://localhost:7687",
)

# 3. Load the Property Graph Index
print("Loading the Graph and Vectors...")
index = PropertyGraphIndex.from_existing(
    property_graph_store=graph_store,
    embed_model=embed_model,
)

# 4. Create the Hybrid Query Engine
print("Configuring Hybrid Retrievers...")

class ChunkVectorRetriever(CustomPGRetriever):
    def init(self, **kwargs):
        self.embed_model = kwargs.get("embed_model")
        self.top_k = kwargs.get("top_k", 5)
        
    def custom_retrieve(self, query_str):
        query_embedding = self.embed_model.get_query_embedding(query_str)
        cypher = """
        MATCH (n:__Node__) WHERE n.embedding IS NOT NULL
        WITH n, vector.similarity.cosine(n.embedding, $embedding) AS score
        ORDER BY score DESC LIMIT toInteger($limit)
        RETURN n.text AS text, score
        """
        data = self.graph_store.structured_query(
            cypher, param_map={"embedding": query_embedding, "limit": self.top_k}
        )
        nodes = []
        for record in data:
            nodes.append(NodeWithScore(node=TextNode(text=record["text"]), score=record["score"]))
        return nodes

vector_retriever = ChunkVectorRetriever(
    graph_store=graph_store,
    embed_model=embed_model,
    top_k=5
)

synonym_retriever = LLMSynonymRetriever(
    graph_store,
    llm=llm,
    include_text=False,
)

class KeywordCypherRetriever(CustomPGRetriever):
    def init(self, **kwargs):
        pass
        
    def custom_retrieve(self, query_str):
        import re
        q_lower = query_str.lower()
        cypher = None
        
        if "pillar" in q_lower:
            match = re.search(r'pillar\s*(\d+)', q_lower)
            if match:
                pillar_num = int(match.group(1))
                pillar_id = f"P{pillar_num:02d}"
                cypher = f"MATCH (p:Pillar {{pillarId: '{pillar_id}'}}) RETURN 'Pillar ' + p.pillarId + ': ' + p.name AS text"
            else:
                cypher = "MATCH (p:Pillar) RETURN 'Pillar ' + p.pillarId + ': ' + p.name AS text"
        elif any(w in q_lower for w in ["established", "founded", "headquarters", "hq"]):
            cypher = "MATCH (c:Company) RETURN 'Company Name: ' + c.name + ', Founded: ' + toString(c.founded) + ', Headquarters: ' + c.headquarters AS text"
        elif any(w in q_lower for w in ["revenue", "turnover", "ebitda", "profit", "pat"]):
            cypher = "MATCH (m:Metric) WHERE m.category = 'Finance and Accounts' RETURN m.name + ': ' + toString(m.value) + ' ' + m.unit AS text"
        elif any(w in q_lower for w in ["capacity", "crude steel"]):
            cypher = "MATCH (m:Metric) WHERE m.category = 'Manufacturing and Operations' RETURN m.name + ': ' + toString(m.value) + ' ' + m.unit AS text"
        elif any(w in q_lower for w in ["safety", "ltifr", "injuries", "injury"]):
            cypher = "MATCH (m:Metric) WHERE m.category = 'Safety' RETURN m.name + ': ' + toString(m.value) + ' ' + m.unit AS text"
        elif any(w in q_lower for w in ["employees", "workers", "workforce"]):
            cypher = "MATCH (m:Metric) WHERE m.category = 'People/HR' RETURN m.name + ': ' + toString(m.value) + ' ' + m.unit AS text"
            
        nodes = []
        if cypher:
            try:
                data = self.graph_store.structured_query(cypher)
                for record in data:
                    nodes.append(NodeWithScore(node=TextNode(text=record["text"]), score=1.0))
            except Exception as e:
                print(f"Cypher execution error: {e}")
                
        return nodes

keyword_cypher_retriever = KeywordCypherRetriever(graph_store=graph_store)

query_engine = index.as_query_engine(
    sub_retrievers=[vector_retriever, synonym_retriever, keyword_cypher_retriever]
)

if __name__ == "__main__":
    print("\n=============================================")
    print("Welcome to Tata_Ratan Chatbot (Interactive Mode)")
    print("Type 'exit' or 'quit' to stop.")
    print("=============================================\n")
    
    while True:
        try:
            question = input("\nUSER: ")
            if question.strip().lower() in ['exit', 'quit']:
                print("\nGoodbye!")
                break
            if not question.strip():
                continue
                
            print("\nTata_Ratan is thinking (searching graph and vectors)...\n")
            response = query_engine.query(question)
            
            print(f"\nTATA_RATAN:\n{response}")
            
            # Print sources for debugging
            print("\n--- RETRIEVED SOURCES ---")
            for node in response.source_nodes:
                print(f"Score: {node.score:.4f} - Text: {node.node.get_text()[:200]}...")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
