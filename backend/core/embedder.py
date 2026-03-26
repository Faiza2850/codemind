import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from transformers import AutoTokenizer, AutoModel
from dataclasses import dataclass
from typing import Optional
import torch
import numpy as np

MODEL_NAME = "microsoft/codebert-base"
EMBED_DIM  = 768
MAX_TOKENS = 512

@dataclass
class CodeChunk:
    chunk_id:    str
    file_path:   str
    language:    str
    chunk_type:  str
    name:        str
    source_code: str
    start_line:  int
    end_line:    int
    docstring:   Optional[str]
    metadata:    dict


class CodeEmbedder:

    def __init__(self):
        print("⏳ Loading CodeBERT (cached)...")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model     = AutoModel.from_pretrained(MODEL_NAME)
        self.model.eval()
        print("✅ CodeBERT loaded")

    def _mean_pool(self, outputs, attention_mask) -> np.ndarray:
        token_embeddings = outputs.last_hidden_state
        mask   = attention_mask.unsqueeze(-1).float()
        summed = (token_embeddings * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        mean   = summed / counts
        return mean.detach().numpy().astype(np.float32)

    def embed(self, texts: list) -> np.ndarray:
        all_vecs = []
        for text in texts:
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=MAX_TOKENS,
                padding=True,
            )
            with torch.no_grad():
                outputs = self.model(**inputs)
            vec = self._mean_pool(outputs, inputs["attention_mask"])
            all_vecs.append(vec[0])
        return np.array(all_vecs, dtype=np.float32)

    def embed_single(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

    def chunk_text(self, chunk: CodeChunk) -> str:
        parts = []
        if chunk.chunk_type == "function":
            parts.append(f"Python function named {chunk.name}")
            if chunk.metadata.get("args"):
                parts.append(f"with parameters {', '.join(chunk.metadata['args'])}")
            if chunk.metadata.get("calls"):
                parts.append(f"which calls {', '.join(chunk.metadata['calls'][:3])}")
        elif chunk.chunk_type == "class":
            parts.append(f"Python class named {chunk.name}")
            if chunk.metadata.get("methods"):
                parts.append(f"with methods {', '.join(chunk.metadata['methods'][:5])}")
        elif chunk.chunk_type == "import_block":
            parts.append(f"imports and dependencies in file {chunk.file_path}")
        if chunk.docstring:
            parts.append(f"Description: {chunk.docstring}")
        parts.append(f"Located in {chunk.file_path}")
        parts.append(chunk.source_code)
        return "\n".join(parts)