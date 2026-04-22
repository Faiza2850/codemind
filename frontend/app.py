import streamlit as st
import sys
import os
import tempfile
import zipfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from backend.core.parser import CodeParser
from backend.core.vector_store import VectorStore
from backend.core.graph import CodeGraph
from backend.core.rag import RAGPipeline
from backend.core.bug_detector import BugDetector
from backend.core.architect import ArchitectureDiagramGenerator
from backend.core.github_ingestion import GitHubIngestion, parse_github_url

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="CODEMIND - Codebase Intelligence Engine",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main-header {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(90deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.sub-header {
    color: #888;
    font-size: 1rem;
    margin-bottom: 2rem;
}
.source-card {
    background: #1e1e2e;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin: 0.4rem 0;
    border-left: 3px solid #667eea;
    font-family: monospace;
    font-size: 0.82rem;
}
.answer-box {
    background: #1a1a2e;
    border-radius: 10px;
    padding: 1.5rem;
    border: 1px solid #333;
    line-height: 1.8;
    font-size: 0.95rem;
}
.stat-box {
    background: #1e1e2e;
    border-radius: 8px;
    padding: 0.6rem;
    text-align: center;
    border: 1px solid #333;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────
defaults = {
    "indexed": False, "index_dir": None, "parsed_files": [],
    "chat_history": [], "graph": None, "summary": {},
    "repo_name": "", "bugs": [], "bug_sum": {}, "arch_layers": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Cached resources ──────────────────────────────────────────
@st.cache_resource
def get_rag():
    return RAGPipeline()

@st.cache_resource
def get_parser():
    return CodeParser()

@st.cache_resource
def get_ingestion():
    return GitHubIngestion()

# ── Indexing function ─────────────────────────────────────────
def run_indexing(repo_dir: str, repo_name: str):
    """Parse, embed, and graph a directory. Updates session state."""
    status = st.empty()

    status.info("🔍 Parsing source files...")
    parser = get_parser()
    parsed = parser.parse_directory(repo_dir)

    if not parsed:
        st.error("❌ No supported files found (.py, .js, .ts). Check the repo.")
        return False

    status.info(f"🧠 Embedding {len(parsed)} files with CodeBERT...")
    store = VectorStore()
    store.build_from_parsed_files(parsed)

    status.info("🗺️ Building knowledge graph...")
    g = CodeGraph()
    g.build(parsed)
    g.save()
    g.visualize()

    status.info("🏗️ Generating architecture diagram...")
    arch = ArchitectureDiagramGenerator()
    layers = arch.generate(parsed)

    status.info("🐛 Running bug detection...")
    detector = BugDetector()
    bugs = detector.analyze_files(parsed)

    # Save everything to session state
    st.session_state.parsed_files = parsed
    st.session_state.graph        = g
    st.session_state.summary      = g.summary()
    st.session_state.indexed      = True
    st.session_state.index_dir    = repo_dir
    st.session_state.repo_name    = repo_name
    st.session_state.bugs         = bugs
    st.session_state.bug_sum      = detector.summary(bugs)
    st.session_state.arch_layers  = layers
    st.session_state.chat_history = []

    status.success(f"✅ Indexed {len(parsed)} files from **{repo_name}**!")
    return True

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🧠 CODEMIND - Codebase Intelligence")
    st.caption("Understand any codebase instantly")
    st.divider()

    st.markdown("### 📂 Load a codebase")

    tab_gh, tab_zip, tab_local = st.tabs(["🔗 GitHub", "📦 ZIP", "📁 Local"])

    # ── GitHub URL tab ────────────────────────────────────────
    with tab_gh:
        github_url = st.text_input(
            "GitHub repository URL",
            placeholder="https://github.com/owner/repo",
            label_visibility="collapsed",
        )
        if github_url:
            parsed_url = parse_github_url(github_url)
            if parsed_url:
                st.success(f"✅ {parsed_url[0]}/{parsed_url[1]}")
            else:
                st.error("Invalid GitHub URL")

        if st.button("⚡ Clone & Analyze", type="primary",
                     use_container_width=True, key="btn_github"):
            if not github_url:
                st.error("Please enter a GitHub URL")
            elif not parse_github_url(github_url):
                st.error("Invalid GitHub URL format")
            else:
                with st.spinner("Cloning repository..."):
                    try:
                        ingestion = get_ingestion()
                        msgs = []
                        repo_info = ingestion.clone(
                            github_url,
                            progress_callback=lambda m: msgs.append(m)
                        )
                        for m in msgs:
                            st.caption(m)
                        stats = ingestion.get_repo_stats(repo_info.local_path)
                        st.caption(f"Found {stats['total_files']} supported files")
                    except ValueError as e:
                        st.error(str(e))
                        st.stop()

                run_indexing(
                    repo_info.local_path,
                    f"{repo_info.owner}/{repo_info.repo_name}"
                )
                st.rerun()

    # ── ZIP upload tab ────────────────────────────────────────
    with tab_zip:
        uploaded = st.file_uploader(
            "Upload repo as ZIP",
            type=["zip"],
            label_visibility="collapsed",
        )
        if uploaded:
            st.success(f"✅ {uploaded.name}")

        if st.button("⚡ Extract & Analyze", type="primary",
                     use_container_width=True, key="btn_zip"):
            if not uploaded:
                st.error("Please upload a ZIP file first")
            else:
                extract_dir = tempfile.mkdtemp(prefix="codemind_")
                zip_path = os.path.join(extract_dir, "repo.zip")
                with open(zip_path, "wb") as f:
                    f.write(uploaded.read())
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(extract_dir)
                repo_name = uploaded.name.replace(".zip", "")
                run_indexing(extract_dir, repo_name)
                st.rerun()

    # ── Local path tab ────────────────────────────────────────
    with tab_local:
        local_path = st.text_input(
            "Local directory path",
            value="backend",
            label_visibility="collapsed",
        )
        if local_path:
            if os.path.isdir(local_path):
                st.success("✅ Path found")
            else:
                st.error("Path not found")

        if st.button("⚡ Analyze Local", type="primary",
                     use_container_width=True, key="btn_local"):
            if not os.path.isdir(local_path):
                st.error("Invalid path")
            else:
                run_indexing(local_path, local_path)
                st.rerun()

    # ── Stats ─────────────────────────────────────────────────
    if st.session_state.indexed:
        st.divider()
        s = st.session_state.summary
        st.markdown(f"### 📊 `{st.session_state.repo_name}`")
        c1, c2 = st.columns(2)
        c1.metric("Files",     s.get("total_files", 0))
        c2.metric("Functions", s.get("total_functions", 0))
        c1.metric("Imports",   s.get("import_edges", 0))
        c2.metric("Calls",     s.get("call_edges", 0))

        b = st.session_state.bug_sum
        if b:
            st.markdown("**Bug summary:**")
            bc1, bc2, bc3 = st.columns(3)
            bc1.markdown(f"🔴 **{b.get('high',0)}**")
            bc2.markdown(f"🟡 **{b.get('medium',0)}**")
            bc3.markdown(f"🟢 **{b.get('low',0)}**")

    st.divider()
    st.markdown("### 🔀 Navigate")
    page = st.radio(
        "Page",
        ["💬 Ask", "🗺️ Dependency Graph", "📊 Complexity",
         "🗂️ File Explorer", "🐛 Bug Detection", "🏗️ Architecture"],
        label_visibility="collapsed",
    )

# ══════════════════════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════════════════════
st.markdown('<div class="main-header">🧠 Codebase Intelligence Engine</div>',
            unsafe_allow_html=True)

if st.session_state.indexed:
    st.markdown(
        f'<div class="sub-header">Analyzing: <b>{st.session_state.repo_name}</b> '
        f'— {st.session_state.summary.get("total_files",0)} files · '
        f'{st.session_state.summary.get("total_functions",0)} functions</div>',
        unsafe_allow_html=True,
    )

if not st.session_state.indexed:
    st.markdown('<div class="sub-header">Paste a GitHub URL, upload a ZIP, or point to a local folder</div>',
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.info("🔗 **GitHub URL**\nPaste any public repo link")
    col2.info("📦 **ZIP Upload**\nUpload your project as a zip")
    col3.info("📁 **Local Path**\nPoint to a folder on disk")

    st.markdown("### What you'll get:")
    c1, c2, c3 = st.columns(3)
    c1.success("💬 Ask questions in plain English about any part of the code")
    c2.success("🗺️ Visual dependency graph showing how files connect")
    c3.success("🐛 Bug detection with severity ratings and code snippets")
    c1.success("📊 Complexity hotspots — which functions need refactoring")
    c2.success("🏗️ Auto-generated architecture layer diagram")
    c3.success("🗂️ Full file explorer with functions and classes")
    st.stop()

# ══════════════════════════════════════════════════════════════
# PAGE: Ask
# ══════════════════════════════════════════════════════════════
if page == "💬 Ask":
    st.markdown("## 💬 Ask about the codebase")

    st.markdown("**Quick questions:**")
    suggestions = [
        "How does authentication work?",
        "Where are routes defined?",
        "What are the most complex functions?",
        "How is the database layer structured?",
        "Find potential bugs",
        "Explain the main entry point",
    ]
    cols = st.columns(3)
    for i, s in enumerate(suggestions):
        if cols[i % 3].button(s, use_container_width=True):
            st.session_state.current_q = s

    question = st.text_input(
        "Ask anything",
        value=st.session_state.get("current_q", ""),
        placeholder="e.g. How does login work? Where is error handling?",
    )
    col1, col2 = st.columns([1, 5])
    ask_btn = col1.button("Ask →", type="primary")
    top_k   = col2.slider("Chunks to retrieve", 3, 10, 5)

    if ask_btn and question:
        with st.spinner("🔍 Searching codebase..."):
            rag    = get_rag()
            result = rag.ask(question, top_k=top_k)
        st.session_state.chat_history.append({"q": question, "r": result})
        st.session_state.pop("current_q", None)
        st.rerun()

    for item in reversed(st.session_state.chat_history):
        st.markdown(f"**❓ {item['q']}**")
        st.markdown(
            f'<div class="answer-box">{item["r"]["answer"]}</div>',
            unsafe_allow_html=True,
        )
        with st.expander(f"📁 {item['r']['chunks_used']} source chunks used"):
            for s in item["r"]["sources"]:
                st.markdown(
                    f'<div class="source-card">'
                    f'<b>{s["name"]}</b> ({s["type"]}) · '
                    f'{s["file"]} · lines {s["lines"]} · score {s["score"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        st.divider()

# ══════════════════════════════════════════════════════════════
# PAGE: Dependency Graph
# ══════════════════════════════════════════════════════════════
elif page == "🗺️ Dependency Graph":
    st.markdown("## 🗺️ File dependency graph")
    st.caption("Shows how files import and depend on each other")

    # Always regenerate fresh diagram
    if st.session_state.graph:
        with st.spinner("Rendering graph..."):
            st.session_state.graph.visualize(
                output_path="data/indexes/graph.png"
            )

    graph_path = "data/indexes/graph.png"
    if os.path.exists(graph_path):
        from PIL import Image
        img = Image.open(graph_path)
        st.image(img, use_column_width=True, caption="File dependency graph")

        # Download button
        with open(graph_path, "rb") as f:
            st.download_button(
                "📥 Download graph",
                f, "dependency_graph.png", "image/png"
            )
    else:
        st.warning("⚠️ Graph not generated. Please build the index first.")
        if st.button("🔄 Generate now"):
            if st.session_state.parsed_files:
                g = CodeGraph()
                g.build(st.session_state.parsed_files)
                g.save()
                g.visualize()
                st.session_state.graph = g
                st.rerun()

    if st.session_state.graph:
        g = st.session_state.graph
        st.divider()
        st.markdown("### 🔗 Most connected files")
        for path, degree in g.get_most_connected_files(10):
            label = f"{os.path.basename(path)} — {degree} connections"
            st.progress(min(degree / 20, 1.0), text=label)

        st.markdown("### 🔍 File dependency lookup")
        options = [pf.file_path for pf in st.session_state.parsed_files]
        if options:
            selected = st.selectbox("Select file", options)
            if selected:
                deps = g.get_file_dependencies(selected)
                c1, c2 = st.columns(2)
                c1.markdown("**This file imports:**")
                for f in (deps["imports"] or ["(none)"]):
                    c1.code(os.path.basename(f))
                c2.markdown("**Imported by:**")
                for f in (deps["imported_by"] or ["(none)"]):
                    c2.code(os.path.basename(f))

# ══════════════════════════════════════════════════════════════
# PAGE: Complexity
# ══════════════════════════════════════════════════════════════
elif page == "📊 Complexity":
    st.markdown("## 🔥 Complexity analysis")
    st.caption("Cyclomatic complexity — higher = harder to test and maintain")

    if st.session_state.graph:
        hotspots = st.session_state.graph.get_complexity_hotspots(top_n=30)
        if hotspots:
            max_c = max(h["complexity"] for h in hotspots)
            for h in hotspots:
                icon = "🔴" if h["complexity"] > 8 else "🟡" if h["complexity"] > 4 else "🟢"
                st.markdown(
                    f"{icon} **`{h['function']}()`** — complexity {h['complexity']}  \n"
                    f"&nbsp;&nbsp;&nbsp;`{h['file']}` line {h['line']}"
                )
                st.progress(h["complexity"] / max(max_c, 1))
        else:
            st.success("No high-complexity functions found!")

# ══════════════════════════════════════════════════════════════
# PAGE: File Explorer
# ══════════════════════════════════════════════════════════════
elif page == "🗂️ File Explorer":
    st.markdown("## 🗂️ File explorer")

    search = st.text_input("🔍 Filter files", placeholder="e.g. auth, model, api")

    files = st.session_state.parsed_files
    if search:
        files = [f for f in files if search.lower() in f.file_path.lower()]

    st.caption(f"Showing {len(files)} files")

    for pf in files:
        label = f"📄 {pf.file_path}  ({pf.total_lines} lines · {len(pf.functions)} functions · {len(pf.classes)} classes)"
        with st.expander(label):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Functions",  len(pf.functions))
            c2.metric("Classes",    len(pf.classes))
            c3.metric("Imports",    len(pf.imports))
            c4.metric("Complexity", pf.complexity_score)

            if pf.functions:
                st.markdown("**Functions:**")
                for fn in pf.functions:
                    complexity_icon = "🔴" if fn.complexity > 8 else "🟡" if fn.complexity > 4 else "🟢"
                    st.markdown(
                        f"{complexity_icon} `{fn.name}("
                        f"{', '.join(fn.args)})` "
                        f"line {fn.start_line} — complexity {fn.complexity}"
                    )

            if pf.classes:
                st.markdown("**Classes:**")
                for cls in pf.classes:
                    st.markdown(
                        f"🏛️ `{cls.name}` "
                        f"— methods: {', '.join(f'`{m}`' for m in cls.methods[:5])}"
                    )

            if pf.imports:
                with st.expander(f"Imports ({len(pf.imports)})"):
                    for imp in pf.imports:
                        st.code(imp, language="python")

# ══════════════════════════════════════════════════════════════
# PAGE: Bug Detection
# ══════════════════════════════════════════════════════════════
elif page == "🐛 Bug Detection":
    st.markdown("## 🐛 Bug detection report")

    bugs = st.session_state.bugs
    s    = st.session_state.bug_sum

    if not bugs:
        st.info("No bugs detected or index not built yet.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Issues", s.get("total", 0))
        c2.metric("🔴 High",      s.get("high", 0))
        c3.metric("🟡 Medium",    s.get("medium", 0))
        c4.metric("🟢 Low",       s.get("low", 0))

        st.divider()

        severity_filter = st.multiselect(
            "Filter by severity",
            ["high", "medium", "low"],
            default=["high", "medium", "low"],
        )

        filtered = [b for b in bugs if b.severity in severity_filter]
        st.caption(f"Showing {len(filtered)} issues")

        for bug in filtered:
            icon = "🔴" if bug.severity == "high" else "🟡" if bug.severity == "medium" else "🟢"
            title = f"{icon} {bug.message[:90]}{'...' if len(bug.message) > 90 else ''}"
            with st.expander(title):
                col1, col2, col3 = st.columns(3)
                col1.markdown(f"**File:** `{os.path.basename(bug.file_path)}`")
                col2.markdown(f"**Line:** {bug.line}")
                col3.markdown(f"**Category:** {bug.category}")
                st.markdown(f"**Full path:** `{bug.file_path}`")
                st.markdown(f"**Message:** {bug.message}")
                if bug.code_snippet:
                    st.code(bug.code_snippet, language="python")

# ══════════════════════════════════════════════════════════════
# PAGE: Architecture
# ══════════════════════════════════════════════════════════════
elif page == "🏗️ Architecture":
    st.markdown("## 🏗️ Architecture diagram")
    st.caption("Auto-generated system layer diagram from your codebase structure")

    # Always regenerate fresh
    if st.session_state.parsed_files and not os.path.exists("data/indexes/architecture.png"):
        with st.spinner("Generating architecture diagram..."):
            arch = ArchitectureDiagramGenerator()
            layers = arch.generate(st.session_state.parsed_files)
            st.session_state.arch_layers = layers

    diag_path = "data/indexes/architecture.png"
    if os.path.exists(diag_path):
        from PIL import Image
        img = Image.open(diag_path)
        st.image(img, use_column_width=True, caption="System architecture")

        # Download button
        with open(diag_path, "rb") as f:
            st.download_button(
                "📥 Download diagram",
                f, "architecture.png", "image/png"
            )
    else:
        st.warning("⚠️ Diagram not generated yet.")
        if st.button("🔨 Generate architecture diagram"):
            with st.spinner("Generating..."):
                arch   = ArchitectureDiagramGenerator()
                layers = arch.generate(st.session_state.parsed_files)
                st.session_state.arch_layers = layers
            st.rerun()

    if st.session_state.arch_layers:
        st.divider()
        st.markdown("### 📐 Layer breakdown")
        layer_icons = {
            "api": "🔵", "core": "🟣", "models": "🩷",
            "data": "🩵", "utils": "🟢", "other": "⚫"
        }
        cols = st.columns(min(len(st.session_state.arch_layers), 3))
        for i, (layer, files) in enumerate(st.session_state.arch_layers.items()):
            icon = layer_icons.get(layer, "⚪")
            col = cols[i % len(cols)]
            col.markdown(f"{icon} **{layer.upper()}**")
            for f in files:
                col.markdown(f"&nbsp;&nbsp;`{os.path.basename(f)}`")