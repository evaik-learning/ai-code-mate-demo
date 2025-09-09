# agent.py #
"""
AI Code Mate Agent - GitHub Repository Analysis Assistant
- Connects to GitHub repositories via MCP
- Provides intelligent code analysis, bug detection, and improvement suggestions
- Supports dynamic repository switching
- Streams responses with real-time tool execution
"""
import os
import json
import requests
import time
import random
from dotenv import load_dotenv
from rich import print
from github_client import GitHubClient
import re

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

print("API Key present:" + GROQ_API_KEY)


if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is required. Please set it in your .env file.")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Shared HTTP helper with retries for Groq API
def _post_with_retries(payload, stream=False, timeout=300, max_retries=6):
    attempt = 0
    last_exc = None
    while attempt < max_retries:
        try:
            r = requests.post(GROQ_URL, headers=HEADERS, json=payload, stream=stream, timeout=timeout)
            # Handle rate limiting explicitly
            if r.status_code == 429:
                # Respect Retry-After header if present
                retry_after = r.headers.get("Retry-After") or r.headers.get("retry-after") or r.headers.get("X-RateLimit-Reset-After")
                if retry_after:
                    try:
                        sleep_s = float(retry_after)
                    except ValueError:
                        # Some providers return a timestamp; fallback to exponential backoff
                        sleep_s = min(30, (2 ** attempt) + random.uniform(0, 0.5))
                else:
                    sleep_s = min(30, (2 ** attempt) + random.uniform(0, 0.5))
                last_exc = requests.exceptions.HTTPError("429 Too Many Requests", response=r)
                time.sleep(sleep_s)
                attempt += 1
                continue
            # Retry on some transient 5xx errors as well
            if 500 <= r.status_code < 600:
                last_exc = requests.exceptions.HTTPError(f"{r.status_code} Server Error", response=r)
                sleep_s = min(30, (2 ** attempt) + random.uniform(0, 0.5))
                time.sleep(sleep_s)
                attempt += 1
                continue
            r.raise_for_status()
            return r
        except requests.exceptions.HTTPError as e:
            # Already handled explicit 429/5xx above; for other HTTP errors do not retry
            last_exc = e
            break
        except requests.exceptions.RequestException as e:
            # Network-level error; retry with backoff
            last_exc = e
            sleep_s = min(30, (2 ** attempt) + random.uniform(0, 0.5))
            time.sleep(sleep_s)
            attempt += 1
            continue
    if last_exc:
        raise last_exc

# Initialize GitHub client
github_client = GitHubClient()

SYSTEM_PROMPT = """
You are AI Code Mate, an expert software engineer and code analyst specializing in GitHub repository analysis.

CORE CAPABILITIES:
- Analyze code for bugs, security issues, and performance problems
- Explain complex code patterns and architectures
- Suggest improvements and best practices
- Navigate large codebases efficiently
- Provide detailed technical explanations

RESPONSE FORMATTING:
- Use clear, structured responses with headers and bullet points
- Include code examples when relevant
- Provide actionable recommendations
- Explain technical concepts in an accessible way
- Use markdown formatting for better readability

CURRENT REPOSITORY: {current_repo}

When analyzing code, follow this approach:
1. First understand the context and purpose
2. Identify potential issues or areas for improvement
3. Provide specific, actionable recommendations
4. Include relevant code snippets with explanations
"""

TOOL_DOCS_TEXT = """
AVAILABLE GITHUB TOOLS:
1) search_code(query, path="") - Search for code patterns, functions, or text in the repository
2) get_file_contents(path) - Read the complete contents of a specific file
3) list_files(path=".") - List all files in a directory
4) get_repo_info() - Get repository metadata and statistics
5) switch_repo(owner, repo) - Switch to a different GitHub repository

USAGE EXAMPLES:
- To find bugs: search_code("bug", "src/")
- To analyze a file: get_file_contents("src/main.py")
- To explore structure: list_files("src/")
- To switch repos: switch_repo("owner", "repo-name")
"""


def _groq_chat_stream(messages, temperature=0.0, max_tokens=1024):
    """
    Streaming generator: yields text chunks as they arrive.
    Yields only content deltas (strings). When finished, returns the full message.
    """
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "tool_choice": "auto",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search for code patterns, functions, or text in the repository",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "path": {"type": "string"}
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_file_contents",
                    "description": "Read the complete contents of a specific file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            },
        ],
        "response_format": {"type": "text"},
    }
    with _post_with_retries(payload, stream=True, timeout=300) as r:
        r.raise_for_status()
        # Ensure UTF-8 decoding for streamed chunks to avoid mojibake (e.g., ð)
        r.encoding = "utf-8"
        full = []
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break
            try:
                obj = json.loads(data)
                # OpenAI-compatible delta
                choices = obj.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                chunk = delta.get("content")
                if chunk:
                    full.append(chunk)
                    yield chunk  # stream out the chunk
            except Exception:
                # if any parsing issue, skip that line
                continue
        # return final full message as a joined string
        yield {"__final__": "".join(full)}
# GitHub tool calling functions
def _call_tool(tool_name, args):
    """Call GitHub tools using the GitHub client"""
    try:
        if tool_name == "search_code":
            query = args.get("query", "")
            path = args.get("path", "")
            result = github_client.search_code(query, path)
            return {
                "query": query,
                "path": path,
                "total_matches": result.get("total_count", 0),
                "filename_matches": result.get("filename_matches", []),
                "content_matches": result.get("content_matches", {}).get("items", []),
            }

        elif tool_name == "get_file_contents":
            path = args.get("path", "")
            content = github_client.get_file_contents(path)
            return {"path": path, "content": content}

        elif tool_name == "list_files":
            path = args.get("path", ".")
            files = github_client.list_files(path)
            return {"path": path, "files": files}

        elif tool_name == "get_repo_info":
            info = github_client.get_repo_info()
            return {"repo_info": info}

        elif tool_name == "switch_repo":
            owner = args.get("owner", "")
            repo = args.get("repo", "")
            result = github_client.switch_repo(owner, repo)
            return {"message": result, "new_repo": f"{owner}/{repo}"}

        elif tool_name == "list_all_files":
            files = github_client.list_all_files()
            return {"files": files, "count": len(files)}

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    except Exception as e:
        return {"error": f"Tool call failed: {str(e)}"}

def ask_agent_stream(user_question, conv_history=None, debug=False, show_raw_tool=False):
    """
    Streaming generator of structured events for the UI.

    Yields dicts:
      - {"type":"model_chunk","text": "..."}  # partial tokens
      - {"type":"tool_call","tool": "search_code","args": {...}}
      - {"type":"tool_result","tool": "...","preview":"...","raw":{...}}  # 'raw' included only if show_raw_tool=True
      - {"type":"final","text":"..."}  # final assistant message (when not a tool call)
    """
    messages = conv_history[:] if conv_history else []
    
    # Format system prompt with current repository
    current_repo = github_client.get_current_repo()
    formatted_system_prompt = SYSTEM_PROMPT.format(current_repo=current_repo)
    
    messages.insert(0, {"role": "system", "content": formatted_system_prompt + "\n" + TOOL_DOCS_TEXT})
    messages.append({"role": "user", "content": user_question})

    while True:
        # 1) stream a single assistant message
        assembled = []
        try:
            for piece in _groq_chat_stream(messages):
                if isinstance(piece, dict) and "__final__" in piece:
                    final_msg = piece["__final__"]
                    break
                else:
                    assembled.append(piece)
                    yield {"type": "model_chunk", "text": piece}
            else:
                final_msg = "".join(assembled)
        except requests.exceptions.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 429:
                final_msg = "The upstream model API returned 429 Too Many Requests. Please wait a few seconds and try again."
            else:
                final_msg = f"Upstream HTTP error: {str(e)}"
            yield {"type": "final", "text": final_msg}
            return
        except Exception as e:
            yield {"type": "final", "text": f"Unexpected error while streaming: {str(e)}"}
            return

        # 2) If streamed text is empty, check for native tool calls via a single non-streaming call
        try:
            if final_msg.strip() != "":
                raise RuntimeError("Skip native tool check; we have final text")
            # Make a non-streaming call to get the full message with tool_calls
            payload = {
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 1024,
                "tool_choice": "auto",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "search_code",
                            "description": "Search for code patterns, functions, or text in the repository",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "path": {"type": "string"}
                                },
                                "required": ["query"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_file_contents",
                            "description": "Read the complete contents of a specific file",
                            "parameters": {
                                "type": "object",
                                "properties": {"path": {"type": "string"}},
                                "required": ["path"],
                            },
                        },
                    },
                ],
                "response_format": {"type": "text"},
            }
            r = _post_with_retries(payload, stream=False, timeout=60)
            r.raise_for_status()
            full_message = r.json()["choices"][0]["message"]
            tool_calls = full_message.get("tool_calls", [])
            
            if tool_calls:
                # Persist the assistant turn that triggered the tool calls
                messages.append({
                    "role": "assistant",
                    "content": full_message.get("content", ""),
                    "tool_calls": tool_calls,
                })
                # Handle native tool calls
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name")
                    arg_str = func.get("arguments") or "{}"
                    try:
                        args = json.loads(arg_str) if isinstance(arg_str, str) else arg_str
                    except Exception:
                        args = {}
                    
                    yield {"type": "tool_call", "tool": tool_name, "args": args}
                    
                    # Call the tool and emit result
                    try:
                        result = _call_tool(tool_name, args)
                        preview = json.dumps(result)[:1200] + ("..." if len(json.dumps(result)) > 1200 else "")
                        payload = {"type": "tool_result", "tool": tool_name, "preview": preview}
                        if show_raw_tool:
                            payload["raw"] = result
                        yield payload
                        
                        # Add tool result to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "name": tool_name,
                            "content": json.dumps(result)[:4000],
                        })
                    except Exception as ex:
                        err_msg = f"TOOL_CALL_ERROR: {ex}"
                        yield {"type": "tool_result", "tool": tool_name, "preview": err_msg}
                        messages.append({
                            "role": "tool", 
                            "tool_call_id": tc.get("id"),
                            "name": tool_name,
                            "content": err_msg,
                        })
                
                # Ask model to continue
                messages.append({"role": "user", "content": "Continue reasoning with the tool results above and provide next step or final answer."})
                continue
                
        except Exception:
            pass  # Fall back to JSON parsing

        # 3) Try JSON-based tool calling (fallback)
        try:
            stripped = final_msg.strip()
            start = stripped.find("{")
            end = stripped.rfind("}")
            obj = json.loads(stripped[start:end+1])
        except Exception:
            # Not JSON
            if final_msg.strip() == "":
                # Avoid emitting an empty final response; ask model to produce an answer
                messages.append({
                    "role": "user",
                    "content": "Please provide a concise final answer summarizing findings and next steps.",
                })
                continue
            # Otherwise, treat as final natural-language answer
            yield {"type": "final", "text": final_msg}
            return

        action = obj.get("action")
        if action == "final_answer":
            yield {"type": "final", "text": obj.get("answer", "")}
            return

        if action != "_call_tool":
            # Unknown object => just surface as final text
            yield {"type": "final", "text": final_msg}
            return

        tool = obj.get("tool")
        args = obj.get("args", {})
        # Reasoning: normalize common query patterns before tool execution
        if tool == "search_code":
            raw_query = args.get("query", "")
            normalized = re.sub(r"\s+", " ", raw_query).strip()
            # If likely filename, normalize separators and case
            if ".py" in normalized or " " not in normalized:
                normalized = normalized.replace(" `", "").replace("`", "")
                normalized = normalized.replace("\\", "/")
            # Also strip punctuation that breaks GitHub search
            cleaned = re.sub(r"[^\w\.\-/ ]", " ", normalized).strip()
            if cleaned and cleaned != raw_query:
                yield {"type": "reasoning", "text": f"Normalized query from '{raw_query}' to '{cleaned}' for reliable search"}
                args["query"] = cleaned
            else:
                yield {"type": "reasoning", "text": f"Using query as-is: '{raw_query}'"}
            # Strategy note
            yield {"type": "reasoning", "text": "Strategy: filename match + content search"}
        yield {"type": "tool_call", "tool": tool, "args": args}

        # 4) call the tool and emit result
        try:
            result = _call_tool(tool, args)
            preview = json.dumps(result)[:1200] + ("..." if len(json.dumps(result)) > 1200 else "")
            payload = {"type": "tool_result", "tool": tool, "preview": preview}
            if show_raw_tool:
                payload["raw"] = result
            yield payload
        except Exception as ex:
            err_msg = f"TOOL_CALL_ERROR: {ex}"
            yield {"type": "tool_result", "tool": tool, "preview": err_msg}
            # Don't continue with undefined result variable
            messages.append({"role": "assistant", "content": f"TOOL_RESULT: {err_msg}"})
            messages.append({"role": "user", "content": "Continue reasoning with the tool result above and provide next step or final answer."})
            continue

        # 5) add tool result to conversation and loop back to the model
        messages.append({"role": "assistant", "content": f"TOOL_RESULT: {json.dumps(result)[:4000]}"})
        messages.append({"role": "user", "content": "Continue reasoning with the tool result above and provide next step or final answer."})
        # loop continues to stream the next assistant message
