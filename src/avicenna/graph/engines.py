"""Per-repo database engine management.

Each indexed repository gets its own Kuzu graph DB and LanceDB vector DB
under ``~/.avicenna/repos/{repo_id}/``.  This module lazily creates and
caches adapter instances so that the rest of the codebase can simply call
``get_engines(repo_id)`` without worrying about paths or singletons.

We bypass Cognee's factory functions (which are LRU-cached singletons)
and construct ``KuzuAdapter`` / ``LanceDBAdapter`` directly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from avicenna.config.settings import get_settings

logger = logging.getLogger(__name__)

# Cache: repo_id -> (KuzuAdapter, LanceDBAdapter)
_engine_cache: dict[str, tuple] = {}

# Shared embedding engine (stateless FastEmbed, expensive to load)
_embedding_engine = None


def repo_db_dir(repo_id: str) -> Path:
    """Return ``~/.avicenna/repos/{repo_id}/``, creating it if needed."""
    d = get_settings().data_dir / "repos" / repo_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_embedding_engine():
    """Return the shared FastEmbed embedding engine singleton."""
    global _embedding_engine
    if _embedding_engine is None:
        from cognee.infrastructure.databases.vector.embeddings import (
            get_embedding_engine as cognee_get_embedding_engine,
        )

        _embedding_engine = cognee_get_embedding_engine()
    return _embedding_engine


async def get_engines(repo_id: str):
    """Return ``(graph_adapter, vector_adapter)`` for a specific repo.

    Adapters are lazily created and cached for the lifetime of the process.
    """
    if repo_id in _engine_cache:
        return _engine_cache[repo_id]

    rd = repo_db_dir(repo_id)
    graph_path = str(rd / "graph")
    vector_path = str(rd / "vectors.lancedb")

    from cognee.infrastructure.databases.graph.kuzu.adapter import KuzuAdapter

    graph = KuzuAdapter(db_path=graph_path)
    if hasattr(graph, "initialize"):
        await graph.initialize()

    from cognee.infrastructure.databases.vector.lancedb.LanceDBAdapter import (
        LanceDBAdapter,
    )

    emb = _get_embedding_engine()
    vec = LanceDBAdapter(url=vector_path, api_key=None, embedding_engine=emb)

    _engine_cache[repo_id] = (graph, vec)
    logger.info("Created engines for repo %s at %s", repo_id, rd)
    return graph, vec


async def get_all_engines() -> dict[str, tuple]:
    """Return engines for every repo that has a DB directory.

    Scans ``~/.avicenna/repos/*/`` and lazily instantiates adapters for
    any repo_id not already cached.  Used for cross-repo search fan-out.
    """
    repos_dir = get_settings().data_dir / "repos"
    if not repos_dir.exists():
        return {}

    for child in repos_dir.iterdir():
        if child.is_dir() and child.name not in _engine_cache:
            # Only instantiate if the graph dir actually exists (was indexed)
            if (child / "graph").exists():
                await get_engines(child.name)

    return dict(_engine_cache)
