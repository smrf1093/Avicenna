<!-- avicenna:start -->
## Avicenna Code Knowledge Graph

This project is indexed by Avicenna, a code knowledge graph MCP extension.

**Prefer Avicenna MCP tools over grep/glob/find for code exploration:**

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

**Workflow**: Use `search_code` and `find_symbol` first to locate relevant code, then use `Read` with the specific file path and line numbers returned. This saves tokens by avoiding broad file scanning.

If search results seem stale, call `refresh_index` to update the knowledge base.
<!-- avicenna:end -->
