# Phase 3: The Immutable Ledger & Vector Store Design

## 1. Architecture and Data Flow
* **The Ledger (`data/ledger.md`):** A plain text source-of-truth file containing the user's verified history (education, projects, jobs).
* **The Ingestor:** Python logic that reads the ledger and breaks it down into small semantic chunks (e.g., ~200 words each) using Langchain's text splitters.
* **Vector Store Database:** We use FAISS (Facebook AI Similarity Search) and OpenAI embeddings (or local HuggingFace embeddings via sentence-transformers) to convert these chunks into searchable mathematical vectors.

## 2. Data Structures & Interfaces
* **Manager:** `src/core/ledger.py` will define the `LedgerManager` class.
* **Methods:**
  * `__init__(ledger_path: str, db_path: str)`: Initializes the paths.
  * `async def build_index(self) -> None`: Reads `ledger.md`, chunks it, creates embeddings, and saves the FAISS index to the disk.
  * `async def search_facts(self, query: str, top_k: int = 3) -> List[str]`: Loads the FAISS index and returns the top K factual chunks that are relevant to the query.

## 3. Edge Cases & Failure Modes
* **Missing Ledger File:** If `data/ledger.md` does not exist, `build_index` must raise a `FileNotFoundError` instead of building an empty index.
* **Missing Index:** If `search_facts` is called before `build_index`, it must raise a clear exception.
* **Chunk Limits:** Text must be cleanly split upon double-newlines so that different projects don't bleed into the same vector space.