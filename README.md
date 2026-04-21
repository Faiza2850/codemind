# 🧠 Codebase Intelligence Engine

> AI that reads and explains entire codebases. Ask questions in plain English, get answers grounded in your actual code.

## ✨ Features

| Feature | Description |
|---|---|
| 💬 Natural language Q&A | Ask anything about your codebase |
| 🔍 Semantic code search | CodeBERT embeddings + FAISS vector search |
| 🗺️ Dependency graph | Visual map of file relationships |
| 🐛 Bug detection | AST analysis + pyflakes + complexity scoring |
| 🏗️ Architecture diagram | Auto-generated system layer diagram |
| 📊 Complexity analysis | Cyclomatic complexity hotspots |

## 🚀 Quick start

### With Docker (recommended)
\`\`\`bash
git clone https://github.com/your-username/codebase-intelligence-engine
cd codebase-intelligence-engine
cp .env.example .env
# Add your GROQ_API_KEY to .env
./start.sh
\`\`\`

Open http://localhost:8501

### Without Docker
\`\`\`bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000 &
streamlit run frontend/app.py --server.port 8501
\`\`\`

## 🏗️ Architecture

\`\`\`
Repository (ZIP or GitHub URL)
    ↓
Code Parser (Tree-sitter AST)
    ↓
Chunker → CodeBERT Embeddings
    ↓
FAISS Vector Index
    ↓
Retriever (semantic search)
    ↓
LLM (Groq / Gemini / Ollama)
    ↓
Explanation + Source References
\`\`\`

## 🛠️ Tech stack

- **Backend:** Python, FastAPI, Uvicorn
- **ML:** CodeBERT (microsoft/codebert-base), FAISS
- **Parsing:** Tree-sitter (Python, JS, TypeScript)
- **LLM:** Groq (Llama 3.1 70B) / Gemini / Ollama
- **Graph:** NetworkX, Matplotlib
- **Frontend:** Streamlit
- **Deploy:** Docker, docker-compose

## 📁 Project structure

\`\`\`
codebase-intelligence-engine/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── api/routes.py        # API endpoints
│   └── core/
│       ├── parser.py        # Tree-sitter code parser
│       ├── embedder.py      # CodeBERT embeddings
│       ├── vector_store.py  # FAISS vector index
│       ├── rag.py           # RAG pipeline
│       ├── graph.py         # Knowledge graph
│       ├── bug_detector.py  # Bug detection
│       └── architect.py     # Architecture diagrams
├── frontend/
│   └── app.py               # Streamlit UI
├── data/
│   ├── uploads/             # Uploaded repos
│   └── indexes/             # FAISS index + graphs
├── docker-compose.yml
└── README.md
\`\`\`