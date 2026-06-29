import os
# 0. CRITICAL PATCHES
os.environ["LLAMA_INDEX_INSTRUMENTATION_ENABLED"] = "false"

import sys
import asyncio
import nest_asyncio
from pathlib import Path
from typing import List
from llama_parse import LlamaParse
from llama_index.core import PropertyGraphIndex, Settings
from llama_index.core.callbacks import CallbackManager
from llama_index.core.callbacks.base_handler import BaseCallbackHandler
from llama_index.core.schema import Document, BaseNode, TransformComponent, MetadataMode
from llama_index.core.ingestion.pipeline import run_transformations, arun_transformations
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.graph_stores.types import KG_NODES_KEY, KG_RELATIONS_KEY
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor


class IngestProgressHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        super().__init__(event_starts_to_ignore=[], event_ends_to_ignore=[])

    def on_event_start(
        self,
        event_type,
        payload=None,
        event_id="",
        parent_id="",
        **kwargs,
    ) -> str:
        print(f"[INGEST CALLBACK START] {event_type} parent={parent_id} payload={payload}", flush=True)
        return event_id

    def on_event_end(self, event_type, payload=None, event_id="", **kwargs) -> None:
        print(f"[INGEST CALLBACK END] {event_type} payload={payload}", flush=True)

    def start_trace(self, trace_id=None) -> None:
        print(f"[INGEST TRACE START] {trace_id}", flush=True)

    def end_trace(self, trace_id=None, trace_map=None) -> None:
        print(f"[INGEST TRACE END] {trace_id}", flush=True)


class LoggedTransform(TransformComponent):
    transform: TransformComponent
    name: str

    def __init__(self, transform: TransformComponent, name: str) -> None:
        super().__init__(transform=transform, name=name)

    def __call__(self, nodes, show_progress: bool = False, **kwargs):
        print(f"[TRANSFORM START] {self.name} nodes={len(nodes)} show_progress={show_progress}", flush=True)
        result = self.transform(nodes, show_progress=show_progress, **kwargs)
        print(f"[TRANSFORM END] {self.name} nodes={len(result)}", flush=True)
        return result

    async def acall(self, nodes, show_progress: bool = False, **kwargs):
        print(f"[TRANSFORM START] {self.name} nodes={len(nodes)} show_progress={show_progress}", flush=True)
        result = await self.transform.acall(nodes, show_progress=show_progress, **kwargs)
        print(f"[TRANSFORM END] {self.name} nodes={len(result)}", flush=True)
        return result


nest_asyncio.apply()

DATA_DIR = os.getenv("DATA_DIR", "./data")

api_key = os.getenv("LLAMA_CLOUD_API_KEY", "<YOUR_API_KEY>")
os.environ["LLAMA_CLOUD_API_KEY"] = api_key

# 1. Initialize Engines
llm = Ollama(model="llama3.1", request_timeout=120.0, additional_kwargs={"num_ctx": 16384, "temperature": 0.0})

# Add monkey patching to Ollama to log LLM calls explicitly
orig_chat = llm.__class__.chat
orig_achat = llm.__class__.achat

def logged_chat(self, *args, **kwargs):
    print("[LLM] chat request start", flush=True)
    try:
        res = orig_chat(self, *args, **kwargs)
        print("[LLM] chat request end", flush=True)
        return res
    except Exception as e:
        print(f"[LLM] chat error: {e}", flush=True)
        raise

async def logged_achat(self, *args, **kwargs):
    print("[LLM] achat request start", flush=True)
    try:
        res = await orig_achat(self, *args, **kwargs)
        print("[LLM] achat request end", flush=True)
        return res
    except Exception as e:
        print(f"[LLM] achat error: {e}", flush=True)
        raise

llm.__class__.chat = logged_chat
llm.__class__.achat = logged_achat

embed_model = OllamaEmbedding(model_name="nomic-embed-text", additional_kwargs={"num_ctx": 8192})

Settings.llm = llm
Settings.embed_model = embed_model
Settings.chunk_size = 1024 
Settings.chunk_overlap = 200 

# 2. Neo4j Connection
graph_store = Neo4jPropertyGraphStore(
    username="neo4j",
    password="Avyukt@TATA_RATAN2026",
    url="bolt://localhost:7687",
    refresh_schema=False
)

# 3. Data Parsing
print(f"Using data directory: {DATA_DIR}")

pdf_paths = sorted([p for p in Path(DATA_DIR).rglob("*.pdf")])
if not pdf_paths:
    raise FileNotFoundError(f"No PDF files found in {DATA_DIR}")

print(f"Found {len(pdf_paths)} PDF file(s) to parse.")

documents: List[Document] = []
local_pdf_parse = False

try:
    parser = LlamaParse(result_type="markdown", verbose=True)
    local_pdf_parse = bool(api_key)
except Exception as e:
    print(f"WARNING: cloud parser unavailable ({e}). Falling back to local PDF parsing.")
    local_pdf_parse = False

if local_pdf_parse:
    for pdf_path in pdf_paths:
        print(f"Parsing PDF via LlamaParse: {pdf_path}")
        job_result = parser.parse(str(pdf_path))
        if not job_result or not getattr(job_result, "pages", None):
            print(f"Warning: no pages returned for {pdf_path}")
            continue

        for page in job_result.pages:
            page_text = page.md or page.text or ""
            if not page_text.strip():
                continue
            doc = Document(
                id_=f"{pdf_path.stem}_page_{page.page}",
                text=page_text,
                extra_info={
                    "file_path": str(pdf_path),
                    "page_number": page.page,
                },
            )
            documents.append(doc)
else:
    from pypdf import PdfReader
    for pdf_path in pdf_paths:
        print(f"Parsing PDF locally: {pdf_path}")
        reader = PdfReader(pdf_path)
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if not page_text.strip():
                continue
            doc = Document(
                id_=f"{pdf_path.stem}_page_{page_number}",
                text=page_text,
                extra_info={
                    "file_path": str(pdf_path),
                    "page_number": page_number,
                },
            )
            documents.append(doc)

print(f"Loaded and parsed {len(documents)} pages.")

# 4. Structuring Financial Graph Logic Extractors (OPEN ONTOLOGY)
print("4. Configuring Open Ontology Extractors...")

pillar_prompt = """
You are an expert Tata Steel Knowledge Graph architect. 
Extract entities and relationships from the text. 
Prioritize these 16 pillars: People/HR, Safety, Finance & Accounts, Customer Experience,
Manufacturing & Operations, Supply Chain, Procurement, Raw Materials & Mining,
Engineering & Projects, Market Intelligence, Quality Management (TQM), Technology & R&D, 
Corporate Services, AI / IT Systems & Digital, Environment & Sustainability, Legal & Compliance.
If an entity fits a pillar, label it. If it is relevant but not in the list, extract it as an OTHER_ENTITY.
"""

financial_extractor = SchemaLLMPathExtractor(
    llm=llm,
    extract_prompt=pillar_prompt,
    possible_entities=[
        "COMPANY",
        "FINANCIAL_METRIC",
        "FISCAL_YEAR",
        "SUBSIDIARY",
        "REPORT_SECTION",
        "ASSET",
        "LIABILITY",
        "PLANT",
        "MINING_LOCATION",
        "OTHER_ENTITY",
    ],
    possible_relations=[
        "REPORTED",
        "EARNED",
        "OWNS_ASSET",
        "DECREASED_BY",
        "INCREASED_BY",
        "ALLOCATED_TO",
        "OPERATES",
        "RELATES_TO",
    ],
    strict=False,
)

# Wrap KG extractor so we see when extraction begins and ends.
financial_extractor = LoggedTransform(financial_extractor, "financial_extractor")

# Wrap the embedder methods for visible progress.
def wrap_embed_method(obj, name):
    orig = getattr(obj, name)

    if asyncio.iscoroutinefunction(orig):
        async def wrapped(*args, **kwargs):
            print(f"[EMBED] {name} start args={len(args)} kwargs={list(kwargs)}", flush=True)
            result = await orig(*args, **kwargs)
            print(f"[EMBED] {name} complete len(result)={len(result) if hasattr(result, '__len__') else 'unknown'}", flush=True)
            return result
    else:
        def wrapped(*args, **kwargs):
            print(f"[EMBED] {name} start args={len(args)} kwargs={list(kwargs)}", flush=True)
            result = orig(*args, **kwargs)
            print(f"[EMBED] {name} complete len(result)={len(result) if hasattr(result, '__len__') else 'unknown'}", flush=True)
            return result

    object.__setattr__(obj, name, wrapped)

wrap_embed_method(embed_model, "get_text_embedding_batch")
wrap_embed_method(embed_model, "aget_text_embedding_batch")

# Wrap Neo4j upsert methods for visible progress.
def wrap_store_method(obj, name):
    orig = getattr(obj, name)

    def wrapped(*args, **kwargs):
        print(f"[NEO4J] {name} start len(args)={len(args)} kwargs={list(kwargs)}", flush=True)
        result = orig(*args, **kwargs)
        print(f"[NEO4J] {name} complete", flush=True)
        return result

    setattr(obj, name, wrapped)

wrap_store_method(graph_store, "upsert_llama_nodes")
wrap_store_method(graph_store, "upsert_nodes")
wrap_store_method(graph_store, "upsert_relations")

# 5. Ingest to Neo4j
print("5. Launching Processing Nodes into Neo4j Matrix...")
callback_manager = CallbackManager(handlers=[IngestProgressHandler()])
print("Injecting callback manager into Settings and node parser...", flush=True)
Settings.callback_manager = callback_manager
Settings.llm = llm
Settings.embed_model = embed_model
# Access the properties once so the callback manager is wired into the cached objects.
_ = Settings.llm
_ = Settings.embed_model
node_parser = Settings.node_parser
Settings.transformations = [LoggedTransform(node_parser, "node_parser")]
print(f"Active callbacks: {[type(h).__name__ for h in callback_manager.handlers]}")
print(f"Document parser transform pipeline: {[type(t).__name__ for t in Settings.transformations]}")
print(f"Using callback manager: {callback_manager}")
print(f"Documents to ingest: {len(documents)}")
print("Starting PropertyGraphIndex.from_documents() with explicit progress...", flush=True)
index = PropertyGraphIndex.from_documents(
    documents,
    property_graph_store=graph_store,
    kg_extractors=[financial_extractor],
    callback_manager=callback_manager,
    show_progress=True,
    use_async=False,
)

print("SUCCESS: Batch Data Node Matrix Ingestion Complete!")