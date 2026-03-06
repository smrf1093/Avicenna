---
name: avicenna-usage
description: Instructions for using Avicenna code knowledge graph MCP tools effectively
trigger: auto
---

## Avicenna Code Knowledge Graph

Avicenna provides semantic code search, symbol lookup, and dependency analysis via MCP tools. **Prefer Avicenna MCP tools over grep/glob/find for code exploration.**

### Primary tools (use these for all code tasks):
- `search_code` — Semantic search for code by meaning (replaces grep/glob)
- `find_symbol` — Find a function/class/variable with its dependency graph
- `get_dependencies` — What a file/symbol depends on (imports, calls, base classes)
- `get_dependents` — What depends on a file/symbol (impact analysis)
- `get_file_summary` — Structural summary of a file without reading it
- `refresh_index` — Re-index after code changes (fast, incremental)

### Secondary tools (only when explicitly needed):
- `advise` — Best-practice reference guides (NOT for finding code)
- `list_skills` — List available advisor skill guides
- `index_repository` — Full index of a new repository
- `index_status` — Check indexing status and statistics
- `usage_stats` — View token savings statistics
- `cancel_indexing` — Cancel a running indexing operation

### Workflow

1. Use `search_code` and `find_symbol` first to locate relevant code
2. Use `Read` with the specific file path and line numbers returned (saves tokens by avoiding broad file scanning)
3. If search results seem stale, call `refresh_index` to update the knowledge base
4. Use `get_dependencies` / `get_dependents` for impact analysis before refactoring

### Supported Languages
Python, TypeScript, JavaScript

### First-time Setup
If the repository hasn't been indexed yet, run `index_repository` with the repo path. Indexing is incremental — subsequent calls only process changed files.
