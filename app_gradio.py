# app_gradio.py #
import gradio as gr
from agent import ask_agent
from dotenv import load_dotenv
load_dotenv()

def respond(user_message, history):
    # history is list of [user, bot] pairs from Gradio
    conv_history = []
    # build minimal conv history for the agent (optional)
    for pair in history:
        user_msg, bot_msg = pair
        conv_history.append({"role": "user", "content": user_msg})
        conv_history.append({"role": "assistant", "content": bot_msg})
    # ask agent
    answer = ask_agent(user_message, conv_history=conv_history, debug=True)
    # append to gradio history
    history = history + [[user_message, answer]]
    return history, history

with gr.Blocks() as demo:
    gr.Markdown("# AICodeMate — demo (Groq GPT-OSS + MCP + Gradio)")
    chat = gr.Chatbot()
    state = gr.State([])
    txt = gr.Textbox(placeholder="Ask about the repository (e.g., 'find average function bug')", show_label=False)
    send = gr.Button("Send")
    def handle_send(text, history):
        if not text:
            return history, history
        new_history, hist = respond(text, history)
        return new_history, hist
    send.click(handle_send, [txt, state], [chat, state])
    txt.submit(handle_send, [txt, state], [chat, state])
    gr.Markdown("Use this demo to ask the assistant to search the repo, open files, and explain code.")

if __name__ == "__main__":
    demo.launch(share=False, server_name="0.0.0.0", server_port=7860)
