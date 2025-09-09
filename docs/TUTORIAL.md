# AI Code Mate Demo — Step‑by‑Step Tutorial

Build and run a local AI agent that can analyze GitHub repositories, search files, and explain code. This tutorial walks you through setup, how the code works, how to use the app, and how to extend it.

What you will learn
- How to run a simple AI agent locally with a UI
- How to call Groq’s OpenAI‑compatible Chat Completions API
- How to select and use openAI GPT‑OSS models (e.g., openai/gpt-oss-20b) via Groq
- How the project exposes GitHub as “tools” (an MCP‑style pattern) to the model
- How to extend the agent with new capabilities

Repository structure (key files)
- app_gradio.py — Gradio UI and event streaming to the page
- agent.py — LLM streaming, tool calling loop, conversation orchestration
- github_client.py — Lightweight GitHub API client (search, read files, list repos)

Prerequisites
- Python 3.9+
- A Groq API key
- Optional: A GitHub token (recommended to avoid low rate limits)

1) Clone and install
- Clone this repository.
- Create a virtual environment and install dependencies:
  - pip install -U gradio python-dotenv requests rich

2) Configure environment variables
Create a .env file in the project root:

GROQ_API_KEY=your_groq_api_key_here
# Optional: pick another Groq model (e.g., llama3-70b-8192, mixtral-8x7b-32768)
GROQ_MODEL=llama3-8b-8192

# Default GitHub repository the agent points at on startup
GITHUB_OWNER=evaik-learning
GITHUB_REPO=ai-code-mate-demo

# Optional but recommended: raises GitHub API limits
GITHUB_TOKEN=ghp_your_personal_access_token

Notes
- Groq supports high‑performance, open GPT‑OSS models such as Llama 3 and Mixtral. Set GROQ_MODEL to any supported model name to switch.
- If you omit GITHUB_TOKEN, the GitHub APIs may be rate‑limited.

3) Run the app locally
- Start the Gradio app: python app_gradio.py
- Open the URL printed in your terminal (default http://127.0.0.1:7860/).

UI overview
- Chat: Ask questions like “Find bugs”, “Explain this file”, or “Suggest improvements”.
- Repository Management: Load repos for an owner, switch the active repository.
- Settings: Toggle “Show raw tool results” to see tool JSON.
- Tool Execution Log: Real‑time trace of the agent’s tool calls and results.

4) How it works (architecture)
- Gradio UI (app_gradio.py)
  - Submits your prompt to stream_reply(), which yields three streams: partial assistant text, updated history, and a formatted Tool Execution Log.
  - The UI updates as the model streams tokens and as tools execute.
- The Agent (agent.py)
  - Uses Groq Chat Completions API with streaming to get tokens as they arrive.
  - Sends a structured system prompt plus a “tool catalog” describing available GitHub tools.
  - Parses streaming responses; if the final text is empty, it does a non‑streaming call to inspect native function/tool calls.
  - Executes tools via a local dispatcher (_call_tool) and appends results to the conversation so the model can continue reasoning with them.
  - Emits events: model_chunk, tool_call, reasoning, tool_result, final — which the UI renders.
- GitHub Client (github_client.py)
  - search_code(query, path): Combines a filename scan with GitHub code search.
  - get_file_contents(path): Fetches and decodes file contents from the repo.
  - list_files(path): Lists directory contents.
  - list_repos_for_owner(owner): Lists repos for a user or org (best‑effort across endpoints).
  - get_repo_info(): Basic repo metadata.
  - switch_repo(owner, repo): Changes the active repo the agent targets.

5) Using Groq with GPT‑OSS models
- This project uses Groq’s OpenAI‑compatible endpoint located at https://api.groq.com/openai/v1/chat/completions.
- Set GROQ_MODEL to select an open model:
  - llama3-8b-8192 (default)
  - openai/gpt-oss-20b
  - mixtral-8x7b-32768
  - gemma2-9b-it (as available)
- The agent relies on function/tool calling and text streaming; the Groq API responses are parsed incrementally for low‑latency UX.

6) MCP‑style tool pattern for GitHub
- While this repository does not implement the full Model Context Protocol (MCP), it follows the same idea: expose external capabilities as declarative tools the model can call.
- In agent.py, the tools catalog describes available functions and JSON schemas for their arguments.
- The loop dispatches calls to _call_tool(), which uses GitHubClient to execute.
- Tool results are appended back into the conversation so the model can reason over them.

Available tools (in this demo)
- search_code(query, path=""): Find files by name and code matches via GitHub search.
- get_file_contents(path): Read and return a file’s content.
- list_files(path="."): List directory entries.
- get_repo_info(): Repo metadata.
- switch_repo(owner, repo): Switch the active target repository.

7) Step‑by‑step: build your own agent from this template
- Step 1 — Define your system prompt
  - Describe the agent’s persona, capabilities, and formatting.
- Step 2 — Define tools
  - Add entries to the tools list (name, description, JSON schema for args).
  - Implement the corresponding functions in _call_tool().
- Step 3 — Stream model output
  - Use streaming to render partial tokens in the UI for responsiveness.
- Step 4 — Handle tool calls
  - When the assistant returns tool_calls, dispatch them, push results back to the conversation, and continue the loop.
- Step 5 — Design the UI
  - Build a minimal Gradio interface with a chat area, settings, and a tool log.

8) Extending the agent
- Add a new tool (example: repo tree)
  - Implement a new function in github_client.py, e.g., get_file_tree().
  - Add a new branch in _call_tool() to execute it.
  - Register it in the tools schema sent to the model.
- Add analysis skills
  - Expand SYSTEM_PROMPT with guidance like “identify security smells” or “write unit tests”.
- Swap models
  - Change GROQ_MODEL to switch to a larger or more instruction‑tuned model.

9) Troubleshooting
- 429 Too Many Requests
  - The agent has retry/backoff logic for Groq API. If it persists, slow down or try later.
- GitHub rate limits
  - Provide GITHUB_TOKEN and keep requests modest.
- Empty or partial answers
  - The agent falls back to a non‑streaming call to retrieve tool_calls when needed; check the Tool Execution Log and enable “Show raw tool results”.
- Encoding issues
  - The streaming code forces UTF‑8 decoding for event lines.

10) Security notes
- Do not commit secrets. Use .env for keys and tokens.
- The agent will only access public GitHub APIs through the declared tools; review any new tools you add.

Command cheat‑sheet
- Install deps: pip install -U gradio python-dotenv requests rich
- Run app: python app_gradio.py

That’s it — you now have a local AI agent that can analyze GitHub repositories using Groq and openai/gpt-oss-20b models, with an MCP‑style tool pattern you can extend for your own use cases.
