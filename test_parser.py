from backend.core.parser import CodeParser

parser = CodeParser()
result = parser.parse_file("backend/main.py")

print(f"\n📄 File: {result.file_path}")
print(f"🌐 Language: {result.language}")
print(f"📦 Imports ({len(result.imports)}):")
for imp in result.imports:
    print(f"   {imp}")

print(f"\n🏛️  Classes ({len(result.classes)}):")
for cls in result.classes:
    print(f"   {cls.name}  (line {cls.start_line}–{cls.end_line})")
    print(f"   methods: {cls.methods}")

print(f"\n⚙️  Functions ({len(result.functions)}):")
for fn in result.functions:
    print(f"   {fn.name}()  args={fn.args}  line {fn.start_line}  complexity={fn.complexity}")
    if fn.docstring:
        print(f"   doc: {fn.docstring[:60]}")
    if fn.calls:
        print(f"   calls: {fn.calls}")

print(f"\n📊 Complexity score: {result.complexity_score}")
print(f"📏 Total lines: {result.total_lines}")