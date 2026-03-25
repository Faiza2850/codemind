from transformers import AutoTokenizer, AutoModel
from dataclasses import dataclass
from typing import Optional
import torch
import numpy as np
import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"

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
        """
        Mean pooling over all token embeddings (not just CLS).
        This gives far better semantic similarity scores.
        """
        token_embeddings = outputs.last_hidden_state          # (batch, seq, 768)
        mask = attention_mask.unsqueeze(-1).float()           # (batch, seq, 1)
        summed = (token_embeddings * mask).sum(dim=1)         # (batch, 768)
        counts = mask.sum(dim=1).clamp(min=1e-9)              # (batch, 1)
        mean   = summed / counts                               # (batch, 768)
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
        parts = [
            f"# {chunk.language} {chunk.chunk_type}: {chunk.name}",
            f"# file: {chunk.file_path}",
        ]
        if chunk.docstring:
            parts.append(f"# description: {chunk.docstring}")
        if chunk.metadata.get("args"):
            parts.append(f"# arguments: {', '.join(chunk.metadata['args'])}")
        if chunk.metadata.get("calls"):
            parts.append(f"# calls: {', '.join(chunk.metadata['calls'][:5])}")
        parts.append(chunk.source_code)
        return "\n".join(parts)