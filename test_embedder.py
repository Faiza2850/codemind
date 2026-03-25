from backend.core.parser import CodeParser
from backend.core.vector_store import VectorStore

# Step 1 — parse your backend folder
print("=== Step 1: Parsing ===")
parser = CodeParser()
parsed = parser.parse_directory("backend")
print(f"Parsed {len(parsed)} files")

# Step 2 — build the index (downloads CodeBERT on first run)
print("\n=== Step 2: Building FAISS index ===")
store = VectorStore()
store.build_from_parsed_files(parsed)

# Step 3 — search with natural language
print("\n=== Step 3: Semantic search ===")
queries = [
    "health check endpoint",
    "parse directory recursively walk files",
    "faiss index build embed vectors",
    "extract function name arguments",
    "load save pickle index to disk",
]

for q in queries:
    print(f"\n🔍 Query: '{q}'")
    results = store.search(q, top_k=3)
    for r in results:
        print(f"   [{r['score']:.3f}] {r['name']}() in {r['file_path']} line {r['start_line']}")