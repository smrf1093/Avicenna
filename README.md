# Avicenna

Code knowledge graph MCP extension for Claude CLI. Reduces token usage by replacing brute-force file searching with intelligent, graph-aware code retrieval.

**Fully local and free** — no API keys, no Ollama, no external services. Uses FastEmbed for local CPU-based embeddings and file-based storage (LanceDB + Kuzu + SQLite).

## Quick Start

### 1. Install

```bash
# Requires Python 3.11-3.12 and Claude CLI
git clone https://github.com/YOUR_USERNAME/avicenna.git
cd avicenna
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Initialize for your project

```bash
python -m avicenna init /path/to/your/project
```

This single command:
- Registers Avicenna as an MCP server with Claude CLI (globally, works in all projects)
- Indexes your project's codebase into a knowledge graph
- Creates a `CLAUDE.md` in your project that tells Claude to prefer Avicenna tools

### 3. Verify

```bash
claude mcp list
# Should show: ✓ avicenna
```

### 4. Use

Open Claude CLI in your project — Avicenna tools are automatically available:

> "Search the codebase for authentication middleware"

> "Find the UserService class and show me its dependencies"

> "What files depend on the database module?"

Claude will use `search_code` and `find_symbol` instead of grep/glob, returning precise results with file paths and line numbers.

## How It Works

Avicenna pre-indexes your codebase into a knowledge graph using [Cognee](https://github.com/topoteretes/cognee) and [tree-sitter](https://tree-sitter.github.io/), then exposes targeted retrieval tools via MCP. Instead of Claude doing 10-30 file reads and grep calls per task, it queries the graph and gets back signatures, line numbers, and relationships — then fetches only what it needs.

```
Codebase --> tree-sitter parsing --> per-repo knowledge graph (vectors + graph DB)
                                              |
Claude CLI <-- MCP stdio <-- Avicenna MCP Server <-- vector search + graph queries
```

No separate LLM is needed. Avicenna writes directly to Kuzu (graph) and LanceDB (vectors) — no LLM is called during indexing. Embeddings are generated locally by FastEmbed. At search time, Claude itself (already running in your CLI) does all the reasoning.

### Per-Repository Isolation

Each indexed repository gets its own isolated database under `~/.avicenna/repos/{repo_id}/`:

```
~/.avicenna/repos/
├── a1b2c3d4e5f67890/     # Project A
│   ├── graph              # Kuzu graph database
│   └── vectors.lancedb/   # LanceDB vector database
├── f0e1d2c3b4a59876/     # Project B
│   ├── graph
│   └── vectors.lancedb/
└── ...
```

This means:
- **Parallel indexing** — different repos can be indexed concurrently (no shared lock)
- **Clean isolation** — corrupting or re-indexing one repo doesn't affect others
- **Scoped search** — queries target the active repo by default, avoiding cross-repo noise

## Supported Languages

- Python
- TypeScript / TSX
- JavaScript / JSX

## Prerequisites

- **Python 3.11 - 3.12** (recommended 3.12 — FastEmbed requires < 3.13, Cognee requires < 3.14)
- **Claude CLI** installed

That's it. No Ollama, no API keys, no external services.

### Setup Python with pyenv (if needed)

```bash
pyenv install 3.12.8
pyenv local 3.12.8
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `index_repository` | Parse and index a codebase (supports incremental updates) |
| `refresh_index` | Re-index only changed files — call after code edits |
| `search_code` | Semantic search across indexed code — replaces grep/glob |
| `find_symbol` | Find a function/class/variable with its dependency graph |
| `get_dependencies` | What does a file/symbol depend on (imports, calls, base classes) |
| `get_dependents` | What depends on a file/symbol (impact analysis) |
| `get_file_summary` | Structural summary of a file without reading full contents |
| `advise` | Get best-practice advice — frameworks, patterns, principles |
| `list_skills` | List all loaded advisor skills with metadata |
| `index_status` | Check indexing stats and pending changes |
| `usage_stats` | View token savings report (Avicenna vs traditional) |

### Token Reduction

Tools return **signatures, names, line numbers, and docstrings** — not full source code. Claude uses its built-in `Read` tool with precise line numbers only when it needs the full source. This typically reduces exploration tokens by 5-10x.

## CLI Commands

```bash
# Initialize Avicenna for a project (recommended)
python -m avicenna init /path/to/project

# Index a project (without MCP registration or CLAUDE.md)
python -m avicenna index /path/to/project

# Check indexing status
python -m avicenna status /path/to/project

# View token savings stats
python -m avicenna stats

# Start the MCP server (used internally by Claude CLI)
python -m avicenna serve
```

### Init options

```bash
# Skip indexing (only register MCP + create CLAUDE.md)
python -m avicenna init --skip-index /path/to/project

# Skip MCP registration (only index + create CLAUDE.md)
python -m avicenna init --skip-mcp /path/to/project
```

## Measuring Token Savings

Avicenna automatically tracks every search tool call and estimates how many tokens a traditional grep/read workflow would have used for the same query.

```bash
python -m avicenna stats

# === Avicenna Token Savings Report ===
#
#   Period:            Last 7 day(s)
#   Total tool calls:  47
#   Avicenna tokens:   3,842
#   Traditional est.:  28,650
#   Tokens saved:      24,808
#   Savings:           86.6%
```

Or ask Claude: *"Show me the Avicenna token savings stats"*

## Keeping the Knowledge Base Fresh

### Stale Detection (automatic)

Every search tool automatically checks if indexed files have changed. If they have, the response includes a `_stale` warning telling Claude to call `refresh_index`.

### `refresh_index` Tool (on-demand)

After making code edits, Claude (or you) can call `refresh_index` to re-index only the changed files. This is fast — it hashes files, detects what changed, and only re-parses those.

### File Watcher (automatic background)

When a repository is indexed, Avicenna automatically starts a file watcher (if `watchfiles` is installed). It monitors the repository for changes and triggers incremental re-indexing with a 2-second debounce.

```bash
pip install -e ".[watch]"
```

### How Incremental Indexing Works

Avicenna tracks SHA-256 content hashes per file in SQLite. On re-index:
- Only new/changed files are parsed and ingested
- Deleted files have their entities removed from the graph
- Unchanged files are skipped entirely

## Advisor Skills

Avicenna includes an extensible advisor system that provides best-practice guidance on frameworks, design patterns, and engineering principles. Claude can call the `advise` tool during planning or code review to get relevant guidance matched by semantic similarity.

### How It Works

Skills are `SKILL.md` files with YAML frontmatter + markdown body. When Claude calls `advise("how should I structure Django views?")`, Avicenna:

1. Embeds the query using FastEmbed (same engine as code search)
2. Computes cosine similarity against all loaded skill descriptions
3. Applies boosts for trigger phrase matches and detected project frameworks
4. Returns the best-matching skill's full content, plus metadata for secondary matches

### Built-in Skills

| Skill | Category | Description |
|-------|----------|-------------|
| `django` | framework | Project structure, views, models, ORM, DRF |
| `react` | framework | Components, hooks, state management, performance |
| `solid-principles` | principle | SRP, OCP, LSP, ISP, DIP with examples |
| `strategy-pattern` | pattern | When and how to use the Strategy pattern |

### Skill Format

Each skill is a directory containing a `SKILL.md`:

```yaml
---
name: my-skill
description: What this skill does and when to use it.
category: framework          # framework | principle | pattern | tool | custom
domains:                     # For conflict detection + matching
  - django
  - python
triggers:                    # Phrases that boost this skill's match score
  - "django views"
priority: 50                 # 0-100, higher wins conflicts
depends-on:                  # Auto-include these skills in results
  - solid-principles
metadata:
  author: my-team
  version: "1.0"
---

# My Skill

Markdown body with guidance, examples, and best practices.
```

### Adding Custom Skills

Skills are discovered from three locations (in priority order):

| Location | Source | Priority Boost |
|----------|--------|---------------|
| `{repo}/.avicenna/skills/` | Project-specific (team overrides) | +20 |
| `~/.avicenna/skills/` | User-installed (personal) | +10 |
| `src/avicenna/advisor/skills/` | Built-in (ships with Avicenna) | +0 |

To add a custom skill:

```bash
mkdir -p ~/.avicenna/skills/my-framework
# Create ~/.avicenna/skills/my-framework/SKILL.md with the format above
```

The skill name in frontmatter must match the directory name.

### Conflict Detection

- **Name collisions**: If two skills share the same name, the higher-priority one wins (project > user > built-in). A warning is logged.
- **Domain overlaps**: If two skills in the same category share >50% of their domains, a warning is flagged (non-fatal).

### Skill Composition

Skills can declare dependencies via `depends-on`. When the primary match has dependencies, those skills are automatically included in the response with a boosted score, ensuring Claude sees related guidance together (e.g., Django advice + SOLID principles).

## Configuration

All settings are in `.env` (see `.env.template`). **The defaults work with zero configuration.**

```bash
cp .env.template .env  # optional — only if you want to customize
```

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `fastembed` | Embedding provider (local, no API key) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `EMBEDDING_DIMENSIONS` | `384` | Embedding vector size |
| `VECTOR_DB_PROVIDER` | `lancedb` | Vector store (file-based) |
| `GRAPH_DATABASE_PROVIDER` | `kuzu` | Graph DB (file-based) |
| `DB_PROVIDER` | `sqlite` | Relational DB (file-based) |
| `AVICENNA_DATA_DIR` | `~/.avicenna` | Where indexes are stored |
| `AVICENNA_MAX_FILE_SIZE_KB` | `500` | Skip files larger than this |
| `AVICENNA_BATCH_SIZE` | `50` | DataPoints per ingestion batch |

### Optional: Higher Quality Embeddings with Ollama

```env
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text:latest
EMBEDDING_ENDPOINT=http://localhost:11434/api/embed
EMBEDDING_DIMENSIONS=768
HUGGINGFACE_TOKENIZER=nomic-ai/nomic-embed-text-v1.5
```

### Optional: Cloud Embeddings with OpenAI

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
EMBEDDING_API_KEY=sk-your-key-here
```

## Manual Setup (alternative to `init`)

If you prefer to set things up manually instead of using `python -m avicenna init`:

```bash
# Register with Claude CLI
claude mcp add avicenna -- /path/to/avicenna/.venv/bin/python -m avicenna serve

# Index your project
python -m avicenna index /path/to/your/project

# Create CLAUDE.md in your project (so Claude knows to use Avicenna)
# See the init command's output for the recommended CLAUDE.md content
```

## Architecture

```
src/avicenna/
├── config/settings.py          # Pydantic settings from .env
├── models/code_entities.py     # 6 DataPoint subclasses (CodeFile, CodeFunction, etc.)
├── parser/
│   ├── languages.py            # Language registry + tree-sitter grammar loading
│   ├── tree_sitter_parser.py   # Core parsing engine
│   └── queries/                # Tree-sitter S-expression patterns per language
├── indexer/
│   ├── file_discovery.py       # .gitignore-aware file walking
│   ├── file_hasher.py          # SHA-256 change detection
│   ├── incremental_state.py    # SQLite state tracking
│   ├── repository_indexer.py   # Orchestrator (per-repo locking)
│   └── watcher.py              # File watcher for auto re-indexing
├── graph/
│   ├── engines.py              # Per-repo Kuzu + LanceDB engine cache
│   ├── ingester.py             # ParseResult -> DataPoints -> direct Kuzu/LanceDB writes
│   ├── searcher.py             # Per-repo and cross-repo vector + graph queries
│   └── query_builder.py        # Tool params -> search queries
└── server/
    ├── mcp_server.py           # FastMCP server + tool registration
    ├── tools.py                # MCP tool implementations (repo-aware)
    └── formatters.py           # Token-efficient result formatting
```

## Development

```bash
pip install -e ".[dev]"
ruff check src/
pytest
```

## License

MIT
