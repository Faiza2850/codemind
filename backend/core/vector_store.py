import faiss
import numpy as np
import pickle
import os
from backend.core.embedder import CodeChunk, CodeEmbedder, EMBED_DIM
from tqdm import tqdm

INDEX_FILE  = "data/indexes/faiss.index"
CHUNKS_FILE = "data/indexes/chunks.pkl"


class VectorStore:
    """Stores code chunk embeddings in FAISS, supports semantic search."""

    def __init__(self):
        self.embedder = CodeEmbedder()
        self.index    = None      # FAISS index
        self.chunks   = []        # parallel list of CodeChunk objects

    # ── Indexing ─────────────────────────────────────────────

    def build_from_parsed_files(self, parsed_files: list):
        """
        Takes output of CodeParser.parse_directory() and builds
        a full FAISS index from all functions and classes found.
        """
        chunks = self._parsed_files_to_chunks(parsed_files)
        if not chunks:
            print("⚠️  No chunks found — nothing to index")
            return

        print(f"\n🔨 Building index for {len(chunks)} chunks...")
        self._build_index(chunks)
        self.save()
        print(f"✅ Index built and saved — {len(chunks)} chunks indexed")

    def _parsed_files_to_chunks(self, parsed_files: list) -> list[CodeChunk]:
        """Convert ParsedFile objects → flat list of CodeChunks."""
        chunks = []
        for pf in parsed_files:

            # One chunk per function
            for fn in pf.functions:
                chunks.append(CodeChunk(
                    chunk_id   = f"{pf.file_path}::{fn.name}",
                    file_path  = pf.file_path,
                    language   = pf.language,
                    chunk_type = "function",
                    name       = fn.name,
                    source_code= fn.source_code,
                    start_line = fn.start_line,
                    end_line   = fn.end_line,
                    docstring  = fn.docstring,
                    metadata   = {
                        "args":       fn.args,
                        "calls":      fn.calls,
                        "complexity": fn.complexity,
                    },
                ))

            # One chunk per class
            for cls in pf.classes:
                chunks.append(CodeChunk(
                    chunk_id   = f"{pf.file_path}::{cls.name}",
                    file_path  = pf.file_path,
                    language   = pf.language,
                    chunk_type = "class",
                    name       = cls.name,
                    source_code= f"class {cls.name}({', '.join(cls.base_classes)}):",
                    start_line = cls.start_line,
                    end_line   = cls.end_line,
                    docstring  = cls.docstring,
                    metadata   = {
                        "methods":      cls.methods,
                        "base_classes": cls.base_classes,
                    },
                ))

            # One chunk for all imports in a file
            if pf.imports:
                chunks.append(CodeChunk(
                    chunk_id   = f"{pf.file_path}::__imports__",
                    file_path  = pf.file_path,
                    language   = pf.language,
                    chunk_type = "import_block",
                    name       = "__imports__",
                    source_code= "\n".join(pf.imports),
                    start_line = 1,
                    end_line   = len(pf.imports),
                    docstring  = None,
                    metadata   = {},
                ))

        return chunks

    def _build_index(self, chunks: list[CodeChunk]):
        """Embed all chunks and store in FAISS."""
        self.chunks = chunks

        # Build texts to embed
        texts = [self.embedder.chunk_text(c) for c in chunks]

        # Embed in batches of 16 with progress bar
        all_vecs = []
        batch_size = 16
        for i in tqdm(range(0, len(texts), batch_size), desc="Embedding"):
            batch = texts[i : i + batch_size]
            vecs  = self.embedder.embed(batch)
            all_vecs.append(vecs)

        matrix = np.vstack(all_vecs).astype(np.float32)

        # Normalize for cosine similarity
        faiss.normalize_L2(matrix)

        # Build flat index (exact search — good up to ~100k chunks)
        self.index = faiss.IndexFlatIP(EMBED_DIM)   # Inner Product = cosine after normalize
        self.index.add(matrix)

    # ── Search ────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Natural language query → top-K most relevant code chunks.
        Returns list of dicts with chunk info + similarity score.
        """
        if self.index is None:
            raise RuntimeError("Index not built. Call build_from_parsed_files() first.")

        # Embed the query
        q_vec = self.embedder.embed_single(query).reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(q_vec)

        # Search
        scores, indices = self.index.search(q_vec, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk = self.chunks[idx]
            results.append({
                "score":       round(float(score), 4),
                "chunk_id":    chunk.chunk_id,
                "file_path":   chunk.file_path,
                "name":        chunk.name,
                "chunk_type":  chunk.chunk_type,
                "start_line":  chunk.start_line,
                "end_line":    chunk.end_line,
                "source_code": chunk.source_code,
                "docstring":   chunk.docstring,
                "language":    chunk.language,
            })

        return results

    # ── Persistence ───────────────────────────────────────────

    def save(self):
        os.makedirs("data/indexes", exist_ok=True)
        faiss.write_index(self.index, INDEX_FILE)
        with open(CHUNKS_FILE, "wb") as f:
            pickle.dump(self.chunks, f)
        print(f"💾 Saved index → {INDEX_FILE}")
        print(f"💾 Saved chunks → {CHUNKS_FILE}")

    def load(self):
        if not os.path.exists(INDEX_FILE):
            raise FileNotFoundError("No index found. Run indexing first.")
        self.index  = faiss.read_index(INDEX_FILE)
        with open(CHUNKS_FILE, "rb") as f:
            self.chunks = pickle.load(f)
        print(f"✅ Loaded {len(self.chunks)} chunks from index")