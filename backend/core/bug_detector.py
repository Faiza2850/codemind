import ast
import os
import subprocess
from dataclasses import dataclass
from typing import Optional
from backend.core.parser import ParsedFile

@dataclass
class BugReport:
    file_path:   str
    line:        int
    severity:    str          # "high" | "medium" | "low"
    category:    str          # "null_risk" | "unused" | "complexity" | "style"
    message:     str
    code_snippet: Optional[str]


class BugDetector:
    """
    Multi-layer bug detection:
    1. AST analysis  — null risks, bare excepts, mutable defaults
    2. pyflakes      — unused imports, undefined names
    3. Complexity    — functions too complex to maintain
    """

    COMPLEXITY_THRESHOLD = 8   # flag functions above this

    def analyze_files(self, parsed_files: list) -> list[BugReport]:
        """Run all checks on all parsed files, return sorted bug reports."""
        all_bugs = []
        for pf in parsed_files:
            if pf.language == "python":
                all_bugs += self._ast_checks(pf)
                all_bugs += self._pyflakes_check(pf.file_path)
                all_bugs += self._complexity_check(pf)
        # Sort: high → medium → low, then by file
        severity_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(all_bugs, key=lambda b: (severity_order[b.severity], b.file_path, b.line))

    # ── AST checks ────────────────────────────────────────────

    def _ast_checks(self, pf: ParsedFile) -> list[BugReport]:
        bugs = []
        try:
            with open(pf.file_path, "r", errors="replace") as f:
                source = f.read()
            lines  = source.splitlines()
            tree   = ast.parse(source, filename=pf.file_path)
        except SyntaxError as e:
            return [BugReport(
                file_path=pf.file_path, line=e.lineno or 0,
                severity="high", category="syntax",
                message=f"Syntax error: {e.msg}",
                code_snippet=None,
            )]

        for node in ast.walk(tree):

            # ── Bare except ───────────────────────────────────
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bugs.append(BugReport(
                    file_path=pf.file_path,
                    line=node.lineno,
                    severity="medium",
                    category="error_handling",
                    message="Bare `except:` catches everything including KeyboardInterrupt. Use `except Exception:`.",
                    code_snippet=self._get_line(lines, node.lineno),
                ))

            # ── Mutable default argument ──────────────────────
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        bugs.append(BugReport(
                            file_path=pf.file_path,
                            line=node.lineno,
                            severity="high",
                            category="null_risk",
                            message=f"`{node.name}()` uses mutable default argument. This is shared across all calls — use `None` and assign inside.",
                            code_snippet=self._get_line(lines, node.lineno),
                        ))

            # ── == None instead of is None ────────────────────
            if isinstance(node, ast.Compare):
                for op, comp in zip(node.ops, node.comparators):
                    if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant) and comp.value is None:
                        bugs.append(BugReport(
                            file_path=pf.file_path,
                            line=node.lineno,
                            severity="low",
                            category="style",
                            message="Use `is None` instead of `== None` for None comparisons.",
                            code_snippet=self._get_line(lines, node.lineno),
                        ))

            # ── Empty except body (just pass) ─────────────────
            if isinstance(node, ast.ExceptHandler):
                if node.body and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    bugs.append(BugReport(
                        file_path=pf.file_path,
                        line=node.lineno,
                        severity="medium",
                        category="error_handling",
                        message="Exception silently swallowed with `pass`. Log or re-raise the error.",
                        code_snippet=self._get_line(lines, node.lineno),
                    ))

            # ── Hardcoded secrets ─────────────────────────────
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id.lower()
                        if any(k in name for k in ("password", "secret", "api_key", "token", "passwd")):
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                if len(node.value.value) > 4:
                                    bugs.append(BugReport(
                                        file_path=pf.file_path,
                                        line=node.lineno,
                                        severity="high",
                                        category="security",
                                        message=f"Possible hardcoded secret in `{target.id}`. Move to environment variables.",
                                        code_snippet=self._get_line(lines, node.lineno),
                                    ))

            # ── Unused variable (assigned but never used) ─────
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assigned = {}
                used     = set()
                for child in ast.walk(node):
                    if isinstance(child, ast.Assign):
                        for t in child.targets:
                            if isinstance(t, ast.Name) and not t.id.startswith("_"):
                                assigned[t.id] = getattr(child, "lineno", node.lineno)
                    if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                        used.add(child.id)
                for var, lineno in assigned.items():
                    if var not in used:
                        bugs.append(BugReport(
                            file_path=pf.file_path,
                            line=lineno,
                            severity="low",
                            category="unused",
                            message=f"Variable `{var}` is assigned but never used.",
                            code_snippet=self._get_line(lines, lineno),
                        ))

        return bugs

    # ── pyflakes check ────────────────────────────────────────

    def _pyflakes_check(self, file_path: str) -> list[BugReport]:
        bugs = []
        try:
            result = subprocess.run(
                ["python3", "-m", "pyflakes", file_path],
                capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.splitlines():
                # Format: filepath:line:col: message
                parts = line.split(":")
                if len(parts) >= 3:
                    try:
                        lineno  = int(parts[1])
                        message = ":".join(parts[2:]).strip()
                        severity = "medium" if "undefined" in message.lower() else "low"
                        bugs.append(BugReport(
                            file_path=file_path,
                            line=lineno,
                            severity=severity,
                            category="unused",
                            message=f"[pyflakes] {message}",
                            code_snippet=None,
                        ))
                    except (ValueError, IndexError):
                        continue
        except Exception:
            pass
        return bugs

    # ── Complexity check ──────────────────────────────────────

    def _complexity_check(self, pf: ParsedFile) -> list[BugReport]:
        bugs = []
        for fn in pf.functions:
            if fn.complexity > self.COMPLEXITY_THRESHOLD:
                severity = "high" if fn.complexity > 12 else "medium"
                bugs.append(BugReport(
                    file_path=pf.file_path,
                    line=fn.start_line,
                    severity=severity,
                    category="complexity",
                    message=f"`{fn.name}()` has cyclomatic complexity {fn.complexity} (threshold: {self.COMPLEXITY_THRESHOLD}). Consider breaking it into smaller functions.",
                    code_snippet=None,
                ))
        return bugs

    # ── Helpers ───────────────────────────────────────────────

    def _get_line(self, lines: list, lineno: int) -> Optional[str]:
        idx = lineno - 1
        if 0 <= idx < len(lines):
            return lines[idx].strip()
        return None

    def summary(self, bugs: list[BugReport]) -> dict:
        return {
            "total":    len(bugs),
            "high":     sum(1 for b in bugs if b.severity == "high"),
            "medium":   sum(1 for b in bugs if b.severity == "medium"),
            "low":      sum(1 for b in bugs if b.severity == "low"),
            "by_category": {
                cat: sum(1 for b in bugs if b.category == cat)
                for cat in {"null_risk", "unused", "complexity", "security", "error_handling", "style"}
            }
        }