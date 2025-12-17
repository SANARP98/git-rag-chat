"""Simplified Gradio web UI for Git RAG Chat - Gradio 6.x compatible."""

import os
import logging
import gradio as gr
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
RAG_API_URL = os.getenv('RAG_API_URL', 'http://rag-pipeline:8001')
GRADIO_SERVER_PORT = int(os.getenv('GRADIO_SERVER_PORT', '7860'))

# Simple HTTP client
client = httpx.Client(timeout=60.0)


def add_repository(repo_path: str, emb_provider: str, emb_model: str):
    """Add a repository to the system with embedding selection."""
    try:
        if not repo_path.strip():
            return "❌ Error: Please enter a repository path"

        # Don't validate path in web-ui since volumes are mounted in rag-pipeline
        # Let the backend handle validation
        repo_name = repo_path.rstrip('/').split('/')[-1]

        # Step 1: Add repository
        response = client.post(
            f"{RAG_API_URL}/api/repos",
            json={"path": repo_path.strip(), "name": repo_name}
        )

        if response.status_code == 200:
            data = response.json()
            repo_id = data.get('id', data.get('repo_id', 'unknown'))

            # Step 2: Trigger indexing WITH embedding choice
            logger.info(f"Triggering indexing for repo {repo_id} with {emb_provider}/{emb_model}")
            index_payload = {"force_reindex": False, "embedding_provider": emb_provider}

            # Only send embedding_model if it's not the default
            if emb_model not in ["sentence-transformers/all-MiniLM-L6-v2", ""]:
                index_payload["embedding_model"] = emb_model

            index_response = client.post(
                f"{RAG_API_URL}/api/repos/{repo_id}/index",
                json=index_payload
            )

            if index_response.status_code == 200:
                index_data = index_response.json()
                indexed_files = index_data.get('indexed_files', 0)
                total_chunks = index_data.get('total_chunks', 0)
                emb_info = f"{index_data.get('embedding_provider', 'unknown')}/{index_data.get('embedding_model', 'unknown')}"
                emb_dim = index_data.get('embedding_dimension', 'unknown')

                return f"""✅ Repository '{repo_name}' added and indexed!

**Repo ID:** {repo_id}
**Files indexed:** {indexed_files}
**Chunks created:** {total_chunks}
**Embedding:** {emb_info} ({emb_dim} dimensions)
"""
            else:
                # Repository added but indexing failed
                return f"⚠️ Repository '{repo_name}' added (ID: {repo_id}) but indexing failed.\n\nError: {index_response.status_code}\n{index_response.text}"
        else:
            error_detail = response.json() if response.headers.get('content-type') == 'application/json' else response.text
            return f"❌ Error: {response.status_code}\n{error_detail}"

    except Exception as e:
        logger.error(f"Error adding repository: {e}")
        return f"❌ Error: {str(e)}"


def list_repositories():
    """List all repositories with embedding info."""
    try:
        response = client.get(f"{RAG_API_URL}/api/repos")
        if response.status_code == 200:
            repos = response.json()
            if not repos:
                return "No repositories indexed yet.", []

            output = "**Indexed Repositories:**\n\n"
            repo_choices = []
            for repo in repos:
                status = "🟢" if repo.get('is_active') else "⚪"
                repo_id = repo.get('id', '')
                repo_name = repo.get('name', 'Unknown')

                # Show embedding info
                emb_provider = repo.get('embedding_provider', 'unknown')
                emb_model = repo.get('embedding_model', 'unknown')
                emb_dim = repo.get('embedding_dimension', 'unknown')

                output += f"{status} **{repo_name}** - `{repo.get('path')}`\n"
                output += f"   Files: {repo.get('total_files', 0)} | Chunks: {repo.get('total_chunks', 0)}\n"
                output += f"   Embedding: {emb_provider}/{emb_model} ({emb_dim}D)\n"
                output += f"   ID: `{repo_id}`\n\n"

                # Add to dropdown choices: display name + ID for selection
                repo_choices.append(f"{repo_name} ({repo_id})")

            return output, repo_choices
        else:
            return f"Error: {response.status_code}", []
    except Exception as e:
        logger.error(f"Error listing repositories: {e}")
        return f"Error: {str(e)}", []


def reindex_repository(repo_selection: str, emb_provider: str, emb_model: str):
    """Re-index an existing repository with embedding choice."""
    try:
        if not repo_selection:
            return "❌ Please select a repository to re-index"

        # Extract repo_id from selection (format: "name (repo_id)")
        repo_id = repo_selection.split('(')[-1].rstrip(')')

        logger.info(f"Re-indexing repository {repo_id} with {emb_provider}/{emb_model}")
        index_payload = {"force_reindex": True, "embedding_provider": emb_provider}

        # Only send embedding_model if it's not the default
        if emb_model not in ["sentence-transformers/all-MiniLM-L6-v2", ""]:
            index_payload["embedding_model"] = emb_model

        response = client.post(
            f"{RAG_API_URL}/api/repos/{repo_id}/index",
            json=index_payload
        )

        if response.status_code == 200:
            data = response.json()
            indexed_files = data.get('indexed_files', 0)
            total_chunks = data.get('total_chunks', 0)
            emb_info = f"{data.get('embedding_provider', 'unknown')}/{data.get('embedding_model', 'unknown')}"
            emb_dim = data.get('embedding_dimension', 'unknown')

            return f"""✅ Repository re-indexed successfully!

**Files indexed:** {indexed_files}
**Chunks created:** {total_chunks}
**Embedding:** {emb_info} ({emb_dim} dimensions)
"""
        else:
            return f"❌ Re-indexing failed: {response.status_code}\n{response.text}"

    except Exception as e:
        logger.error(f"Error re-indexing repository: {e}")
        return f"❌ Error: {str(e)}"


def delete_repository(repo_selection: str):
    """Delete a repository."""
    try:
        if not repo_selection:
            return "❌ Please select a repository to delete"

        # Extract repo_id from selection
        repo_id = repo_selection.split('(')[-1].rstrip(')')

        logger.info(f"Deleting repository {repo_id}")
        response = client.delete(f"{RAG_API_URL}/api/repos/{repo_id}")

        if response.status_code == 200:
            return f"✅ Repository deleted successfully!"
        else:
            return f"❌ Delete failed: {response.status_code}\n{response.text}"

    except Exception as e:
        logger.error(f"Error deleting repository: {e}")
        return f"❌ Error: {str(e)}"


def check_codex_status():
    """Check Codex CLI status."""
    try:
        response = client.get(f"{RAG_API_URL}/api/codex/status")
        if response.status_code == 200:
            data = response.json()

            status_parts = ["**Codex CLI Status:**\n"]

            if data.get('installed'):
                status_parts.append(f"✅ **Installed**: {data.get('version', 'Unknown version')}")
            else:
                status_parts.append("❌ **Not Installed**")

            if data.get('authenticated'):
                status_parts.append("\n✅ **Authenticated**: Ready to use")
            elif data.get('authenticated') is False:
                status_parts.append("\n❌ **Not Authenticated**")
            else:
                status_parts.append("\n⚠️ **Authentication Status**: Unknown")

            if data.get('error'):
                status_parts.append(f"\n\n**Error**: {data.get('error')}")

            return "\n".join(status_parts)
        else:
            return f"❌ Failed to check Codex status: {response.status_code}"
    except Exception as e:
        logger.error(f"Error checking Codex status: {e}")
        return f"❌ Error: {str(e)}"


def query_rag(message: str, history):
    """Query the RAG API."""
    if not message.strip():
        return history

    try:
        response = client.post(
            f"{RAG_API_URL}/api/query",
            json={"query": message, "top_k": 10}
        )

        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', 'No answer generated')
            sources = data.get('sources', [])

            formatted = f"{answer}\n\n**Sources:**\n"
            for i, src in enumerate(sources[:5], 1):
                file_path = src.get('file_path', 'Unknown')
                formatted += f"{i}. `{file_path}`\n"

            # Gradio 6.x expects messages with 'role' and 'content' (array of content blocks)
            history.append({"role": "user", "content": [{"type": "text", "text": message}]})
            history.append({"role": "assistant", "content": [{"type": "text", "text": formatted}]})
        else:
            history.append({"role": "user", "content": [{"type": "text", "text": message}]})
            history.append({"role": "assistant", "content": [{"type": "text", "text": f"❌ Error: {response.status_code}"}]})
    except Exception as e:
        logger.error(f"Query error: {e}")
        history.append({"role": "user", "content": [{"type": "text", "text": message}]})
        history.append({"role": "assistant", "content": [{"type": "text", "text": f"❌ Error: {str(e)}"}]})

    return history


# Create Gradio 6.x compatible interface
demo = gr.Blocks(title="Git RAG Chat")

with demo:
    gr.Markdown("# 🤖 Git RAG Chat\nQuery your Git repositories using natural language")

    gr.Markdown("## 💬 Chat Interface")

    chatbot = gr.Chatbot(height=400)
    msg = gr.Textbox(placeholder="Ask about your code...", label="Your Question", lines=2)

    with gr.Row():
        submit = gr.Button("Send", variant="primary")
        clear = gr.Button("Clear")

    gr.Markdown("## 📁 Repository Management")

    with gr.Accordion("⚙️ Advanced Indexing Options", open=False):
        gr.Markdown("### Embedding Model Selection")
        embedding_provider = gr.Radio(
            choices=["local", "openai"],
            value="local",
            label="Embedding Provider",
            info="Local: Fast, free, offline (384-dim) | OpenAI: High quality, API cost (3072-dim)"
        )

        embedding_model = gr.Dropdown(
            choices=[
                "sentence-transformers/all-MiniLM-L6-v2",
                "sentence-transformers/all-mpnet-base-v2",
                "text-embedding-3-small",
                "text-embedding-3-large"
            ],
            value="sentence-transformers/all-MiniLM-L6-v2",
            label="Specific Model (Optional)",
            info="Leave default or choose a specific model"
        )

        gr.Markdown("""
**Model Comparison:**
- `all-MiniLM-L6-v2`: Fast, 384-dim, free, good for most use cases
- `all-mpnet-base-v2`: Better quality, 768-dim, free, slower
- `text-embedding-3-small`: OpenAI, 1536-dim, $0.02/1M tokens
- `text-embedding-3-large`: OpenAI, 3072-dim, $0.13/1M tokens (best quality)
        """)

    repo_path_input = gr.Textbox(
        label="Repository Path (Container Path)",
        placeholder="/repos  or  /host/Documents/your-repo-name",
        lines=1,
        info="💡 Use container paths: /repos or /host/Documents/[folder]"
    )
    add_btn = gr.Button("Add & Index Repository", variant="primary")
    add_status = gr.Textbox(label="Status", lines=2, interactive=False)

    gr.Markdown("### Existing Repositories")
    repos_list = gr.Markdown("Loading...")

    gr.Markdown("### Manage Existing Repository")
    repo_dropdown = gr.Dropdown(
        label="Select Repository",
        choices=[],
        interactive=True
    )

    with gr.Row():
        refresh_btn = gr.Button("Refresh List", variant="secondary")
        reindex_btn = gr.Button("Re-Index Selected", variant="primary")
        delete_btn = gr.Button("Delete Selected", variant="stop")

    manage_status = gr.Textbox(label="Management Status", lines=2, interactive=False)

    gr.Markdown("## 🔧 Codex CLI Status")
    codex_status_display = gr.Markdown("Checking Codex status...")
    with gr.Row():
        check_codex_btn = gr.Button("Check Codex Status", variant="secondary")

    # Event handlers
    def respond(message, history):
        return query_rag(message, history), ""

    def refresh_repos():
        """Refresh repository list and update dropdown."""
        repos_text, repo_choices = list_repositories()
        return repos_text, gr.Dropdown(choices=repo_choices)

    submit.click(respond, [msg, chatbot], [chatbot, msg])
    msg.submit(respond, [msg, chatbot], [chatbot, msg])
    clear.click(lambda: [], None, chatbot)
    add_btn.click(add_repository, [repo_path_input, embedding_provider, embedding_model], [add_status])
    refresh_btn.click(refresh_repos, outputs=[repos_list, repo_dropdown])
    reindex_btn.click(reindex_repository, [repo_dropdown, embedding_provider, embedding_model], [manage_status])
    delete_btn.click(delete_repository, [repo_dropdown], [manage_status])
    check_codex_btn.click(check_codex_status, outputs=[codex_status_display])

    # Load repositories and Codex status on startup
    demo.load(refresh_repos, outputs=[repos_list, repo_dropdown])
    demo.load(check_codex_status, outputs=[codex_status_display])

    gr.Markdown("---\n💻 **Git RAG Chat** | Powered by ChromaDB + Gradio + Codex CLI")


if __name__ == "__main__":
    logger.info("Starting Git RAG Chat UI...")
    logger.info(f"RAG API URL: {RAG_API_URL}")
    demo.launch(server_name="0.0.0.0", server_port=GRADIO_SERVER_PORT)
