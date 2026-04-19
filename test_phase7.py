import os
from backend.core.parser import CodeParser
from backend.core.bug_detector import BugDetector
from backend.core.architect import ArchitectureDiagramGenerator
import os

parser   = CodeParser()
files    = parser.parse_directory("backend")

print("=" * 60)
print("🐛 BUG DETECTION")
print("=" * 60)

detector = BugDetector()
bugs     = detector.analyze_files(files)
summary  = detector.summary(bugs)

print(f"\n📊 Summary: {summary['total']} issues found")
print(f"   🔴 High:   {summary['high']}")
print(f"   🟡 Medium: {summary['medium']}")
print(f"   🟢 Low:    {summary['low']}")

print(f"\n🔍 Issues:")
for bug in bugs:
    icon = "🔴" if bug.severity == "high" else "🟡" if bug.severity == "medium" else "🟢"
    print(f"\n{icon} [{bug.severity.upper()}] {bug.category}")
    print(f"   📄 {bug.file_path} line {bug.line}")
    print(f"   💬 {bug.message}")
    if bug.code_snippet:
        print(f"   📝 {bug.code_snippet}")

print("\n" + "=" * 60)
print("🏗️  ARCHITECTURE DIAGRAM")
print("=" * 60)

architect = ArchitectureDiagramGenerator()
layers    = architect.generate(files)

print("\n📐 Layer assignments:")
for layer, file_list in layers.items():
    print(f"   {layer.upper():10s} → {[os.path.basename(f) for f in file_list]}")

print("\n✅ Open data/indexes/architecture.png to see the diagram!")
