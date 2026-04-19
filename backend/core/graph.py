import os
import json
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")   # no display needed — saves to file

GRAPH_FILE = "data/indexes/graph.json"


class CodeGraph:
    """
    Builds a directed graph of file and function relationships.
    Nodes  = files and functions
    Edges  = import dependencies + function calls
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    # ── Build ─────────────────────────────────────────────────

    def build(self, parsed_files: list):
        """Build graph from list of ParsedFile objects."""
        self.graph.clear()

        # Map: module name → file path (for resolving imports)
        module_map = self._build_module_map(parsed_files)

        for pf in parsed_files:
            # Add file node
            self.graph.add_node(
                pf.file_path,
                node_type = "file",
                language  = pf.language,
                functions = [f.name for f in pf.functions],
                classes   = [c.name for c in pf.classes],
                lines     = pf.total_lines,
                complexity= pf.complexity_score,
            )

            # Add function nodes
            for fn in pf.functions:
                fn_id = f"{pf.file_path}::{fn.name}"
                self.graph.add_node(
                    fn_id,
                    node_type  = "function",
                    file_path  = pf.file_path,
                    start_line = fn.start_line,
                    end_line   = fn.end_line,
                    complexity = fn.complexity,
                    args       = fn.args,
                )
                # file → function edge
                self.graph.add_edge(
                    pf.file_path, fn_id,
                    edge_type="contains"
                )

            # Add import edges (file → file)
            for imp in pf.imports:
                target = self._resolve_import(imp, pf.file_path, module_map)
                if target:
                    self.graph.add_edge(
                        pf.file_path, target,
                        edge_type="imports",
                        import_statement=imp,
                    )

            # Add function call edges
            for fn in pf.functions:
                fn_id = f"{pf.file_path}::{fn.name}"
                for called in fn.calls:
                    # look for called function in same file first
                    local_id = f"{pf.file_path}::{called}"
                    if self.graph.has_node(local_id):
                        self.graph.add_edge(
                            fn_id, local_id,
                            edge_type="calls"
                        )

        print(f"✅ Graph built: {self.graph.number_of_nodes()} nodes, "
              f"{self.graph.number_of_edges()} edges")

    # ── Query ─────────────────────────────────────────────────

    def get_file_dependencies(self, file_path: str) -> dict:
        """What files does this file import? What imports it?"""
        imports = [
            t for _, t, d in self.graph.out_edges(file_path, data=True)
            if d.get("edge_type") == "imports"
        ]
        imported_by = [
            s for s, _, d in self.graph.in_edges(file_path, data=True)
            if d.get("edge_type") == "imports"
        ]
        return {"imports": imports, "imported_by": imported_by}

    def get_function_calls(self, file_path: str, fn_name: str) -> dict:
        """What does this function call? What calls it?"""
        fn_id = f"{file_path}::{fn_name}"
        if not self.graph.has_node(fn_id):
            return {"calls": [], "called_by": []}

        calls = [
            t.split("::")[-1]
            for _, t, d in self.graph.out_edges(fn_id, data=True)
            if d.get("edge_type") == "calls"
        ]
        called_by = [
            s.split("::")[-1]
            for s, _, d in self.graph.in_edges(fn_id, data=True)
            if d.get("edge_type") == "calls"
        ]
        return {"calls": calls, "called_by": called_by}

    def get_most_connected_files(self, top_n: int = 5) -> list:
        """Files with most connections — usually core/central files."""
        file_nodes = [n for n, d in self.graph.nodes(data=True)
                      if d.get("node_type") == "file"]
        scores = [
            (n, self.graph.degree(n)) for n in file_nodes
        ]
        return sorted(scores, key=lambda x: x[1], reverse=True)[:top_n]

    def get_complexity_hotspots(self, top_n: int = 5) -> list:
        """Functions with highest complexity — likely need review."""
        fn_nodes = [
            (n, d) for n, d in self.graph.nodes(data=True)
            if d.get("node_type") == "function"
        ]
        scored = [
            {
                "function": n.split("::")[-1],
                "file":     d.get("file_path"),
                "line":     d.get("start_line"),
                "complexity": d.get("complexity", 1),
            }
            for n, d in fn_nodes
        ]
        return sorted(scored, key=lambda x: x["complexity"], reverse=True)[:top_n]

    def summary(self) -> dict:
        """High-level stats about the codebase graph."""
        file_nodes = [n for n, d in self.graph.nodes(data=True)
                      if d.get("node_type") == "file"]
        fn_nodes   = [n for n, d in self.graph.nodes(data=True)
                      if d.get("node_type") == "function"]
        import_edges = [(s, t) for s, t, d in self.graph.edges(data=True)
                        if d.get("edge_type") == "imports"]
        call_edges   = [(s, t) for s, t, d in self.graph.edges(data=True)
                        if d.get("edge_type") == "calls"]

        return {
            "total_files":     len(file_nodes),
            "total_functions": len(fn_nodes),
            "import_edges":    len(import_edges),
            "call_edges":      len(call_edges),
            "most_connected":  self.get_most_connected_files(3),
            "complexity_hotspots": self.get_complexity_hotspots(3),
        }

    # ── Visualize ─────────────────────────────────────────────

    def visualize(self, output_path: str = "data/indexes/graph.png"):
        """Save a visual diagram of file-level dependencies."""
        # Only show file nodes for clarity
        file_nodes = [n for n, d in self.graph.nodes(data=True)
                      if d.get("node_type") == "file"]
        subgraph = self.graph.subgraph(file_nodes)

        plt.figure(figsize=(14, 10))
        pos = nx.spring_layout(subgraph, seed=42, k=2)

        # Color nodes by number of connections
        degrees = dict(subgraph.degree())
        colors  = [degrees.get(n, 0) for n in subgraph.nodes()]

        nx.draw_networkx_nodes(
            subgraph, pos,
            node_color=colors, cmap=plt.cm.Blues,
            node_size=1500, alpha=0.9,
        )
        nx.draw_networkx_edges(
            subgraph, pos,
            edge_color="#888", arrows=True,
            arrowsize=20, width=1.5, alpha=0.7,
        )
        # Short labels — just filename not full path
        labels = {n: os.path.basename(n) for n in subgraph.nodes()}
        nx.draw_networkx_labels(subgraph, pos, labels, font_size=9)

        plt.title("Codebase dependency graph", fontsize=14)
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"📊 Graph saved → {output_path}")

    # ── Persist ───────────────────────────────────────────────

    def save(self):
        os.makedirs("data/indexes", exist_ok=True)
        data = nx.node_link_data(self.graph)
        with open(GRAPH_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"💾 Graph saved → {GRAPH_FILE}")

    def load(self):
        with open(GRAPH_FILE) as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data)
        print(f"✅ Graph loaded: {self.graph.number_of_nodes()} nodes")

    # ── Helpers ───────────────────────────────────────────────

    def _build_module_map(self, parsed_files: list) -> dict:
        """Map module names to file paths for import resolution."""
        module_map = {}
        for pf in parsed_files:
            # e.g. backend/core/parser.py → backend.core.parser
            module = pf.file_path.replace("/", ".").replace("\\", ".").rstrip(".py")
            module_map[module] = pf.file_path
            # also map just the filename stem
            stem = os.path.splitext(os.path.basename(pf.file_path))[0]
            module_map[stem] = pf.file_path
        return module_map

    def _resolve_import(self, imp: str, source_file: str, module_map: dict) -> str:
        """Try to resolve an import statement to a file path."""
        # e.g. "from backend.core.parser import CodeParser"
        parts = imp.replace("from ", "").replace("import ", "").strip().split()
        for part in parts:
            part = part.rstrip(",")
            if part in module_map:
                target = module_map[part]
                if target != source_file:
                    return target
            # try submodules: backend.core.parser → parser
            for key in module_map:
                if part.endswith(key) or key.endswith(part):
                    target = module_map[key]
                    if target != source_file:
                        return target
        return None