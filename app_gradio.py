# app_gradio.py #
import gradio as gr
from agent import ask_agent_stream, github_client
from dotenv import load_dotenv
import json
load_dotenv()

EVENT_HEADER = "### 🔧 Tool Execution Log\n"
def stream_reply(user_message, history, show_raw_tool):
    """
    Streaming handler for Gradio.
    We progressively update the last assistant message and the event log.
    """
    if not user_message:
        yield history, history, EVENT_HEADER
        return

    # Prime the chat with a placeholder assistant message
    history = history + [[user_message, ""]]
    event_log = EVENT_HEADER

    # Build a minimal conv history for the agent (optional but nice for context)
    conv_history = []
    # history includes the new empty assistant entry, so build from all but the last
    for i, pair in enumerate(history[:-1]):
        user_msg, bot_msg = pair
        conv_history.append({"role": "user", "content": user_msg})
        conv_history.append({"role": "assistant", "content": bot_msg})

    # Stream events from the agent
    partial = []
    for event in ask_agent_stream(user_message, conv_history=conv_history, debug=True, show_raw_tool=show_raw_tool):
        etype = event.get("type")
        if etype == "model_chunk":
            partial.append(event["text"])
            history[-1][1] = "".join(partial)
            yield history, history, event_log

        elif etype == "tool_call":
            tool = event["tool"]
            args = event.get("args", {})
            event_log += f"- 🛠️ **Executing** `{tool}`\n"
            if args:
                event_log += f"  - Args: `{json.dumps(args, indent=2)}`\n"
            yield history, history, event_log

        elif etype == "reasoning":
            note = event.get("text", "")
            if note:
                event_log += f"- 🧠 **Reasoning**: {note}\n"
            yield history, history, event_log

        elif etype == "tool_result":
            tool = event["tool"]
            preview = event.get("preview", "")
            event_log += f"- ✅ **Completed** `{tool}`\n"
            if preview and len(preview) < 500:
                event_log += f"  - Result: `{preview}`\n"
            elif preview:
                event_log += f"  - Result: `{preview[:200]}...`\n"
            
            # If user wants raw results, append nicely below
            raw = event.get("raw")
            if raw is not None and show_raw_tool:
                event_log += f"\n<details><summary>📋 Raw Data</summary>\n\n```json\n{json.dumps(raw, indent=2)}\n```\n</details>\n"
            yield history, history, event_log

        elif etype == "final":
            final_text = event.get("text", "")
            if not partial:  # if nothing streamed (e.g., JSON only), show the final now
                history[-1][1] = final_text
            else:
                # make sure any final delta is appended
                history[-1][1] = "".join(partial) if final_text == "" else final_text
            yield history, history, event_log
            return

    # Safety return in case generator exits unexpectedly
    yield history, history, event_log

def switch_repository(owner, repo):
    """Switch to a different GitHub repository"""
    try:
        result = github_client.switch_repo(owner, repo)
        return f"✅ {result}", f"Current Repository: **{owner}/{repo}**"
    except Exception as e:
        return f"❌ Error switching repository: {str(e)}", f"Current Repository: **{github_client.get_current_repo()}**"

def get_current_repo_info():
    """Get current repository information"""
    try:
        info = github_client.get_repo_info()
        if "error" in info:
            return f"❌ Error: {info['error']}"
        
        return f"""
**Repository:** {info.get('full_name', 'Unknown')}
**Description:** {info.get('description', 'No description')}
**Language:** {info.get('language', 'Unknown')}
**Stars:** ⭐ {info.get('stargazers_count', 0)}
**Forks:** 🍴 {info.get('forks_count', 0)}
**Last Updated:** {info.get('updated_at', 'Unknown')}
"""
    except Exception as e:
        return f"❌ Error getting repository info: {str(e)}"

with gr.Blocks(fill_height=True, title="AI Code Mate") as demo:
    gr.Markdown("# 🤖 AI Code Mate - GitHub Repository Analysis Assistant")
    gr.Markdown("Analyze GitHub repositories for bugs, explain code, and get improvement suggestions")
    
    with gr.Row():
        with gr.Column(scale=3):
            chat = gr.Chatbot(
                height=500,
                label="💬 Chat with AI Code Mate",
                show_label=True,
                bubble_full_width=False
            )
            
            with gr.Row():
                txt = gr.Textbox(
                    placeholder="Ask about the repository (e.g., 'Find bugs in the code', 'Explain the main function', 'Suggest improvements')",
                    show_label=False,
                    scale=4
                )
                send = gr.Button("🚀 Send", scale=1, variant="primary")
        
        with gr.Column(scale=1):
            # Repository Management
            gr.Markdown("### 📁 Repository Management")
            
            with gr.Row():
                repo_owner = gr.Textbox(
                    label="Owner",
                    placeholder="evaik-learning",
                    value="evaik-learning"
                )
                repo_name = gr.Dropdown(label="Repository", choices=[], value=None)
            
            def load_repos(owner):
                try:
                    names = github_client.list_repos_for_owner(owner)
                    # Return choices and a default selection (keep current if present)
                    current = github_client.get_current_repo().split("/")[-1]
                    default = current if current in names else (names[0] if names else None)
                    return gr.Dropdown(choices=names, value=default)
                except Exception:
                    return gr.Dropdown(choices=[], value=None)
            
            load_btn = gr.Button("🔁 Load Repos", variant="secondary")
            load_btn.click(load_repos, inputs=[repo_owner], outputs=[repo_name], queue=False)
            
            switch_btn = gr.Button("🔄 Switch Repository", variant="secondary")
            current_repo_display = gr.Markdown(f"Current Repository: **{github_client.get_current_repo()}**")
            
            repo_info_btn = gr.Button("ℹ️ Repository Info", variant="secondary")
            repo_info_display = gr.Markdown("Click 'Repository Info' to see details")
            
            # Settings
            gr.Markdown("### ⚙️ Settings")
            show_raw = gr.Checkbox(label="Show raw tool results", value=False)
            
            # Event Log
            event_md = gr.Markdown(EVENT_HEADER, elem_id="event_log", height=300)

    state = gr.State([])  # chat history

    def submit_fn(message, history, show_raw_tool):
        # Yield directly from the stream_reply generator
        yield from stream_reply(message, history, show_raw_tool)

    # Chat functionality
    send.click(
        submit_fn,
        inputs=[txt, state, show_raw],
        outputs=[chat, state, event_md],
        queue=True,
        show_progress=True,
    )
    txt.submit(
        submit_fn,
        inputs=[txt, state, show_raw],
        outputs=[chat, state, event_md],
        queue=True,
        show_progress=True,
    )
    
    # Repository switching functionality
    switch_btn.click(
        switch_repository,
        inputs=[repo_owner, repo_name],
        outputs=[gr.Textbox(visible=False), current_repo_display],
        queue=False
    )
    
    # Repository info functionality
    repo_info_btn.click(
        get_current_repo_info,
        outputs=[repo_info_display],
        queue=False
    )

if __name__ == "__main__":
    demo.queue().launch(
    share=False,
    server_name="0.0.0.0",
    server_port=7860
)
