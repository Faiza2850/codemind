from tree_sitter import Language, Parser
import tree_sitter_python as tspython
from dataclasses import dataclass
from typing import Optional
import os

try:
    import tree_sitter_javascript as tsjavascript
    HAS_JS = True
except ImportError:
    HAS_JS = False

try:
    import tree_sitter_typescript as tstypescript
    HAS_TS = True
except ImportError:
    HAS_TS = False

@dataclass
class FunctionInfo:
    name: str
    start_line: int
    end_line: int
    args: list
    docstring: Optional[str]
    calls: list
    complexity: int
    source_code: str

@dataclass
class ClassInfo:
    name: str
    start_line: int
    end_line: int
    methods: list
    docstring: Optional[str]
    base_classes: list

@dataclass
class ParsedFile:
    file_path: str
    language: str
    imports: list
    classes: list
    functions: list
    total_lines: int
    complexity_score: float

LANGUAGE_MAP = {
    ".py":  "python",
    ".js":  "javascript",
    ".ts":  "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
}

INVALID_NAME_CHARS = {"[", "]", "(", ")", ":", " ", "-", ">"}

def _make_parser(ext: str) -> Optional[Parser]:
    lang_name = LANGUAGE_MAP.get(ext)
    if not lang_name:
        return None
    if lang_name == "python":
        capsule = tspython.language()
    elif lang_name == "javascript":
        if not HAS_JS:
            return None
        capsule = tsjavascript.language()
    elif lang_name == "typescript":
        if not HAS_TS:
            return None
        try:
            capsule = tstypescript.language_typescript()
        except AttributeError:
            capsule = tstypescript.language()
    else:
        return None
    lang = Language(capsule, lang_name)
    p = Parser()
    p.set_language(lang)
    return p


class CodeParser:

    def parse_file(self, file_path: str) -> Optional[ParsedFile]:
        ext = os.path.splitext(file_path)[1].lower()
        try:
            parser = _make_parser(ext)
        except Exception as e:
            print(f"  [error] building parser for {ext}: {e}")
            return None
        if not parser:
            return None
        with open(file_path, "rb") as f:
            source = f.read()
        try:
            tree = parser.parse(source)
        except Exception as e:
            print(f"  [error] parsing {file_path}: {e}")
            return None
        lang_name = LANGUAGE_MAP[ext]
        source_str = source.decode("utf-8", errors="replace")
        lines = source_str.splitlines()
        functions = self._extract_functions(tree.root_node, source_str)
        avg = sum(f.complexity for f in functions) / len(functions) if functions else 0.0
        return ParsedFile(
            file_path=file_path,
            language=lang_name,
            imports=self._extract_imports(tree.root_node, source_str, lang_name),
            classes=self._extract_classes(tree.root_node, source_str),
            functions=functions,
            total_lines=len(lines),
            complexity_score=round(avg, 2),
        )

    def _extract_imports(self, root, source: str, lang: str) -> list:
        imports = []
        types = {
            "python":     {"import_statement", "import_from_statement"},
            "javascript": {"import_declaration"},
            "typescript": {"import_declaration"},
        }.get(lang, set())
        def walk(node):
            if node.type in types:
                imports.append(source[node.start_byte:node.end_byte].strip())
            for c in node.children:
                walk(c)
        walk(root)
        return imports

    def _extract_classes(self, root, source: str) -> list:
        classes = []
        def walk(node):
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                name = source[name_node.start_byte:name_node.end_byte] if name_node else "unknown"
                bases = []
                sup = node.child_by_field_name("superclasses")
                if sup:
                    for c in sup.children:
                        if c.type == "identifier":
                            bases.append(source[c.start_byte:c.end_byte])
                methods = []
                body = node.child_by_field_name("body")
                if body:
                    for c in body.children:
                        if c.type == "function_definition":
                            mn = c.child_by_field_name("name")
                            if mn:
                                methods.append(source[mn.start_byte:mn.end_byte])
                classes.append(ClassInfo(
                    name=name,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    methods=methods,
                    docstring=self._get_docstring(node, source),
                    base_classes=bases,
                ))
            for c in node.children:
                walk(c)
        walk(root)
        return classes

    def _extract_functions(self, root, source: str) -> list:
        functions = []
        def walk(node):
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    for c in node.children:
                        walk(c)
                    return
                name = source[name_node.start_byte:name_node.end_byte]
                if not name or any(ch in name for ch in INVALID_NAME_CHARS):
                    for c in node.children:
                        walk(c)
                    return
                args = []
                params = node.child_by_field_name("parameters")
                if params:
                    for c in params.children:
                        if c.type == "identifier":
                            args.append(source[c.start_byte:c.end_byte])
                functions.append(FunctionInfo(
                    name=name,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    args=args,
                    docstring=self._get_docstring(node, source),
                    calls=self._get_calls(node, source),
                    complexity=self._get_complexity(node),
                    source_code=source[node.start_byte:node.end_byte],
                ))
            for c in node.children:
                walk(c)
        walk(root)
        return functions

    def _get_docstring(self, node, source: str) -> Optional[str]:
        body = node.child_by_field_name("body")
        if not body:
            return None
        for child in body.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        raw = source[sub.start_byte:sub.end_byte]
                        return raw.strip('"""').strip("'''").strip('"').strip("'").strip()
        return None

    def _get_calls(self, fn_node, source: str) -> list:
        calls = []
        def walk(node):
            if node.type == "call":
                fn = node.child_by_field_name("function")
                if fn:
                    calls.append(source[fn.start_byte:fn.end_byte])
            for c in node.children:
                walk(c)
        walk(fn_node)
        return list(set(calls))

    def _get_complexity(self, fn_node) -> int:
        branch_types = {
            "if_statement", "elif_clause", "for_statement",
            "while_statement", "try_statement", "except_clause",
            "boolean_operator", "with_statement",
        }
        count = 1
        def walk(node):
            nonlocal count
            if node.type in branch_types:
                count += 1
            for c in node.children:
                walk(c)
        walk(fn_node)
        return count

    def parse_directory(self, dir_path: str) -> list:
        results = []
        skip = {".git", "__pycache__", "node_modules", ".venv", "venv"}
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in skip]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in LANGUAGE_MAP:
                    parsed = self.parse_file(os.path.join(root, fname))
                    if parsed:
                        results.append(parsed)
        return results
