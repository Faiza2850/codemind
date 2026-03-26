from backend.core.parser import CodeParser
from backend.core.graph import CodeGraph

parser = CodeParser()
files  = parser.parse_directory("backend")

graph  = CodeGraph()
graph.build(files)

# Summary
print("\n📊 Codebase summary:")
summary = graph.summary()
print(f"  Files:     {summary['total_files']}")
print(f"  Functions: {summary['total_functions']}")
print(f"  Imports:   {summary['import_edges']}")
print(f"  Calls:     {summary['call_edges']}")

print("\n🔗 Most connected files:")
for path, degree in summary["most_connected"]:
    print(f"  {degree:2d} connections — {path}")

print("\n🔥 Complexity hotspots:")
for h in summary["complexity_hotspots"]:
    print(f"  complexity={h['complexity']} — {h['function']}() in {h['file']} line {h['line']}")

print("\n📁 Dependencies of backend/core/parser.py:")
deps = graph.get_file_dependencies("backend/core/parser.py")
print(f"  imports:     {deps['imports']}")
print(f"  imported by: {deps['imported_by']}")

# Save graph + diagram
graph.save()
graph.visualize()
print("\n✅ Open data/indexes/graph.png to see the dependency diagram!")