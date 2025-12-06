"""API routes for RAG pipeline."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
import logging

from ..config import get_settings, Settings
from ..db.metadata_db import MetadataDB
from ..core.git_ops import GitOperations
from ..core.vector_store import VectorStore
from ..core.embedder import Embedder
from ..indexing.indexer import RepositoryIndexer
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
    return VectorStore(
        host=settings.chroma_host,
        port=settings.chroma_port,
        embedding_model=settings.embedding_model
    )


def get_embedder() -> Embedder:
    """Get embedder instance."""
    settings = get_settings()
    return Embedder(model_name=settings.embedding_model)


def get_indexer(
    db: MetadataDB = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store),
    embedder: Embedder = Depends(get_embedder)
) -> RepositoryIndexer:
    """Get indexer instance."""
    return RepositoryIndexer(
        metadata_db=db,
        vector_store=vector_store,
        embedder=embedder
    )


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
    request: IndexingRequest = None,
    indexer: RepositoryIndexer = Depends(get_indexer),
    db: MetadataDB = Depends(get_db)
):
    """Trigger repository indexing."""
    repo = db.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        force_reindex = request.force_reindex if request else False

        # Run full indexing
        result = indexer.index_repository(
            repo_id=repo_id,
            repo_path=repo['path'],
            force_reindex=force_reindex
        )

        return {
            "message": "Indexing completed",
            "repo_id": repo_id,
            "indexed_files": result['indexed_files'],
            "total_chunks": result['total_chunks'],
            "status": result['status']
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
    db: MetadataDB = Depends(get_db)
):
    """Query the RAG system."""
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

    # TODO: Implement actual RAG query
    return QueryResponse(
        answer="Query functionality not yet implemented",
        sources=[],
        repo_id=repo_id
    )
