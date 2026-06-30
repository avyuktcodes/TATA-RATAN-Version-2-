import os
import asyncio
import logging
import sys

# Enable verbose logging
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

from llama_index.core import PropertyGraphIndex, Settings
from llama_index.core.indices.property_graph import CustomPGRetriever, LLMSynonymRetriever, TextToCypherRetriever
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.llms.ollama import Ollama
from llama_index.llms.gemini import Gemini
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
    password=os.environ.get("NEO4J_PASSWORD", "password_not_set"),
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
    top_k=10
)

synonym_retriever = LLMSynonymRetriever(
    graph_store,
    llm=llm,
    include_text=False,
)

# 5. Gemini 3.5 Flash Text-To-Cypher Integration
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("\n❌ ERROR: GEMINI_API_KEY is not set in this terminal!")
    print("Please run: export GEMINI_API_KEY='your-key-here'")
    sys.exit(1)

gemini = Gemini(model="models/gemini-3.5-flash", api_key=api_key)

def strip_cypher_markdown(cypher: str) -> str:
    cypher = cypher.strip()
    if cypher.startswith("```"):
        lines = cypher.split("\n")
        if lines[0].startswith("```"): lines = lines[1:]
        if lines and lines[-1].startswith("```"): lines = lines[:-1]
        cypher = "\n".join(lines)
    return cypher.strip()

text_to_cypher_retriever = TextToCypherRetriever(
    graph_store=graph_store,
    llm=gemini,
    cypher_validator=strip_cypher_markdown
)

query_engine = index.as_query_engine(
    sub_retrievers=[vector_retriever, synonym_retriever, text_to_cypher_retriever],
    streaming=True
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
                
            print("\nThinking (searching graph and vectors)...")
            response = query_engine.query(question)
            
            print("\n--- Response ---")
            for text in response.response_gen:
                print(text, end="", flush=True)
            print("\n")
            
            # Print sources for debugging
            print("\n--- RETRIEVED SOURCES ---")
            for node in response.source_nodes:
                print(f"Score: {node.score:.4f} - Text: {node.node.get_text()[:200]}...")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
