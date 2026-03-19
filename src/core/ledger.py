import os
from typing import List
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

class LedgerManager:
    def __init__(self, ledger_path: str, db_path: str):
        self.ledger_path = ledger_path
        self.db_path = db_path
        self.index = None
        self.chunks = []
        self.model = None

    def _lazy_load_model(self):
        if self.model is None:
            # We use a tiny, fast model locally so we don't have to pay for OpenAI API calls during indexing
            self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def build_index(self) -> None:
        if not os.path.exists(self.ledger_path):
            raise FileNotFoundError(f"Ledger file not found at {self.ledger_path}")
            
        with open(self.ledger_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split the text by double newlines (paragraphs/projects) to prevent bleeding context
        self.chunks = [chunk.strip() for chunk in content.split('\n\n') if chunk.strip()]
        
        if not self.chunks:
            self.index = None
            return

        self._lazy_load_model()
        
        # Convert text chunks into mathematical vectors (embeddings)
        embeddings = self.model.encode(self.chunks)
        
        # Build the FAISS similarity search index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension) # L2 Distance metric
        self.index.add(np.array(embeddings).astype('float32'))

    def search_facts(self, query: str, top_k: int = 3) -> List[str]:
        if self.index is None:
            raise RuntimeError("Cannot search facts before building the index. Call build_index() first.")
            
        self._lazy_load_model()
        
        # Convert the user's question into the same mathematical space
        query_vector = self.model.encode([query])
        
        # Ask FAISS for the closest facts
        distances, indices = self.index.search(np.array(query_vector).astype('float32'), min(top_k, len(self.chunks)))
        
        results = []
        for idx in indices[0]:
            if idx != -1 and idx < len(self.chunks):
                results.append(self.chunks[idx])
                
        return results
