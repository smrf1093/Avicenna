"""CLI entry points for Avicenna."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

import click

from avicenna.config.settings import apply_cognee_env

# --- CLAUDE.md template (between markers for idempotent updates) ---

_AVICENNA_MARKER_START = "<!-- avicenna:start -->"
_AVICENNA_MARKER_END = "<!-- avicenna:end -->"

_CLAUDE_MD_SECTION = """\
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
<!-- avicenna:end -->"""


def _register_mcp_server() -> bool:
    """Register Avicenna as a global MCP server in ~/.claude.json."""
    claude_json_path = Path.home() / ".claude.json"

    try:
        if claude_json_path.exists():
            config = json.loads(claude_json_path.read_text())
        else:
            config = {}
    except (json.JSONDecodeError, OSError) as e:
        click.echo(f"  Warning: Could not read {claude_json_path}: {e}", err=True)
        config = {}

    python_path = sys.executable
    mcp_entry = {
        "type": "stdio",
        "command": python_path,
        "args": ["-m", "avicenna", "serve"],
        "env": {},
    }

    if "mcpServers" not in config:
        config["mcpServers"] = {}
    config["mcpServers"]["avicenna"] = mcp_entry

    try:
        claude_json_path.write_text(json.dumps(config, indent=2) + "\n")
        return True
    except OSError as e:
        click.echo(f"  Error: Could not write {claude_json_path}: {e}", err=True)
        return False


def _update_claude_md(project_path: str) -> bool:
    """Create or update CLAUDE.md in the target project with Avicenna instructions."""
    claude_md_path = Path(project_path) / "CLAUDE.md"

    try:
        if claude_md_path.exists():
            content = claude_md_path.read_text()
            # Replace existing Avicenna section if present
            pattern = re.compile(
                re.escape(_AVICENNA_MARKER_START) + r".*?" + re.escape(_AVICENNA_MARKER_END),
                re.DOTALL,
            )
            if pattern.search(content):
                content = pattern.sub(_CLAUDE_MD_SECTION, content)
            else:
                # Append to existing file
                if not content.endswith("\n"):
                    content += "\n"
                content += "\n" + _CLAUDE_MD_SECTION + "\n"
        else:
            content = _CLAUDE_MD_SECTION + "\n"

        claude_md_path.write_text(content)
        return True
    except OSError as e:
        click.echo(f"  Error: Could not write {claude_md_path}: {e}", err=True)
        return False


@click.group()
def main():
    """Avicenna — Code knowledge graph for Claude CLI."""
    pass


@main.command()
@click.option(
    "--transport",
    default="stdio",
    type=click.Choice(["stdio", "http"]),
    help="MCP transport mode (default: stdio)",
)
@click.option("--port", default=8000, help="Port for HTTP transport (default: 8000)")
def serve(transport: str, port: int):
    """Start the Avicenna MCP server."""
    apply_cognee_env()
    from avicenna.server.mcp_server import run_server

    run_server(transport=transport)


@main.command()
@click.argument("path")
@click.option("--full", is_flag=True, help="Force full re-index (ignore incremental state)")
@click.option(
    "--languages", "-l", multiple=True, help="Languages to index (python, typescript, javascript)"
)
def index(path: str, full: bool, languages: tuple[str, ...]):
    """Index a code repository."""
    from avicenna.indexer.repository_indexer import is_server_running

    running, pid = is_server_running()
    if running:
        click.echo(
            f"Error: An Avicenna MCP server is already running (pid {pid}).\n"
            f"The Kuzu graph database only supports one process at a time.\n\n"
            f"To index from a running Claude session, use the index_repository\n"
            f"MCP tool instead of the CLI:\n\n"
            f"  Claude> Please index /path/to/project using Avicenna\n\n"
            f"Or close all Claude sessions using Avicenna first, then retry.",
            err=True,
        )
        raise SystemExit(1)

    apply_cognee_env()

    async def _run():
        from avicenna.indexer.repository_indexer import index_repository

        result = await index_repository(
            repo_path=path,
            incremental=not full,
            languages=list(languages) if languages else None,
        )
        click.echo(
            json.dumps(
                {
                    "status": "completed",
                    "repo_path": result.repo_path,
                    "new_files": result.new_files,
                    "changed_files": result.changed_files,
                    "deleted_files": result.deleted_files,
                    "unchanged_files": result.unchanged_files,
                    "total_entities": result.total_entities,
                    "duration_seconds": round(result.duration_seconds, 2),
                    "errors": result.errors[:10] if result.errors else [],
                },
                indent=2,
            )
        )

    asyncio.run(_run())


@main.command(name="init")
@click.argument("path")
@click.option(
    "--skip-index", is_flag=True, help="Skip indexing (only register MCP and create CLAUDE.md)"
)
@click.option("--skip-mcp", is_flag=True, help="Skip MCP registration in ~/.claude.json")
def init_project(path: str, skip_index: bool, skip_mcp: bool):
    """Initialize Avicenna for a project. Registers the MCP server, indexes
    the codebase, and creates a CLAUDE.md with usage instructions.

    This is the recommended one-command setup. Run this once per project:

        python -m avicenna init /path/to/your/project
    """
    project_path = os.path.abspath(path)

    if not os.path.isdir(project_path):
        click.echo(f"Error: {project_path} is not a directory.", err=True)
        raise SystemExit(1)

    # Check for running server before indexing
    if not skip_index:
        from avicenna.indexer.repository_indexer import is_server_running

        running, pid = is_server_running()
        if running:
            click.echo(
                f"\nWarning: Avicenna MCP server is running (pid {pid}). "
                f"Indexing will be skipped.\n"
                f"Use the index_repository tool from your Claude session instead.\n",
                err=True,
            )
            skip_index = True

    click.echo(f"\nAvicenna — Initializing for: {project_path}\n")

    # Step 1: Register MCP server
    if not skip_mcp:
        click.echo("[1/3] Registering MCP server with Claude CLI...")
        if _register_mcp_server():
            click.echo(f"  OK — Added to ~/.claude.json (using {sys.executable})")
        else:
            click.echo(
                "  FAILED — You can register manually: claude mcp add avicenna -- python -m avicenna serve"
            )
    else:
        click.echo("[1/3] Skipping MCP registration (--skip-mcp)")

    # Step 2: Create/update CLAUDE.md
    click.echo("[2/3] Creating CLAUDE.md with Avicenna instructions...")
    if _update_claude_md(project_path):
        click.echo(f"  OK — {project_path}/CLAUDE.md updated")
    else:
        click.echo("  FAILED — You can create CLAUDE.md manually")

    # Step 3: Index the project
    if not skip_index:
        click.echo("[3/3] Indexing codebase (this may take a moment)...")
        apply_cognee_env()

        async def _run_index():
            from avicenna.indexer.repository_indexer import index_repository

            return await index_repository(repo_path=project_path, incremental=True)

        try:
            result = asyncio.run(_run_index())
            total_files = result.new_files + result.changed_files + result.unchanged_files
            click.echo(
                f"  OK — {total_files} files, {result.total_entities} entities indexed in {result.duration_seconds:.1f}s"
            )
            if result.errors:
                click.echo(f"  Warnings: {len(result.errors)} file(s) had errors")
        except Exception as e:
            err_msg = str(e)
            if "Could not set lock" in err_msg:
                click.echo(
                    "  FAILED — Database is locked (another Avicenna instance may be running).\n"
                    "  Close other Claude CLI sessions using Avicenna, then run:\n"
                    f"    python -m avicenna index {project_path}"
                )
            else:
                click.echo(f"  FAILED — {err_msg}")
                click.echo(
                    f"  You can index manually later: python -m avicenna index {project_path}"
                )
    else:
        click.echo("[3/3] Skipping indexing (--skip-index)")

    # Summary
    click.echo("\nDone! Next steps:")
    click.echo("  1. Verify:  claude mcp list  (should show avicenna)")
    click.echo(f"  2. Use:     cd {project_path} && claude")
    click.echo("  3. Claude will automatically prefer Avicenna tools for code search\n")


@main.command()
@click.argument("path", required=False)
def status(path: str | None):
    """Show indexing status for a repository (or all repos)."""
    from avicenna.indexer.repository_indexer import get_index_status

    result = get_index_status(repo_path=path)
    click.echo(json.dumps(result, indent=2))


@main.command()
@click.option("--days", "-d", default=7, help="Number of days to show (default: 7)")
@click.option("--reset", is_flag=True, help="Reset all usage statistics")
def stats(days: int, reset: bool):
    """Show token usage statistics and savings report."""
    from avicenna.stats.tracker import get_tracker

    tracker = get_tracker()

    if reset:
        result = tracker.reset()
        click.echo(json.dumps(result, indent=2))
        return

    summary = tracker.get_summary(days=days)

    # Pretty-print the summary
    click.echo("\n=== Avicenna Token Savings Report ===\n")
    click.echo(f"  Period:            {summary['period']}")
    click.echo(f"  Total tool calls:  {summary['total_calls']}")
    click.echo(f"  Avicenna tokens:   {summary['total_avicenna_tokens']:,}")
    click.echo(f"  Traditional est.:  {summary['total_traditional_estimate']:,}")
    click.echo(f"  Tokens saved:      {summary['total_tokens_saved']:,}")
    click.echo(f"  Savings:           {summary['overall_savings']}")
    click.echo(f"\n  Lifetime calls:    {summary['lifetime_calls']}")
    click.echo(f"  Lifetime saved:    {summary['lifetime_saved']:,} tokens")

    if summary.get("daily"):
        click.echo("\n--- Daily Breakdown ---\n")
        click.echo(
            f"  {'Date':<12} {'Calls':>6} {'Avicenna':>10} {'Traditional':>12} {'Saved':>10} {'%':>7}"
        )
        click.echo(f"  {'-' * 12} {'-' * 6} {'-' * 10} {'-' * 12} {'-' * 10} {'-' * 7}")
        for day in summary["daily"]:
            click.echo(
                f"  {day['date']:<12} {day['calls']:>6} "
                f"{day['avicenna_tokens']:>10,} {day['traditional_estimate']:>12,} "
                f"{day['saved']:>10,} {day['savings_pct']:>7}"
            )

    click.echo()


if __name__ == "__main__":
    main()
