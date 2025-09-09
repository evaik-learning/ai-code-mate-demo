# 🤖 AI Code Mate - GitHub Repository Analysis Assistant

AI Code Mate is an intelligent assistant that analyzes GitHub repositories for bugs, explains code, and provides improvement suggestions. It uses Groq's LLM API and connects directly to GitHub repositories via the GitHub API.

## ✨ Features

- **🔍 Intelligent Code Analysis**: Find bugs, security issues, and performance problems
- **📚 Code Explanation**: Understand complex code patterns and architectures  
- **💡 Improvement Suggestions**: Get actionable recommendations for better code
- **🔄 Dynamic Repository Switching**: Switch between different GitHub repositories
- **📊 Real-time Streaming**: See AI responses and tool execution in real-time
- **🛠️ Tool Execution Log**: Monitor GitHub API calls and results
- **🎨 Modern UI**: Clean, intuitive Gradio interface

## Preview ###
https://github.com/user-attachments/assets/187903a7-798c-4381-bd0a-f561133dcf33

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Using pipenv (recommended)
pipenv install -r requirements.txt

# Or using pip
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file with your API keys:

```bash
# Groq API Configuration
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama3-8b-8192

# GitHub Configuration  
GITHUB_TOKEN=your_github_token_here
GITHUB_OWNER=evaik-learning
GITHUB_REPO=ai-code-mate-demo
```

### 3. Get API Keys

**Groq API Key:**
1. Visit [console.groq.com](https://console.groq.com)
2. Sign up/login and create an API key

**GitHub Token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with `repo` permissions
3. Copy the token to your `.env` file

### 4. Run the Application

```bash
python app_gradio.py
```

The application will start at `http://localhost:7860`

## 🎯 Usage Examples

### Code Analysis
- "Find bugs in the authentication module"
- "Analyze the performance of the main function"
- "Check for security vulnerabilities"

### Code Explanation
- "Explain how the authentication system works"
- "What does the main function do?"
- "How does the error handling work?"

### Repository Exploration
- "Show me the project structure"
- "What are the main components of this codebase?"
- "List all the configuration files"

### Improvement Suggestions
- "Suggest improvements for the error handling"
- "How can I optimize this code?"
- "What best practices should be implemented?"

## 🔧 Repository Management

### Switching Repositories
1. Enter the repository owner and name in the sidebar
2. Click "🔄 Switch Repository"
3. The AI will now analyze the new repository

### Repository Information
- Click "ℹ️ Repository Info" to see repository metadata
- View stars, forks, language, and description

## 🛠️ Available Tools

The AI has access to these GitHub tools:

- **`search_code`**: Search for code patterns, functions, or text
- **`get_file_contents`**: Read complete file contents
- **`list_files`**: List files in directories
- **`get_repo_info`**: Get repository metadata
- **`switch_repo`**: Switch to different repositories

## 📁 Project Structure

```
ai-code-mate-demo/
├── agent.py              # Main AI agent with streaming
├── app_gradio.py         # Gradio web interface
├── github_client.py      # GitHub API client
├── github_mcp_server.py  # MCP server (optional)
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key (required) | - |
| `GROQ_MODEL` | Groq model to use | `llama3-8b-8192` |
| `GITHUB_TOKEN` | GitHub personal access token (required) | - |
| `GITHUB_OWNER` | Default repository owner | `evaik-learning` |
| `GITHUB_REPO` | Default repository name | `ai-code-mate-demo` |

### Model Options

Supported Groq models:
- `llama3-8b-8192` (default)
- `llama3-70b-8192`
- `mixtral-8x7b-32768`
- `gemma-7b-it`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

**"Connection error" or "Failed to resolve api.groq.com"**
- Check your internet connection
- Verify your Groq API key is correct
- Try switching to a different network

**"GitHub client not configured"**
- Make sure you've set `GITHUB_TOKEN` in your `.env` file
- Verify the token has `repo` permissions

**Empty responses from AI**
- Check that your Groq API key is valid
- Ensure you have sufficient API credits
- Try a different model

### Getting Help

- Check the tool execution log for detailed error messages
- Enable "Show raw tool results" to see full API responses
- Verify your environment variables are set correctly
