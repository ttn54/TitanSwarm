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

    @classmethod
    def from_content(cls, content: str, db_path: str = ":memory:") -> "LedgerManager":
        """
        Create a LedgerManager that operates on in-memory content rather than
        a file on disk.  Used in multi-tenant mode where ledger content comes
        from the database instead of data/ledger.md.
        """
        import tempfile, os
        # Write content to a temp file so build_index() can read it
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        tmp.write(content)
        tmp.close()
        mgr = cls(ledger_path=tmp.name, db_path=db_path)
        mgr._tmp_path = tmp.name   # keep reference so caller can clean up if needed
        return mgr

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

    def write_github_section(self, github_text: str) -> None:
        """
        Write (or replace) the '## GitHub Projects:' section in the ledger file.

        If the section already exists it is replaced entirely — no duplicates.
        If it does not exist it is appended after the existing content.
        """
        _MARKER = "## GitHub Projects:"
        new_block = f"{_MARKER}\n{github_text}\n"

        if not os.path.exists(self.ledger_path):
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                f.write(new_block)
            return

        content = open(self.ledger_path, encoding="utf-8").read()

        if _MARKER in content:
            # Replace from the marker to the next top-level section (##) or end of file
            import re
            content = re.sub(
                rf"{re.escape(_MARKER)}.*?(?=\n## |\Z)",
                new_block.rstrip(),
                content,
                count=1,
                flags=re.DOTALL,
            )
        else:
            content = content.rstrip() + "\n\n" + new_block

        with open(self.ledger_path, "w", encoding="utf-8") as f:
            f.write(content)

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
