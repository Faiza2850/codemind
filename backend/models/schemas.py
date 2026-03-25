from pydantic import BaseModel
from typing import Optional

class FunctionSchema(BaseModel):
    name: str
    start_line: int
    end_line: int
    args: list[str]
    docstring: Optional[str]
    calls: list[str]
    complexity: int
    source_code: str

class ClassSchema(BaseModel):
    name: str
    start_line: int
    end_line: int
    methods: list[str]
    docstring: Optional[str]
    base_classes: list[str]

class ParsedFileSchema(BaseModel):
    file_path: str
    language: str
    imports: list[str]
    classes: list[ClassSchema]
    functions: list[FunctionSchema]
    total_lines: int

class ParseRequest(BaseModel):
    github_url: Optional[str] = None   # Phase 6 — GitHub ingestion
    directory: Optional[str] = None    # local path for testing now