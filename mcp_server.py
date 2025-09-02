# mcp_server.py #
"""
Simple MCP-like server (demo) that exposes three tools:
- list_tools (MCP discovery)
- search_repo(query)
- read_file(path)

This is a minimal, practical server (not full MCP spec). It responds with JSON.
"""
import os
import json
from typing import List
from fastapi import FastAPI, HTTPException, Query
import requests
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # optional for public repos
REPO_OWNER = os.getenv("REPO_OWNER", "evaik-learning")
REPO_NAME = os.getenv("REPO_NAME", "demo-repo")
BRANCH = os.getenv("REPO_BRANCH", "main")

app = FastAPI(title="Demo MCP Server (GitHub backed)")

GITHUB_API = "https://api.github.com"

headers = {}
if GITHUB_TOKEN:
    headers["Authorization"] = f"token {GITHUB_TOKEN}"

# -- Tool discovery route (MCP-like)
@app.get("/.well-known/mcp/servers", tags=["mcp"])
def server_info():
    """
    Return a simple info object describing available tools.
    """
    tools = [
        {
            "name": "search_repo",
            "description": "Search repository filenames and file contents for a substring (case-insensitive).",
            "params": {"q": "string"}
        },
        {
            "name": "read_file",
            "description": "Return raw file contents for a path relative to repo root.",
            "params": {"path": "string"}
        },
        {
            "name": "list_files",
            "description": "List files under a path (folder).",
            "params": {"path": "string"}
        }
    ]
    return {"server": "demo-github-mcp", "repo": f"{REPO_OWNER}/{REPO_NAME}", "tools": tools}

# Helper: read a file via GitHub API
def github_get_file(path: str):
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    params = {"ref": BRANCH}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    if resp.status_code == 200:
        j = resp.json()
        # if it's a file, content is base64
        if j.get("type") == "file":
            import base64
            content = base64.b64decode(j["content"]).decode("utf-8", errors="replace")
            return {"path": path, "content": content}
        else:
            raise HTTPException(status_code=400, detail="Path is not a file")
    elif resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Not found")
    else:
        raise HTTPException(status_code=resp.status_code, detail=f"GitHub error: {resp.text}")

# search_repo tool: simple substring search across filenames and file contents
@app.get("/tools/search_repo")
def search_repo(q: str = Query(..., min_length=1)):
    """
    Search filenames and (limited) file contents. Returns a list of matches: {path, snippet}.
    NOTE: This demo fetches repo file tree (recursively) using Git trees API then scans each file (size limit).
    """
    # fetch tree
    tree_url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/{BRANCH}?recursive=1"
    r = requests.get(tree_url, headers=headers, timeout=20)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repo tree: {r.text}")
    tree = r.json().get("tree", [])
    matches = []
    q_lower = q.lower()
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item.get("path")
        if q_lower in path.lower():
            matches.append({"path": path, "snippet": "(match in filename)"})
            continue
        # fetch small files only (e.g., < 50 KB)
        size = item.get("size") or 0
        if size > 50_000:
            continue
        try:
            f = github_get_file(path)
            if q_lower in f["content"].lower():
                # find a small snippet
                idx = f["content"].lower().find(q_lower)
                start = max(0, idx - 60)
                snippet = f["content"][start: start + 200].replace("\n", " ")
                matches.append({"path": path, "snippet": snippet})
        except Exception:
            continue
    return {"query": q, "matches": matches[:30]}

# read_file tool
@app.get("/tools/read_file")
def read_file(path: str = Query(..., min_length=1)):
    """
    Return the content of the requested file (size-limited).
    """
    f = github_get_file(path)
    content = f["content"]
    if len(content) > 200_000:
        content = content[:200_000] + "\n\n--TRUNCATED--"
    return {"path": path, "content": content}
