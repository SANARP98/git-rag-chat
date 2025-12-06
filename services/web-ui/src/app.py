"""Gradio web UI for Git RAG Chat."""

import os
import logging
from typing import List, Tuple, Optional
import gradio as gr
from dotenv import load_dotenv

from components.chat import ChatInterface
from components.repo_manager import RepositoryManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
RAG_API_URL = os.getenv('RAG_API_URL', 'http://rag-pipeline:8000')
GRADIO_SERVER_PORT = int(os.getenv('GRADIO_SERVER_PORT', '7860'))
GRADIO_ALLOWED_PATHS = os.getenv('GRADIO_ALLOWED_PATHS', '').split(',')
GRADIO_ALLOWED_PATHS = [p.strip() for p in GRADIO_ALLOWED_PATHS if p.strip()]

# Initialize components
chat_interface = ChatInterface(rag_api_url=RAG_API_URL)
repo_manager = RepositoryManager(
    rag_api_url=RAG_API_URL,
    allowed_paths=GRADIO_ALLOWED_PATHS
)


def validate_path_realtime(repo_path: str) -> str:
    """Real-time path validation."""
    return repo_manager.validate_path(repo_path)


def add_repository(repo_path: str) -> Tuple[str, str]:
    """Add and index repository."""
    status, info, success = repo_manager.add_repository(repo_path)
    return status, info


def get_indexing_status() -> str:
    """Get current repository indexing status."""
    return repo_manager.get_indexing_status()


def list_repositories() -> str:
    """List all repositories."""
    return repo_manager.list_repositories()


def chat_query(
    message: str,
    history: List[Tuple[str, str]],
    temperature: float,
    max_results: int
) -> Tuple[str, List[Tuple[str, str]]]:
    """Process chat query."""
    return chat_interface.query(
        message=message,
        history=history,
        repo_id=repo_manager.current_repo_id,
        temperature=temperature,
        max_results=max_results
    )


def clear_chat() -> List[Tuple[str, str]]:
    """Clear chat history."""
    return chat_interface.clear_history()


# Create Gradio Interface
with gr.Blocks(
    title="Git RAG Chat",
    theme=gr.themes.Soft(),
    css="""
    .container { max-width: 1200px; margin: auto; }
    .repo-info { background-color: #f0f0f0; padding: 15px; border-radius: 5px; }
    """,
    analytics_enabled=False,
    fill_height=True
) as app:
    gr.Markdown(
        """
        # 🤖 Git RAG Chat

        Query your Git repositories using natural language with RAG (Retrieval-Augmented Generation).
        """
    )

    with gr.Tabs():
        # Tab 1: Chat Interface
        with gr.Tab("💬 Chat"):
            with gr.Row():
                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(
                        label="Conversation",
                        height=500,
                        show_copy_button=True,
                        render_markdown=True
                    )

                    with gr.Row():
                        msg = gr.Textbox(
                            label="Your Question",
                            placeholder="Ask about your code... (e.g., 'How does authentication work?')",
                            lines=2,
                            scale=4
                        )
                        submit_btn = gr.Button("Send", variant="primary", scale=1)

                    with gr.Row():
                        clear_btn = gr.Button("Clear Chat", variant="secondary")

                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Query Settings")

                    temperature_slider = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=0.1,
                        step=0.1,
                        label="Temperature",
                        info="Lower = more focused, Higher = more creative"
                    )

                    max_results_slider = gr.Slider(
                        minimum=1,
                        maximum=20,
                        value=10,
                        step=1,
                        label="Max Results",
                        info="Number of code chunks to retrieve"
                    )

                    gr.Markdown("### 📊 Status")
                    status_display = gr.Markdown("No repository selected")
                    refresh_status_btn = gr.Button("Refresh Status", size="sm")

            # Chat event handlers
            submit_btn.click(
                chat_query,
                inputs=[msg, chatbot, temperature_slider, max_results_slider],
                outputs=[msg, chatbot]
            )

            msg.submit(
                chat_query,
                inputs=[msg, chatbot, temperature_slider, max_results_slider],
                outputs=[msg, chatbot]
            )

            clear_btn.click(clear_chat, outputs=[chatbot])

            refresh_status_btn.click(
                get_indexing_status,
                outputs=[status_display]
            )

        # Tab 2: Repository Management
        with gr.Tab("📁 Repository"):
            gr.Markdown("### Add New Repository")

            with gr.Row():
                with gr.Column(scale=3):
                    repo_path_input = gr.Textbox(
                        label="Repository Path",
                        placeholder="Enter full path to Git repository (e.g., /Users/name/my-project)",
                        lines=1,
                        info="Paste the full path to your local Git repository"
                    )

                    validation_status = gr.Textbox(
                        label="Validation Status",
                        interactive=False,
                        lines=1
                    )

                    with gr.Row():
                        validate_btn = gr.Button("Add & Index Repository", variant="primary")
                        clear_path_btn = gr.Button("Clear", variant="secondary")

                with gr.Column(scale=2):
                    if GRADIO_ALLOWED_PATHS:
                        allowed_info = "\n".join([f"- `{p}`" for p in GRADIO_ALLOWED_PATHS])
                        gr.Markdown(
                            f"""
                            ### ℹ️ Allowed Directories

                            For security, only paths under these directories are allowed:

                            {allowed_info}
                            """
                        )

            repo_info_display = gr.Markdown("", elem_classes=["repo-info"])

            gr.Markdown("---")
            gr.Markdown("### Existing Repositories")

            repos_list_display = gr.Markdown("Loading...")
            refresh_repos_btn = gr.Button("Refresh List", variant="secondary")

            # Repository event handlers
            repo_path_input.change(
                validate_path_realtime,
                inputs=[repo_path_input],
                outputs=[validation_status]
            )

            validate_btn.click(
                add_repository,
                inputs=[repo_path_input],
                outputs=[validation_status, repo_info_display]
            )

            clear_path_btn.click(
                lambda: ("", "", ""),
                outputs=[repo_path_input, validation_status, repo_info_display]
            )

            refresh_repos_btn.click(
                list_repositories,
                outputs=[repos_list_display]
            )

            # Load repositories on startup
            app.load(list_repositories, outputs=[repos_list_display])

        # Tab 3: Settings & Help
        with gr.Tab("⚙️ Settings"):
            gr.Markdown(
                f"""
                ### Configuration

                **RAG API URL:** `{RAG_API_URL}`

                **Server Port:** `{GRADIO_SERVER_PORT}`

                **Allowed Paths:** {', '.join([f'`{p}`' for p in GRADIO_ALLOWED_PATHS]) if GRADIO_ALLOWED_PATHS else 'All paths allowed (not recommended for production)'}

                ---

                ### How It Works

                1. **Add Repository**: Select a local Git repository to index
                2. **Indexing**: The system extracts code, creates embeddings, and stores them in ChromaDB
                3. **Query**: Ask questions in natural language
                4. **Retrieval**: The system finds relevant code chunks using semantic search
                5. **Generation**: LLM generates answers based on retrieved context

                ### Tips

                - **Be Specific**: Ask targeted questions about specific features or functions
                - **Use Context**: Mention file names or component names when relevant
                - **Adjust Settings**: Lower temperature for factual answers, higher for creative suggestions
                - **Check Sources**: Review the source code snippets provided with each answer

                ### Supported LLM Providers

                - **Codex CLI (ChatGPT Enterprise)**: Primary provider using GPT-4
                - **Ollama**: Offline fallback with local models (deepseek-coder, codellama)

                ### Troubleshooting

                - **No Response**: Check if RAG pipeline container is running
                - **Indexing Stuck**: Check file-watcher logs for errors
                - **Empty Results**: Repository might not be fully indexed yet
                """
            )

    gr.Markdown(
        """
        ---

        **Git RAG Chat** | Built with ChromaDB, sentence-transformers, and Gradio
        """
    )


def main():
    """Launch Gradio app."""
    logger.info("Starting Git RAG Chat UI...")
    logger.info(f"RAG API URL: {RAG_API_URL}")
    logger.info(f"Server Port: {GRADIO_SERVER_PORT}")
    logger.info(f"Allowed Paths: {GRADIO_ALLOWED_PATHS or 'All (unrestricted)'}")

    try:
        # Simple launch - Gradio handles Docker detection automatically
        app.launch(
            server_name="0.0.0.0",
            server_port=GRADIO_SERVER_PORT,
            share=False
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        chat_interface.close()
        repo_manager.close()
    except Exception as e:
        logger.error(f"Failed to start UI: {e}")
        raise


if __name__ == "__main__":
    main()
