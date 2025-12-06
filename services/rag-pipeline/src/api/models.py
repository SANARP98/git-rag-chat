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
    repo_id: str = Field(..., description="Repository ID to index")
    job_type: str = Field("full", description="Job type: full, incremental, file, commit")
    target_path: Optional[str] = Field(None, description="Optional target file or commit hash")


class QueryRequest(BaseModel):
    """Request model for RAG query."""
    query: str = Field(..., description="User query")
    repo_id: Optional[str] = Field(None, description="Optional repository ID (uses active if not specified)")
    top_k: int = Field(5, description="Number of chunks to retrieve")


class QueryResponse(BaseModel):
    """Response model for RAG query."""
    answer: str
    sources: List[dict]
    repo_id: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    chromadb_connected: bool
