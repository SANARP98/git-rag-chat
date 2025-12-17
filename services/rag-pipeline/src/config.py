"""Configuration management for RAG pipeline."""

import os
from typing import Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class ChromaDBConfig(BaseModel):
    """ChromaDB configuration."""
    host: str = "chromadb"
    port: int = 8000

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    provider: str = "codex"  # codex, ollama, chatgpt-enterprise
    codex_profile: Optional[str] = None
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "deepseek-coder:33b"
    temperature: float = 0.1
    max_tokens: int = 4096


class EmbeddingConfig(BaseModel):
    """Embedding model configuration."""
    provider: str = "local"  # "local" or "openai"
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_model: str = "text-embedding-3-large"
    cache_dir: str = "/app/data/models"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ChromaDB settings
    chroma_host: str = "chromadb"
    chroma_port: int = 8000

    # LLM settings
    llm_provider: str = "codex"
    codex_profile: Optional[str] = None
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "deepseek-coder:33b"

    # Embedding settings (Iteration 2)
    embedding_provider: str = "local"  # "local" or "openai"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_api_key: Optional[str] = None
    openai_embedding_model: str = "text-embedding-3-large"

    # Database settings
    metadata_db_path: str = "/app/data/metadata/repos.db"

    # Logging
    log_level: str = "INFO"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def chromadb_config(self) -> ChromaDBConfig:
        """Get ChromaDB configuration."""
        return ChromaDBConfig(
            host=self.chroma_host,
            port=self.chroma_port
        )

    @property
    def llm_config(self) -> LLMConfig:
        """Get LLM configuration."""
        return LLMConfig(
            provider=self.llm_provider,
            codex_profile=self.codex_profile,
            ollama_base_url=self.ollama_base_url,
            ollama_model=self.ollama_model
        )

    @property
    def embedding_config(self) -> EmbeddingConfig:
        """Get embedding configuration."""
        return EmbeddingConfig(
            provider=self.embedding_provider,
            model=self.embedding_model,
            openai_model=self.openai_embedding_model
        )


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
