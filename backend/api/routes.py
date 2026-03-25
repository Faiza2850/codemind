from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from backend.core.parser import CodeParser
from backend.models.schemas import ParsedFileSchema, ParseRequest
import tempfile, shutil, os, zipfile, dataclasses

from backend.core.vector_store import VectorStore
from pydantic import BaseModel

# Add this at the top with other imports
store = VectorStore()

class IndexRequest(BaseModel):
    directory: str

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

@router.post("/index/build")
async def build_index(req: IndexRequest):
    """Parse a directory and build the FAISS index."""
    from backend.core.parser import CodeParser
    parser = CodeParser()
    parsed = parser.parse_directory(req.directory)
    store.build_from_parsed_files(parsed)
    return {"status": "ok", "files_indexed": len(parsed)}

@router.post("/index/search")
async def search_code(req: SearchRequest):
    """Search the index with a natural language query."""
    try:
        store.load()
    except FileNotFoundError:
        return {"error": "No index found. Build index first via /index/build"}
    results = store.search(req.query, top_k=req.top_k)
    return {"query": req.query, "results": results}

router = APIRouter(prefix="/api/v1", tags=["parser"])
parser = CodeParser()

def _to_dict(obj):
    """Convert dataclass recursively to dict for JSON response."""
    if dataclasses.is_dataclass(obj):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    return obj

@router.post("/parse/upload")
async def parse_uploaded_zip(file: UploadFile = File(...)):
    """Upload a .zip of a repo and get structured parse result back."""
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files supported")

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "repo.zip")
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        extract_dir = os.path.join(tmpdir, "repo")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)

        parsed_files = parser.parse_directory(extract_dir)

    return JSONResponse(content={
        "total_files": len(parsed_files),
        "files": [_to_dict(pf) for pf in parsed_files]
    })

@router.post("/parse/directory")
async def parse_local_directory(req: ParseRequest):
    """Parse a local directory path (for development/testing)."""
    if not req.directory or not os.path.isdir(req.directory):
        raise HTTPException(status_code=400, detail="Invalid directory path")

    parsed_files = parser.parse_directory(req.directory)
    return {
        "total_files": len(parsed_files),
        "files": [_to_dict(pf) for pf in parsed_files]
    }