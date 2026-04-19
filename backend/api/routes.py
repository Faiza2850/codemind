from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from backend.core.parser import CodeParser
from backend.models.schemas import ParsedFileSchema, ParseRequest
import tempfile, shutil, os, zipfile, dataclasses

from backend.core.vector_store import VectorStore
from pydantic import BaseModel
from backend.core.rag import RAGPipeline
from fastapi.responses import StreamingResponse

from backend.core.graph import CodeGraph

from backend.core.bug_detector import BugDetector
from backend.core.architect import ArchitectureDiagramGenerator
import dataclasses

graph_engine = CodeGraph()

# Add this at the top with other imports
store = VectorStore()
bug_detector = BugDetector()
architect    = ArchitectureDiagramGenerator()

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

# Add with other top-level instances
rag = RAGPipeline()

class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    stream: bool = False

@router.post("/ask")
async def ask_question(req: AskRequest):
    """Ask a natural language question about the indexed codebase."""
    if req.stream:
        # Streaming response — tokens arrive live
        def generate():
            for token in rag.ask_stream(req.question, top_k=req.top_k):
                yield token
        return StreamingResponse(generate(), media_type="text/plain")

    # Standard response
    result = rag.ask(req.question, top_k=req.top_k)
    return result



@router.post("/graph/build")
async def build_graph(req: IndexRequest):
    from backend.core.parser import CodeParser
    parser = CodeParser()
    parsed = parser.parse_directory(req.directory)
    graph_engine.build(parsed)
    graph_engine.save()
    graph_engine.visualize()
    return graph_engine.summary()

@router.get("/graph/summary")
async def graph_summary():
    graph_engine.load()
    return graph_engine.summary()

@router.get("/graph/file")
async def file_dependencies(path: str):
    graph_engine.load()
    return graph_engine.get_file_dependencies(path)

@router.post("/analyze/bugs")
async def detect_bugs(req: IndexRequest):
    """Run bug detection on a directory."""
    from backend.core.parser import CodeParser
    parser = CodeParser()
    parsed = parser.parse_directory(req.directory)
    bugs   = bug_detector.analyze_files(parsed)
    summary = bug_detector.summary(bugs)
    return {
        "summary": summary,
        "bugs": [dataclasses.asdict(b) for b in bugs],
    }

@router.post("/analyze/architecture")
async def generate_architecture(req: IndexRequest):
    """Generate architecture diagram for a directory."""
    from backend.core.parser import CodeParser
    parser = CodeParser()
    parsed = parser.parse_directory(req.directory)
    layers = architect.generate(parsed)
    return {"layers": layers, "diagram_path": "data/indexes/architecture.png"}