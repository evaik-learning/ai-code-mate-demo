# agent.py #
"""
Agent orchestrator that:
- talks to Groq Chat Completion endpoint
- offers a tool-calling loop: model may request a tool call with a JSON payload
  like: {"action":"call_tool","tool":"search_repo","args":{"q":"average bug"}}
- agent calls local MCP server endpoints and feeds results back to the model.
"""
import os
import json
import requests
from dotenv import load_dotenv
from rich import print

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
MCP_SERVER = os.getenv("MCP_SERVER", "http://localhost:8000")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

SYSTEM_PROMPT = """
You are AICodeMate, an assistant that helps inspect a GitHub repo for bugs, explain code, and suggest improvements.
You have access to two tools (described below). When you need repo context, produce a JSON object ONLY in your assistant response with one of these shapes:

1) Call a tool:
{"action":"call_tool", "tool":"search_repo", "args":{"q":"..."}}

or

{"action":"call_tool", "tool":"read_file", "args":{"path":"path/to/file.py"}}

2) Or if you're done, return:
{"action":"final_answer", "answer":"...explanation..."}

Do NOT output any extra text outside the JSON object when you intend a tool call. If you need multiple tool calls, return them in sequence by returning a JSON tool call, then after the tool result is given, you will be invoked again to continue reasoning.
"""

TOOL_DOCS_TEXT = """
TOOLS AVAILABLE:
1) search_repo(q) - searches filenames and small file contents for substring 'q'. Returns list of matches {path, snippet}.
2) read_file(path) - returns full file contents (up to server limit).
"""

# Helper: call Groq Chat completion
def groq_chat(messages, temperature=0.0, max_tokens=1024):
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "tool_choice": "auto",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "search_repo",
                    "description": "Search repository filenames and small file contents for substring q",
                    "parameters": {
                        "type": "object",
                        "properties": {"q": {"type": "string"}},
                        "required": ["q"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file's full contents",
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
    r = requests.post(GROQ_URL, headers=HEADERS, json=payload, timeout=60)
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # Surface server-provided message (e.g., invalid model -> 400)
        try:
            err_body = r.json()
        except Exception:
            err_body = r.text
        raise RuntimeError(
            f"Groq API error {r.status_code} for model '{GROQ_MODEL}': {err_body}"
        ) from e
    j = r.json()
    # Groq API returns choices...structure similar to OpenAI-compatible endpoint
    return j["choices"][0]["message"]

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
    }
    with requests.post(GROQ_URL, headers=HEADERS, json=payload, stream=True, timeout=300) as r:
        r.raise_for_status()
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
# Call MCP server tools
def call_tool(tool_name, args):
    if tool_name == "search_repo":
        resp = requests.get(f"{MCP_SERVER}/tools/search_repo", params={"q": args["q"]}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    elif tool_name == "read_file":
        resp = requests.get(f"{MCP_SERVER}/tools/read_file", params={"path": args["path"]}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    else:
        raise ValueError("Unknown tool")

# The multi-turn agent loop
def ask_agent(user_question, conv_history=None, debug=False):
    """
    conv_history: list of dict messages in {role, content} shape to maintain context.
    Returns final answer text.
    """
    messages = conv_history[:] if conv_history else []
    # system + tool docs
    messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT + "\n" + TOOL_DOCS_TEXT})
    messages.append({"role": "user", "content": user_question})

    while True:
        if debug:
            print("[bold blue]Sending messages to Groq...[/bold blue]")
        message = groq_chat(messages)
        if debug:
            print("[green]Model message:[/green]\n", message)
        # Handle official tool calls if present
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            # Append assistant message with tool_calls
            messages.append({"role": "assistant", "content": message.get("content", ""), "tool_calls": tool_calls})
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name")
                arg_str = func.get("arguments") or "{}"
                try:
                    args = json.loads(arg_str) if isinstance(arg_str, str) else arg_str
                except Exception:
                    args = {}
                try:
                    tool_result = call_tool(name, args)
                    tool_content = json.dumps(tool_result)[:4000]
                except Exception as ex:
                    tool_content = f"TOOL_CALL_ERROR: {ex}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": name,
                    "content": tool_content,
                })
            # Ask model to continue reasoning with the tool outputs
            messages.append({"role": "user", "content": "Continue reasoning with the tool result above and provide next step or final answer."})
            continue

        model_output = message.get("content", "")
        # Try to parse JSON object out of model output
        try:
            stripped = model_output.strip()
            # If model returns backtick or markdown, try to extract first JSON block
            # naive: find first '{' and last '}' and parse
            start = stripped.find("{")
            end = stripped.rfind("}")
            json_text = stripped[start:end+1]
            obj = json.loads(json_text)
        except Exception as e:
            # If parsing fails, assume model returned final answer text
            return model_output

        action = obj.get("action")
        if action == "final_answer":
            return obj.get("answer", "")
        elif action == "call_tool":
            tool = obj.get("tool")
            args = obj.get("args", {})
            # call the MCP server
            try:
                tool_result = call_tool(tool, args)
            except Exception as ex:
                # append error and continue
                messages.append({"role": "assistant", "content": f"TOOL_CALL_ERROR: {ex}"})
                continue
            # Append tool result as assistant/tool result message and loop
            messages.append({"role": "assistant", "content": f"TOOL_RESULT: {json.dumps(tool_result)[:4000]}"})
            # Now ask the model to continue reasoning (no additional user message needed)
            messages.append({"role": "user", "content": "Continue reasoning with the tool result above and provide next step or final answer."})
            continue
        else:
            # unknown behavior: return raw model output
            return model_output
