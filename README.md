# AI Code Mate (Demo)
AI‑powered coding assistant demo that reviews GitHub repos, finds bugs, explains code, and suggests fixes — built with FastAPI, Groq GPT‑OSS,Model Context Protocol (MCP) and Gradio UI. Test

## Features
- Search repo files and contents via `search_repo`.
- Read files via `read_file`.
- Model-guided tool-calling loop: model decides when to read/search repo.
- Explains code, highlights errors, suggests fixes.

## Requirements
- Python 3.10+
- A Groq API key
- (Optional) GitHub token for private repos

## Install
```bash
git clone <this-demo-repo>
cd <this-demo-repo>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with keys: GROQ_API_KEY, GITHUB_TOKEN (if needed), REPO_OWNER, REPO_NAME

