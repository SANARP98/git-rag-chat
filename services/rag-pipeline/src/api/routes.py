"""API routes for RAG pipeline."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional
import logging

from ..config import get_settings, Settings
from ..db.metadata_db import MetadataDB
from ..core.git_ops import GitOperations
from ..core.vector_store import VectorStore
from ..core.embedder import BaseEmbedder, create_embedder
from ..indexing.indexer import RepositoryIndexer
from ..retrieval.retriever import CodeRetriever
from ..retrieval.reranker import Reranker
from ..retrieval.context import ContextAssembler
from ..llm.factory import LLMFactory
from ..llm.base import LLMError
from .models import (
    RepositoryCreate,
    RepositoryResponse,
    RepositoryStats,
    IndexingRequest,
    QueryRequest,
    QueryResponse,
    HealthResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db() -> MetadataDB:
    """Get database instance."""
    settings = get_settings()
    return MetadataDB(settings.metadata_db_path)


def get_vector_store() -> VectorStore:
    """Get vector store instance."""
    settings = get_settings()
    # Don't pass embedding_model when using OpenAI or other pre-computed embeddings
    # ChromaDB's SentenceTransformer function is only needed for local embeddings
    embedding_model = None if settings.embedding_provider == "openai" else settings.embedding_model
    return VectorStore(
        host=settings.chroma_host,
        port=settings.chroma_port,
        embedding_model=embedding_model
    )


def get_embedder() -> BaseEmbedder:
    """Get embedder instance."""
    settings = get_settings()
    kwargs = {}
    if settings.embedding_provider == "openai":
        kwargs["api_key"] = settings.openai_api_key
        model_name = settings.openai_embedding_model
    else:
        model_name = settings.embedding_model

    return create_embedder(
        provider=settings.embedding_provider,
        model_name=model_name,
        **kwargs
    )


def get_indexer(
    db: MetadataDB = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    embedder: BaseEmbedder = Depends(get_embedder)
) -> RepositoryIndexer:
    """Get indexer instance."""
    return RepositoryIndexer(
        metadata_db=db,
        vector_store=vector_store,
        embedder=embedder
    )


def get_retriever(
    vector_store: VectorStore = Depends(get_vector_store),
    embedder: BaseEmbedder = Depends(get_embedder)
) -> CodeRetriever:
    """Get retriever instance."""
    return CodeRetriever(
        vector_store=vector_store,
        embedder=embedder
    )


def get_reranker(embedder: BaseEmbedder = Depends(get_embedder)) -> Reranker:
    """Get reranker instance."""
    return Reranker(embedder=embedder)


def get_context_assembler() -> ContextAssembler:
    """Get context assembler instance."""
    return ContextAssembler(max_tokens=4000)


def get_llm_provider(settings: Settings = Depends(get_settings)):
    """Get LLM provider instance."""
    return LLMFactory.create_from_settings(settings)


@router.get("/health", response_model=HealthResponse)
async def health_check(
    settings: Settings = Depends(get_settings),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Health check endpoint."""
    # Check ChromaDB connection
    try:
        vector_store.client.heartbeat()
        chromadb_connected = True
    except Exception as e:
        logger.error(f"ChromaDB health check failed: {e}")
        chromadb_connected = False

    return HealthResponse(
        status="healthy" if chromadb_connected else "degraded",
        version="0.1.0",
        chromadb_connected=chromadb_connected
    )


@router.get("/codex/status")
async def codex_status():
    """Check Codex CLI availability and authentication status."""
    import subprocess
    import json as json_lib

    try:
        # Check if codex is installed
        version_result = subprocess.run(
            ['codex', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if version_result.returncode != 0:
            return {
                "installed": False,
                "authenticated": False,
                "version": None,
                "error": "Codex CLI not found"
            }

        version = version_result.stdout.strip()

        # Try a simple test to check authentication
        # Note: --dangerously-bypass-approvals-and-sandbox is required in Docker containers
        test_result = subprocess.run(
            ['codex', 'exec', '--skip-git-repo-check', '--dangerously-bypass-approvals-and-sandbox', '--json', 'echo test'],
            capture_output=True,
            text=True,
            timeout=15
        )

        authenticated = test_result.returncode == 0
        error_msg = None

        if not authenticated:
            stderr = test_result.stderr
            if "403" in stderr or "Unauthorized" in stderr:
                error_msg = "Not authenticated. Please run 'codex' on host to login."
            else:
                error_msg = stderr[:200] if stderr else "Unknown authentication error"

        return {
            "installed": True,
            "authenticated": authenticated,
            "version": version,
            "error": error_msg
        }

    except subprocess.TimeoutExpired:
        return {
            "installed": True,
            "authenticated": None,
            "version": None,
            "error": "Codex CLI timeout - may be waiting for input"
        }
    except FileNotFoundError:
        return {
            "installed": False,
            "authenticated": False,
            "version": None,
            "error": "Codex CLI not installed in container"
        }
    except Exception as e:
        return {
            "installed": None,
            "authenticated": None,
            "version": None,
            "error": str(e)
        }


@router.post("/repos", response_model=RepositoryResponse)
async def create_repository(
    repo_data: RepositoryCreate,
    db: MetadataDB = Depends(get_db)
):
    """Add a new repository to track."""
    try:
        # Validate Git repository
        if not GitOperations.is_git_repository(repo_data.path):
            raise HTTPException(status_code=400, detail="Path is not a valid Git repository")

        # Check if repository already exists
        existing = db.get_repository_by_path(repo_data.path)
        if existing:
            raise HTTPException(status_code=409, detail="Repository already exists")

        # Add repository
        repo_id = db.add_repository(repo_data.path, repo_data.name)
        repo = db.get_repository(repo_id)

        return RepositoryResponse(**repo)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos", response_model=List[RepositoryResponse])
async def list_repositories(db: MetadataDB = Depends(get_db)):
    """List all repositories."""
    try:
        repos = db.list_repositories()
        return [RepositoryResponse(**repo) for repo in repos]
    except Exception as e:
        logger.error(f"Error listing repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos/{repo_id}", response_model=RepositoryResponse)
async def get_repository(repo_id: str, db: MetadataDB = Depends(get_db)):
    """Get repository details."""
    repo = db.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepositoryResponse(**repo)


@router.put("/repos/{repo_id}/activate")
async def activate_repository(repo_id: str, db: MetadataDB = Depends(get_db)):
    """Set a repository as active."""
    repo = db.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    db.set_active_repository(repo_id)
    return {"message": "Repository activated", "repo_id": repo_id}


@router.delete("/repos/{repo_id}")
async def delete_repository(
    repo_id: str,
    db: MetadataDB = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Delete a repository."""
    repo = db.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        # Delete from ChromaDB
        collection_name = repo['chroma_collection_name']
        vector_store.delete_collection(collection_name)
        logger.info(f"Deleted ChromaDB collection: {collection_name}")
    except Exception as e:
        logger.error(f"Failed to delete ChromaDB collection: {e}")

    # Delete from metadata database
    db.delete_repository(repo_id)
    return {"message": "Repository deleted", "repo_id": repo_id}


@router.get("/repos/{repo_id}/stats", response_model=RepositoryStats)
async def get_repository_stats(repo_id: str, db: MetadataDB = Depends(get_db)):
    """Get repository statistics."""
    repo = db.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        git_ops = GitOperations(repo["path"])
        stats = git_ops.get_repo_stats()
        return RepositoryStats(**stats)
    except Exception as e:
        logger.error(f"Error getting repository stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repos/{repo_id}/index")
async def trigger_indexing(
    repo_id: str,
    request: Optional[IndexingRequest] = None,
    db: MetadataDB = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Trigger repository indexing with optional embedding provider selection."""
    repo = db.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        settings = get_settings()
        force_reindex = request.force_reindex if request else False

        # Get embedding provider from request or use default from settings
        embedding_provider = request.embedding_provider if request and request.embedding_provider else settings.embedding_provider
        embedding_model = request.embedding_model if request and request.embedding_model else None

        # Create embedder with specified provider
        if embedding_provider == "openai":
            embedder = create_embedder(
                provider="openai",
                model_name=embedding_model or settings.openai_embedding_model,
                api_key=settings.openai_api_key
            )
        else:
            embedder = create_embedder(
                provider="local",
                model_name=embedding_model or settings.embedding_model
            )

        logger.info(f"Using embedder: {embedding_provider}/{embedder.get_model_info()['model_name']}")

        # Create indexer with custom embedder
        indexer = RepositoryIndexer(
            metadata_db=db,
            vector_store=vector_store,
            embedder=embedder
        )

        # Run full indexing
        result = indexer.index_repository(
            repo_id=repo_id,
            repo_path=repo['path'],
            force_reindex=force_reindex
        )

        # Update repository with embedding info
        db.update_repository_embedding_info(
            repo_id=repo_id,
            embedding_provider=embedding_provider,
            embedding_model=embedder.get_model_info()['model_name'],
            embedding_dimension=embedder.get_embedding_dimension()
        )

        return {
            "message": "Indexing completed",
            "repo_id": repo_id,
            "indexed_files": result['indexed_files'],
            "total_chunks": result['total_chunks'],
            "status": result['status'],
            "embedding_provider": embedding_provider,
            "embedding_model": embedder.get_model_info()['model_name'],
            "embedding_dimension": embedder.get_embedding_dimension()
        }
    except Exception as e:
        logger.error(f"Error during indexing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repos/{repo_id}/index/file")
async def index_file(
    repo_id: str,
    file_path: str,
    indexer: RepositoryIndexer = Depends(get_indexer),
    db: MetadataDB = Depends(get_db)
):
    """Index a specific file in the repository."""
    repo = db.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        chunks_added = indexer.index_file(
            repo_id=repo_id,
            file_path=file_path,
            is_uncommitted=True
        )

        return {
            "message": "File indexed successfully",
            "file_path": file_path,
            "chunks_added": chunks_added
        }
    except Exception as e:
        logger.error(f"Error indexing file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repos/{repo_id}/index/incremental")
async def incremental_index(
    repo_id: str,
    indexer: RepositoryIndexer = Depends(get_indexer),
    db: MetadataDB = Depends(get_db)
):
    """Perform incremental indexing (only modified files)."""
    repo = db.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        result = indexer.incremental_index(repo_id)

        return {
            "message": "Incremental indexing completed",
            "repo_id": repo_id,
            "indexed_files": result['indexed_files'],
            "total_chunks": result['total_chunks'],
            "status": result['status']
        }
    except Exception as e:
        logger.error(f"Error during incremental indexing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repos/{repo_id}/index/status")
async def get_indexing_status(
    repo_id: str,
    indexer: RepositoryIndexer = Depends(get_indexer),
    db: MetadataDB = Depends(get_db)
):
    """Get indexing status and statistics for a repository."""
    repo = db.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        stats = indexer.get_indexing_stats(repo_id)
        return stats
    except Exception as e:
        logger.error(f"Error getting indexing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query(
    query_data: QueryRequest,
    db: MetadataDB = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    reranker: Reranker = Depends(get_reranker),
    context_assembler: ContextAssembler = Depends(get_context_assembler),
    llm_provider = Depends(get_llm_provider)
):
    """Query the RAG system with dynamic embedder matching repository's embedding."""
    # Get active repository if not specified
    if not query_data.repo_id:
        active_repo = db.get_active_repository()
        if not active_repo:
            raise HTTPException(status_code=400, detail="No active repository")
        repo_id = active_repo["id"]
    else:
        repo_id = query_data.repo_id
        repo = db.get_repository(repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

    try:
        # Get repository info
        repo = db.get_repository(repo_id)
        collection_name = repo['chroma_collection_name']

        # Create embedder matching the repository's embedding provider
        settings = get_settings()
        embedding_provider = repo.get('embedding_provider', 'local')
        embedding_model = repo.get('embedding_model')

        logger.info(f"Creating query embedder: {embedding_provider}/{embedding_model}")

        # Always use OpenAI embeddings (local embeddings no longer supported)
        if embedding_provider == "local":
            logger.warning(f"Repository was indexed with 'local' embeddings, but only 'openai' is supported now. Falling back to OpenAI.")
            embedding_provider = "openai"

        if embedding_provider == "openai":
            embedder = create_embedder(
                provider="openai",
                model_name=embedding_model if embedding_provider == "openai" else settings.openai_embedding_model,
                api_key=settings.openai_api_key
            )
        else:
            # This shouldn't happen anymore, but just in case
            raise ValueError(f"Unsupported embedding provider: {embedding_provider}. Only 'openai' is supported.")

        # Create retriever with matching embedder
        retriever = CodeRetriever(
            vector_store=vector_store,
            embedder=embedder
        )

        # Build filters from query parameters
        filters = {}
        if query_data.language:
            filters['language'] = query_data.language
        if query_data.file_path:
            filters['file_path'] = query_data.file_path

        # Retrieve relevant chunks
        logger.info(f"Querying: {query_data.query[:100]}")
        chunks = retriever.retrieve(
            collection_name=collection_name,
            query=query_data.query,
            n_results=query_data.n_results or 20,
            filters=filters if filters else None
        )

        if not chunks:
            return QueryResponse(
                answer="No relevant code found for your query. The repository may not be indexed yet.",
                sources=[],
                repo_id=repo_id,
                metadata={
                    'retrieved_chunks': 0,
                    'collection': collection_name
                }
            )

        # Apply reranking if requested
        if query_data.use_reranking:
            logger.info("Applying MMR reranking")
            chunks = reranker.mmr_rerank(
                chunks=chunks,
                lambda_param=0.5,
                top_k=query_data.n_results or 10
            )

        # Limit to requested number
        final_chunks = chunks[:query_data.n_results] if query_data.n_results else chunks

        # Check if query is about Git history and augment with actual Git data
        git_context = ""
        query_lower = query_data.query.lower()
        if any(keyword in query_lower for keyword in ['commit', 'git log', 'git history', 'latest change', 'recent change', 'what changed', 'changes in']):
            try:
                # Get latest commits
                import subprocess
                result = subprocess.run(
                    ['git', '-C', repo['path'], 'log', '-5', '--format=%H|%s|%an|%ar'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0 and result.stdout:
                    git_context = "\n\n# Actual Git History\n\nLatest 5 commits:\n\n"
                    commits = []
                    for line in result.stdout.strip().split('\n'):
                        hash_val, msg, author, date = line.split('|', 3)
                        git_context += f"- `{hash_val[:7]}` - {msg} (by {author}, {date})\n"
                        commits.append(hash_val[:7])

                    # If query asks about "latest commit" or "what changed", include the diff
                    if any(phrase in query_lower for phrase in ['latest commit', 'what changed', 'changes in', 'what did', 'functional improvement']):
                        logger.info("Adding diff for latest commit")
                        diff_result = subprocess.run(
                            ['git', '-C', repo['path'], 'show', '--stat', '--format=%B', commits[0]],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )

                        if diff_result.returncode == 0 and diff_result.stdout:
                            # Limit diff to first 1500 chars to avoid overwhelming the context
                            diff_text = diff_result.stdout[:1500]
                            if len(diff_result.stdout) > 1500:
                                diff_text += "\n... (diff truncated for brevity)"

                            git_context += f"\n\n## Latest Commit Details (`{commits[0]}`)\n\n```diff\n{diff_text}\n```\n"

                    logger.info(f"Added Git history context for query: {query_data.query[:50]}")
            except Exception as e:
                logger.warning(f"Failed to get Git history: {e}")

        # Assemble context for LLM
        context = context_assembler.assemble_context(
            chunks=final_chunks,
            query=query_data.query,
            max_chunks=10
        )

        # Add Git context if available
        if git_context:
            context = git_context + "\n\n" + context

        # Build prompt (for now, return context as answer)
        # In Phase 6, this will call the actual LLM
        prompt = context_assembler.assemble_prompt(
            chunks=final_chunks,
            query=query_data.query
        )

        # Inject Git context into prompt if available
        if git_context:
            prompt = prompt.replace("# Relevant Code Context\n\n", f"# Relevant Code Context\n\n{git_context}\n\n")

        # Build sources list
        sources = [
            {
                'file_path': chunk['file_path'],
                'chunk_type': chunk['chunk_type'],
                'name': chunk['name'],
                'start_line': chunk['start_line'],
                'end_line': chunk['end_line'],
                'similarity': chunk['similarity'],
                'code_preview': chunk['code'][:200] + '...' if len(chunk['code']) > 200 else chunk['code']
            }
            for chunk in final_chunks
        ]

        # Get metadata summary
        metadata_summary = context_assembler.build_metadata_summary(final_chunks)

        # Call LLM to generate answer
        try:
            logger.info("Calling LLM to generate answer")
            answer = await llm_provider.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=2000
            )
            logger.info(f"LLM generated {len(answer)} chars")

        except LLMError as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to context only
            answer = f"""# Error generating LLM response

{str(e)}

# Retrieved Code Context

{context}

---

Query: {query_data.query}
Retrieved: {len(final_chunks)} relevant code chunks from {metadata_summary['unique_files']} file(s)."""

        return QueryResponse(
            answer=answer,
            sources=sources,
            repo_id=repo_id,
            metadata={
                'retrieved_chunks': len(chunks),
                'final_chunks': len(final_chunks),
                'collection': collection_name,
                'reranking_applied': query_data.use_reranking,
                'summary': metadata_summary,
                'prompt_length': len(prompt),
                'llm_provider': llm_provider.get_model_info()['provider']
            }
        )

    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def query_stream(
    query_data: QueryRequest,
    db: MetadataDB = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    reranker: Reranker = Depends(get_reranker),
    context_assembler: ContextAssembler = Depends(get_context_assembler),
    llm_provider = Depends(get_llm_provider)
):
    """Query the RAG system with streaming response and dynamic embedder."""
    # Get active repository if not specified
    if not query_data.repo_id:
        active_repo = db.get_active_repository()
        if not active_repo:
            raise HTTPException(status_code=400, detail="No active repository")
        repo_id = active_repo["id"]
    else:
        repo_id = query_data.repo_id
        repo = db.get_repository(repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

    try:
        # Get repository info
        repo = db.get_repository(repo_id)
        collection_name = repo['chroma_collection_name']

        # Create embedder matching the repository's embedding provider
        settings = get_settings()
        embedding_provider = repo.get('embedding_provider', 'local')
        embedding_model = repo.get('embedding_model')

        # Always use OpenAI embeddings (local embeddings no longer supported)
        if embedding_provider == "local":
            logger.warning(f"Repository was indexed with 'local' embeddings, but only 'openai' is supported now. Falling back to OpenAI.")
            embedding_provider = "openai"

        if embedding_provider == "openai":
            embedder = create_embedder(
                provider="openai",
                model_name=embedding_model if embedding_provider == "openai" else settings.openai_embedding_model,
                api_key=settings.openai_api_key
            )
        else:
            # This shouldn't happen anymore, but just in case
            raise ValueError(f"Unsupported embedding provider: {embedding_provider}. Only 'openai' is supported.")

        # Create retriever with matching embedder
        retriever = CodeRetriever(
            vector_store=vector_store,
            embedder=embedder
        )

        # Build filters
        filters = {}
        if query_data.language:
            filters['language'] = query_data.language
        if query_data.file_path:
            filters['file_path'] = query_data.file_path

        # Retrieve chunks
        chunks = retriever.retrieve(
            collection_name=collection_name,
            query=query_data.query,
            n_results=query_data.n_results or 20,
            filters=filters if filters else None
        )

        if not chunks:
            async def error_stream():
                yield "No relevant code found for your query."
            return StreamingResponse(error_stream(), media_type="text/plain")

        # Apply reranking
        if query_data.use_reranking:
            chunks = reranker.mmr_rerank(chunks, lambda_param=0.5, top_k=query_data.n_results or 10)

        # Limit chunks
        final_chunks = chunks[:query_data.n_results] if query_data.n_results else chunks

        # Assemble prompt
        prompt = context_assembler.assemble_prompt(chunks=final_chunks, query=query_data.query)

        # Stream LLM response
        async def generate_stream():
            try:
                async for chunk in llm_provider.generate_stream(prompt=prompt, temperature=0.1, max_tokens=2000):
                    yield chunk
            except LLMError as e:
                yield f"\n\n[Error: {str(e)}]"

        return StreamingResponse(generate_stream(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Streaming query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
