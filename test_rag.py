from dotenv import load_dotenv
load_dotenv()

from backend.core.rag import RAGPipeline

rag = RAGPipeline()

questions = [
    "What does the health check endpoint do?",
    "How does the code parser extract functions?",
    "How is the FAISS index built and saved?",
    "What happens when a user uploads a zip file?",
]

for q in questions:
    print(f"\n{'='*60}")
    print(f"❓ {q}")
    print(f"{'='*60}")
    result = rag.ask(q)
    print(result["answer"])
    print(f"\n📁 Sources used:")
    for s in result["sources"]:
        print(f"   [{s['score']}] {s['name']} in {s['file']} lines {s['lines']}")