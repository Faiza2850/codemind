import streamlit as st
import sys
import os
import tempfile
import zipfile
import shutil
import base64

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from backend.core.parser import CodeParser
from backend.core.vector_store import VectorStore
from backend.core.graph import CodeGraph
from backend.core.rag import RAGPipeline

from backend.core.bug_detector import BugDetector
from backend.core.architect import ArchitectureDiagramGenerator

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Codebase Intelligence Engine",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
.main-header {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(90deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.metric-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 1rem;
    border-left: 4px solid #667eea;
}
.source-card {
    background: #f0f4ff;
    border-radius: 8px;
    padding: 0.75rem;
    margin: 0.5rem 0;
    border-left: 3px solid #667eea;
    font-family: monospace;
    font-size: 0.85rem;
}
.answer-box {
    background: #fafafa;
    border-radius: 10px;
    padding: 1.5rem;
    border: 1px solid #e0e0e0;
    line-height: 1.7;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────
if "indexed"      not in st.session_state: st.session_state.indexed      = False
if "index_dir"    not in st.session_state: st.session_state.index_dir    = None
if "parsed_files" not in st.session_state: st.session_state.parsed_files = []
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "graph"        not in st.session_state: st.session_state.graph        = None
if "summary"      not in st.session_state: st.session_state.summary      = {}

# ── Cached resources ──────────────────────────────────────────
@st.cache_resource
def get_rag():
    return RAGPipeline()

@st.cache_resource
def get_parser():
    return CodeParser()

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 Codebase Intelligence")
    st.markdown("---")

    st.markdown("### 📂 Load a codebase")
    input_mode = st.radio("Input type", ["Upload ZIP", "Local path"], label_visibility="collapsed")

    repo_dir = None

    if input_mode == "Upload ZIP":
        uploaded = st.file_uploader("Upload repo as .zip", type=["zip"])
        if uploaded:
            extract_dir = tempfile.mkdtemp(prefix="codemind_")
            zip_path = os.path.join(extract_dir, "repo.zip")
            with open(zip_path, "wb") as f:
                f.write(uploaded.read())
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)
            repo_dir = extract_dir
            st.success(f"✅ Extracted to temp folder")

    else:
        local_path = st.text_input("Local directory path", value="backend")
        if local_path and os.path.isdir(local_path):
            repo_dir = local_path
            st.success(f"✅ Path found")
        elif local_path:
            st.error("Path not found")

    if repo_dir and st.button("⚡ Build Index", type="primary", use_container_width=True):
        with st.spinner("Parsing files..."):
            parser = get_parser()
            parsed = parser.parse_directory(repo_dir)
            st.session_state.parsed_files = parsed

        if not parsed:
            st.error("No supported files found (.py, .js, .ts)")
        else:
            with st.spinner(f"Embedding {len(parsed)} files..."):
                store = VectorStore()
                store.build_from_parsed_files(parsed)

            with st.spinner("Building knowledge graph..."):
                g = CodeGraph()
                g.build(parsed)
                g.save()
                g.visualize()
                st.session_state.graph   = g
                st.session_state.summary = g.summary()

            st.session_state.indexed   = True
            st.session_state.index_dir = repo_dir
            st.success(f"✅ Indexed {len(parsed)} files!")
            st.rerun()

    st.markdown("---")

    if st.session_state.indexed:
        s = st.session_state.summary
        st.markdown("### 📊 Index stats")
        st.metric("Files",     s.get("total_files", 0))
        st.metric("Functions", s.get("total_functions", 0))
        st.metric("Imports",   s.get("import_edges", 0))
        st.metric("Calls",     s.get("call_edges", 0))

    st.markdown("---")
    st.markdown("### 🔀 Navigate")
    page = st.radio(
        "Page",
        ["💬 Ask", "🗺️ Dependency Graph", "📊 Complexity", "🗂️ File Explorer", "🐛 Bug Detection", "🏗️ Architecture"],
        label_visibility="collapsed",
    )

# ── Main header ───────────────────────────────────────────────
st.markdown('<div class="main-header">🧠 Codebase Intelligence Engine</div>', unsafe_allow_html=True)

if not st.session_state.indexed:
    st.info("👈 Load a codebase from the sidebar and click **Build Index** to get started.")
    st.markdown("""
    **What this tool does:**
    - 🔍 Parses your entire codebase (Python, JS, TypeScript)
    - 🧠 Creates semantic embeddings with CodeBERT
    - 💬 Answers natural language questions about your code
    - 🗺️ Visualises file dependency graphs
    - 🔥 Identifies complexity hotspots
    """)
    st.stop()

# ══════════════════════════════════════════════════════════════
# PAGE: Ask
# ══════════════════════════════════════════════════════════════
if page == "💬 Ask":
    st.markdown("## 💬 Ask about your codebase")

    # Suggested questions
    st.markdown("**Quick questions:**")
    cols = st.columns(3)
    suggestions = [
        "How does authentication work?",
        "Where are routes defined?",
        "What are the most complex functions?",
        "How is the database layer structured?",
        "Find potential bugs",
        "Explain the main entry point",
    ]
    for i, suggestion in enumerate(suggestions):
        if cols[i % 3].button(suggestion, use_container_width=True):
            st.session_state.current_q = suggestion

    question = st.text_input(
        "Ask anything about the codebase",
        value=st.session_state.get("current_q", ""),
        placeholder="e.g. How does login work? Where is error handling?",
    )

    col1, col2 = st.columns([1, 5])
    ask_btn    = col1.button("Ask →", type="primary")
    top_k      = col2.slider("Chunks to retrieve", 3, 10, 5)

    if ask_btn and question:
        with st.spinner("🔍 Retrieving relevant code..."):
            rag    = get_rag()
            result = rag.ask(question, top_k=top_k)

        st.session_state.chat_history.append({"q": question, "r": result})
        st.session_state.current_q = ""

    # Display chat history
    for item in reversed(st.session_state.chat_history):
        st.markdown(f"**❓ {item['q']}**")
        st.markdown(f'<div class="answer-box">{item["r"]["answer"]}</div>', unsafe_allow_html=True)

        with st.expander(f"📁 Sources ({item['r']['chunks_used']} chunks)"):
            for s in item["r"]["sources"]:
                st.markdown(
                    f'<div class="source-card">'
                    f'📄 <b>{s["name"]}</b> ({s["type"]})<br>'
                    f'📂 {s["file"]}  •  lines {s["lines"]}  •  score {s["score"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("---")

# ══════════════════════════════════════════════════════════════
# PAGE: Dependency Graph
# ══════════════════════════════════════════════════════════════
elif page == "🗺️ Dependency Graph":
    st.markdown("## 🗺️ File dependency graph")

    graph_path = "data/indexes/graph.png"
    if os.path.exists(graph_path):
        st.image(graph_path, use_container_width=True)
    else:
        st.warning("Graph image not found. Rebuild the index.")

    if st.session_state.graph:
        g = st.session_state.graph
        st.markdown("### 🔗 Most connected files")
        for path, degree in g.get_most_connected_files(8):
            st.progress(min(degree / 20, 1.0), text=f"{os.path.basename(path)} — {degree} connections")

        st.markdown("### 📁 File dependency lookup")
        file_options = [pf.file_path for pf in st.session_state.parsed_files]
        selected = st.selectbox("Select a file", file_options)
        if selected:
            deps = g.get_file_dependencies(selected)
            col1, col2 = st.columns(2)
            col1.markdown("**Imports:**")
            for f in deps["imports"] or ["(none)"]:
                col1.code(f)
            col2.markdown("**Imported by:**")
            for f in deps["imported_by"] or ["(none)"]:
                col2.code(f)

# ══════════════════════════════════════════════════════════════
# PAGE: Complexity
# ══════════════════════════════════════════════════════════════
elif page == "📊 Complexity":
    st.markdown("## 🔥 Complexity hotspots")
    st.caption("Functions with high cyclomatic complexity are harder to test and more bug-prone.")

    if st.session_state.graph:
        hotspots = st.session_state.graph.get_complexity_hotspots(top_n=20)
        for h in hotspots:
            color = "🔴" if h["complexity"] > 8 else "🟡" if h["complexity"] > 4 else "🟢"
            st.markdown(
                f"{color} **{h['function']}()** — complexity {h['complexity']}  \n"
                f"&nbsp;&nbsp;&nbsp;&nbsp;`{h['file']}` line {h['line']}"
            )
            st.progress(min(h["complexity"] / 15, 1.0))

# ══════════════════════════════════════════════════════════════
# PAGE: File Explorer
# ══════════════════════════════════════════════════════════════
elif page == "🗂️ File Explorer":
    st.markdown("## 🗂️ File explorer")

    if st.session_state.parsed_files:
        for pf in st.session_state.parsed_files:
            with st.expander(f"📄 {pf.file_path}  ({pf.total_lines} lines, {len(pf.functions)} functions)"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Functions", len(pf.functions))
                col2.metric("Classes",   len(pf.classes))
                col3.metric("Complexity", pf.complexity_score)

                if pf.functions:
                    st.markdown("**Functions:**")
                    for fn in pf.functions:
                        st.markdown(
                            f"- `{fn.name}({', '.join(fn.args)})` "
                            f"line {fn.start_line} — complexity {fn.complexity}"
                        )

                if pf.classes:
                    st.markdown("**Classes:**")
                    for cls in pf.classes:
                        st.markdown(f"- `{cls.name}` — methods: {', '.join(cls.methods)}")

                if pf.imports:
                    st.markdown("**Imports:**")
                    for imp in pf.imports[:5]:
                        st.code(imp, language="python")
# ══════════════════════════════════════════════════════════════
# PAGE: Bug Detection
# ══════════════════════════════════════════════════════════════
elif page == "🐛 Bug Detection":
    st.markdown("## 🐛 Bug Detection")

    if st.button("🔍 Run Analysis", type="primary"):
        with st.spinner("Analyzing code for bugs..."):
            detector = BugDetector()
            bugs     = detector.analyze_files(st.session_state.parsed_files)
            st.session_state.bugs    = bugs
            st.session_state.bug_sum = detector.summary(bugs)

    if "bugs" in st.session_state:
        s = st.session_state.bug_sum
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Issues", s["total"])
        col2.metric("🔴 High",      s["high"])
        col3.metric("🟡 Medium",    s["medium"])
        col4.metric("🟢 Low",       s["low"])

        st.markdown("---")
        for bug in st.session_state.bugs:
            icon = "🔴" if bug.severity == "high" else "🟡" if bug.severity == "medium" else "🟢"
            with st.expander(f"{icon} {bug.message[:80]}..."):
                st.markdown(f"**File:** `{bug.file_path}` line {bug.line}")
                st.markdown(f"**Category:** {bug.category}")
                st.markdown(f"**Severity:** {bug.severity}")
                if bug.code_snippet:
                    st.code(bug.code_snippet, language="python")

# ══════════════════════════════════════════════════════════════
# PAGE: Architecture
# ══════════════════════════════════════════════════════════════
elif page == "🏗️ Architecture":
    st.markdown("## 🏗️ Architecture Diagram")

    if st.button("🔨 Generate Diagram", type="primary"):
        with st.spinner("Generating architecture diagram..."):
            arch   = ArchitectureDiagramGenerator()
            layers = arch.generate(st.session_state.parsed_files)
            st.session_state.arch_layers = layers

    diag_path = "data/indexes/architecture.png"
    if os.path.exists(diag_path):
        st.image(diag_path, use_container_width=True)

    if "arch_layers" in st.session_state:
        st.markdown("### 📐 Layer breakdown")
        for layer, files in st.session_state.arch_layers.items():
            color = {"api": "🔵", "core": "🟣", "models": "🩷",
                     "data": "🩵", "utils": "🟢", "other": "⚫"}.get(layer, "⚪")
            st.markdown(f"{color} **{layer.upper()}**")
            for f in files:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;`{f}`")