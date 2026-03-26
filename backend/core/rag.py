import os
import json
import httpx
from backend.core.vector_store import VectorStore

OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL    = "llama3.2"

SYSTEM_PROMPT = """You are an expert software engineer and codebase analyst.
You are given relevant code chunks retrieved from a codebase, along with a user question.
Your job is to:
1. Carefully read the provided code chunks
2. Answer the user question clearly and accurately
3. Reference specific file names and line numbers when relevant
4. Keep explanations concise but complete
Always ground your answer in the actual code provided."""


def _build_prompt(question: str, chunks: list) -> str:
    parts = ["Here are the most relevant code chunks from the codebase:\n"]
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"--- Chunk {i} ---\n"
            f"File: {chunk['file_path']}\n"
            f"Type: {chunk['chunk_type']} — {chunk['name']}\n"
            f"Lines: {chunk['start_line']}–{chunk['end_line']}\n"
            f"```{chunk['language']}\n{chunk['source_code']}\n```\n"
        )
    parts.append(f"\nUser question: {question}")
    return "\n".join(parts)


class RAGPipeline:

    def __init__(self):
        self.store = VectorStore()
        self._index_loaded = False

    def _ensure_index(self):
        if not self._index_loaded:
            self.store.load()
            self._index_loaded = True

    def ask(self, question: str, top_k: int = 5) -> dict:
        self._ensure_index()
        chunks = self.store.search(question, top_k=top_k)

        if not chunks:
            return {"question": question, "answer": "No relevant code found.", "sources": []}

        try:
            response = httpx.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": _build_prompt(question, chunks)},
                    ],
                },
                timeout=180,
            )
            response.raise_for_status()
            answer = response.json()["message"]["content"]

        except httpx.ConnectError:
            answer = "❌ Ollama not running. Run: ollama serve"
        except KeyError as e:
            answer = f"❌ Unexpected response format: {response.text[:200]}"
        except Exception as e:
            answer = f"❌ Error: {str(e)}"

        return {
            "question":    question,
            "answer":      answer,
            "sources":     [{"file": c["file_path"], "name": c["name"],
                             "type": c["chunk_type"],
                             "lines": f"{c['start_line']}–{c['end_line']}",
                             "score": c["score"]} for c in chunks],
            "model":       OLLAMA_MODEL,
            "chunks_used": len(chunks),
        }

    def ask_stream(self, question: str, top_k: int = 5):
        self._ensure_index()
        chunks = self.store.search(question, top_k=top_k)

        try:
            with httpx.stream(
                "POST", OLLAMA_CHAT_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "stream": True,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": _build_prompt(question, chunks)},
                    ],
                },
                timeout=180,
            ) as r:
                for line in r.iter_lines():
                    if line:
                        data = json.loads(line)
                        if not data.get("done"):
                            yield data.get("message", {}).get("content", "")
        except httpx.ConnectError:
            yield "❌ Ollama not running. Run: ollama serve"