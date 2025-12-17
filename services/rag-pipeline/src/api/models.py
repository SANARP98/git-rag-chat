"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class RepositoryCreate(BaseModel):
    """Request model for creating a repository."""
    path: str = Field(..., description="Absolute path to Git repository")
    name: Optional[str] = Field(None, description="Optional repository name")


class RepositoryResponse(BaseModel):
    """Response model for repository data."""
    id: str
    name: str
    path: str
    chroma_collection_name: str
    created_at: datetime
    last_indexed_at: Optional[datetime] = None
    last_commit_hash: Optional[str] = None
    is_active: bool
    indexing_status: str
    total_chunks: int
    total_files: int
    # NEW: Iteration 2 - Embedding tracking
    embedding_provider: Optional[str] = Field(None, description="Embedding provider used (local/openai)")
    embedding_model: Optional[str] = Field(None, description="Embedding model name")
    embedding_dimension: Optional[int] = Field(None, description="Embedding dimension")


class RepositoryStats(BaseModel):
    """Repository statistics."""
    path: str
    branch: str
    total_commits: int
    total_files: int
    modified_files: int
    untracked_files: int
    latest_commit: Optional[dict] = None


class IndexingRequest(BaseModel):
    """Request model for triggering indexing."""
    force_reindex: bool = Field(False, description="Force full reindex even if already indexed")
    # NEW: Iteration 2 - Embedding selection
    embedding_provider: Optional[str] = Field(None, description="Embedding provider: 'local' or 'openai'")
    embedding_model: Optional[str] = Field(None, description="Specific embedding model name (optional)")


class QueryRequest(BaseModel):
    """Request model for RAG query."""
    query: str = Field(..., description="User query")
    repo_id: Optional[str] = Field(None, description="Optional repository ID (uses active if not specified)")
    n_results: Optional[int] = Field(10, description="Number of results to return")
    use_reranking: bool = Field(True, description="Whether to apply MMR reranking")
    language: Optional[str] = Field(None, description="Filter by programming language")
    file_path: Optional[str] = Field(None, description="Filter by file path")


class QueryResponse(BaseModel):
    """Response model for RAG query."""
    answer: str
    sources: List[dict]
    repo_id: str
    metadata: Optional[dict] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    chromadb_connected: bool
