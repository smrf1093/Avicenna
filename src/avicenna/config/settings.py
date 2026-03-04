"""Avicenna configuration loaded from environment variables / .env file."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class AvicennaSettings(BaseSettings):
    # LLM — set to a dummy value by default. Avicenna uses add_data_points()
    # (not cognify), so the LLM is never actually called. We only need this
    # to satisfy Cognee's startup validation. Override if you want to use
    # GRAPH_COMPLETION search type which does invoke the LLM.
    llm_provider: str = "ollama"
    llm_model: str = "llama3.1:8b"
    llm_endpoint: str = "http://localhost:11434/v1"
    llm_api_key: str = "placeholder-not-used"

    # Embeddings — FastEmbed runs locally on CPU, no API key, no Ollama needed.
    # This is the zero-config default. Override to use Ollama or OpenAI if preferred.
    embedding_provider: str = "fastembed"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # Only needed for Ollama embeddings (ignored by FastEmbed)
    embedding_endpoint: str = ""
    # Cognee requires this whenever embedding env vars are set.
    # For FastEmbed, this is not actually used but must be present.
    huggingface_tokenizer: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Storage (all file-based, no external services)
    vector_db_provider: str = "lancedb"
    graph_database_provider: str = "sqlite"
    db_provider: str = "sqlite"

    # Avicenna-specific
    avicenna_data_dir: str = "~/.avicenna"
    avicenna_max_file_size_kb: int = 500
    avicenna_batch_size: int = 200

    # Advisor
    avicenna_advisor_enabled: bool = True
    avicenna_advisor_min_similarity: float = 0.3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def data_dir(self) -> Path:
        return Path(self.avicenna_data_dir).expanduser()


_settings: AvicennaSettings | None = None


def get_settings() -> AvicennaSettings:
    global _settings
    if _settings is None:
        _settings = AvicennaSettings()
    return _settings


def apply_cognee_env(settings: AvicennaSettings | None = None) -> None:
    """Push Avicenna settings into environment variables that Cognee reads."""
    s = settings or get_settings()
    env_map = {
        "LLM_PROVIDER": s.llm_provider,
        "LLM_MODEL": s.llm_model,
        "LLM_ENDPOINT": s.llm_endpoint,
        "LLM_API_KEY": s.llm_api_key,
        "EMBEDDING_PROVIDER": s.embedding_provider,
        "EMBEDDING_MODEL": s.embedding_model,
        "EMBEDDING_DIMENSIONS": str(s.embedding_dimensions),
        "HUGGINGFACE_TOKENIZER": s.huggingface_tokenizer,
        "VECTOR_DB_PROVIDER": s.vector_db_provider,
        "GRAPH_DATABASE_PROVIDER": s.graph_database_provider,
        "DB_PROVIDER": s.db_provider,
    }
    # Only set non-empty values (e.g. skip EMBEDDING_ENDPOINT for FastEmbed)
    if s.embedding_endpoint:
        env_map["EMBEDDING_ENDPOINT"] = s.embedding_endpoint

    for key, value in env_map.items():
        os.environ.setdefault(key, value)
