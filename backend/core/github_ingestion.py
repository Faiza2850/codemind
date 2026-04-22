import os
import re
import shutil
import tempfile
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class RepoInfo:
    url:        str
    owner:      str
    repo_name:  str
    local_path: str
    branch:     str = "main"


def parse_github_url(url: str) -> Optional[tuple]:
    """Extract owner and repo name from any GitHub URL format."""
    url = url.strip().rstrip("/")
    patterns = [
        r"(?:https?://)?github\.com/([^/]+)/([^/\s\.]+?)(?:\.git)?$",
        r"git@github\.com:([^/]+)/([^/\s\.]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            return match.group(1), match.group(2)
    return None


class GitHubIngestion:
    """Clone and manage GitHub repositories for analysis."""

    CLONE_BASE = "/tmp/codemind_repos"

    def __init__(self):
        os.makedirs(self.CLONE_BASE, exist_ok=True)

    def clone(self, github_url: str, progress_callback=None) -> RepoInfo:
        parsed = parse_github_url(github_url)
        if not parsed:
            raise ValueError(f"Invalid GitHub URL: {github_url}")

        owner, repo_name = parsed
        local_path = os.path.join(self.CLONE_BASE, f"{owner}_{repo_name}")

        # If already cloned, pull latest
        if os.path.exists(local_path):
            if progress_callback:
                progress_callback(f"📥 Repo cached, pulling latest...")
            try:
                subprocess.run(
                    ["git", "-C", local_path, "pull", "--quiet"],
                    timeout=60, capture_output=True
                )
            except Exception:
                shutil.rmtree(local_path, ignore_errors=True)

        # Clone fresh
        if not os.path.exists(local_path):
            if progress_callback:
                progress_callback(f"📥 Cloning {owner}/{repo_name}...")
            try:
                subprocess.run(
                    ["git", "clone", "--depth=1", "--quiet",
                     f"https://github.com/{owner}/{repo_name}.git",
                     local_path],
                    timeout=120,
                    capture_output=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                raise ValueError(
                    f"Failed to clone. Make sure the repo is public. "
                    f"Error: {e.stderr.decode()[:200]}"
                )

        if progress_callback:
            progress_callback(f"✅ Ready at {local_path}")

        return RepoInfo(
            url=github_url,
            owner=owner,
            repo_name=repo_name,
            local_path=local_path,
        )

    def get_repo_stats(self, local_path: str) -> dict:
        stats = {"total_files": 0, "by_extension": {}}
        skip = {".git", "__pycache__", "node_modules", ".venv", "venv"}
        supported = {".py", ".js", ".ts", ".jsx", ".tsx"}
        for root, dirs, files in os.walk(local_path):
            dirs[:] = [d for d in dirs if d not in skip]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in supported:
                    stats["total_files"] += 1
                    stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1
        return stats

    def cleanup(self, local_path: str):
        shutil.rmtree(local_path, ignore_errors=True)
