# SalesFlow MCP Server: Setup

The SalesFlow MCP server is a read-only Python FastMCP server (stdio transport) managed with `uv`. It serves synthetic data from `data/` to IBM Bob. Tool contract: [`docs/contracts/mcp-tools.md`](contracts/mcp-tools.md).

## 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # macOS / Linux
# or: brew install uv
uv --version
which uv                                            # note this path for Bob config
```

On the lead's machine uv is at `/Users/jwebb/.local/bin/uv` (local troubleshooting only).

## 2. Resolve dependencies

```bash
cd <repo>/mcp-server
uv sync          # creates .venv from uv.lock (FastMCP 4.1.4, Python >= 3.10)
```

`uv.lock` is committed; do not delete it. `.venv/` is git-ignored.

## 3. Start the server manually

```bash
cd <repo>/mcp-server
uv run salesflow-mcp
```

It waits silently on stdin/stdout (stdio MCP). A FastMCP banner appears on stderr. Stop with Ctrl+C. Never add `print()` to stdout in the server: it corrupts the protocol stream.

Optional: `SALESFLOW_DATA_DIR=/path/to/data` overrides the data directory (default: `<repo>/data`).

## 4. Register the server in IBM Bob

Config file: `.bob/mcp.json` (project scope). Bob launches the process itself.

Current working local configuration (absolute paths, this machine only):

```json
{
  "mcpServers": {
    "salesflow": {
      "command": "/Users/jwebb/.local/bin/uv",
      "args": ["run", "--directory", "/Users/jwebb/Desktop/SalesFlow/mcp-server", "salesflow-mcp"],
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

### Portable setup for teammates

Do not commit personal absolute paths. `.bob/mcp.json` is tracked in git, and the committed version on `main` uses `"command": "uv"` with `--directory mcp-server` (relative). That form has NOT been shown to work in Bob on the lead's machine, which is why the absolute-path version above is in the working tree.

What is verified, and what is not:

| Item | Status |
|---|---|
| Bob supports project-level `.bob/mcp.json` and global `~/.bob/mcp.json`; project wins on a name clash | Documented by Bob docs |
| Bob supports optional `cwd` and `env` per stdio server | Documented by Bob docs |
| `uv run --directory mcp-server salesflow-mcp` works when the process cwd is the repo root | Tested locally |
| The same command fails (`No such file or directory`) when cwd is not the repo root | Tested locally |
| Bob's default cwd for project MCP servers is the workspace root | NOT verified |
| Bob expands `${workspaceFolder}` or `~` in `command`/`args`/`cwd` | NOT verified, not documented in the pages searched; do not use |
| Bob finds `uv` on `PATH` when launched as a GUI app | NOT verified |

Recommended procedure (uses only documented or tested behaviour):

1. Keep `.bob/mcp.json` in git as the portable template, and do not commit personal paths.
2. Each teammate puts their machine-specific entry in the **global** file `~/.bob/mcp.json` (Settings, MCP tab, "Edit Global MCP") instead of editing the tracked project file. Use the output of `which uv` for `command` and `<their clone>/mcp-server` for `--directory`, as in the example above. The project-level entry wins on a name clash, so if the tracked `.bob/mcp.json` also defines `salesflow` and does not work for you, rename your global entry (e.g. `salesflow-local`) and disable the project one. Be aware that tool identifiers may then change, so tell Lane A.
3. Alternatively, run `git update-index --skip-worktree .bob/mcp.json` after setting local paths, so local edits are not staged. Undo with `--no-skip-worktree` before changing the shared template.
4. If you want to try the portable form, set `cwd` to your clone path and keep `"command": "uv"` and relative `--directory mcp-server`. Test it in Bob before relying on it.

Make this change only after integration testing is complete. Do not assume relative `--directory` paths resolve against the repo root.

After editing the config, restart or refresh the server in Bob (MCP servers panel, toggle off and on, or reload the window).

## 5. Test the tools

Offline, no Bob needed (FastMCP in-memory client, 22 checks):

```bash
cd <repo>/mcp-server
uv run python tests/run_tools_test.py
```

Exit code 0 means no failures. The `BLOCKED` line for the SPIN playbook is expected until Lane C adds `data/playbooks/*.json`; the playbook code path is exercised with a temporary fixture and labelled as such.

Over real stdio (same launch path Bob uses): connect a `fastmcp.Client` with `StdioTransport(command=<uv path>, args=["run","--directory",<repo>/mcp-server,"salesflow-mcp"])`, then call `list_tools` and each tool.

In Bob: ask in chat, for example "Call the SalesFlow get_account_profile tool for Acme Healthcare". Expected: `account_id` `acct_acme_healthcare`, industry Healthcare. Then "get_opportunity_context for acct_acme_healthcare": expected `opp_acme_storage_01`, stage Discovery, unknowns budget / decision maker / usable capacity.

Tools: `ping`, `get_account_profile(company_name)`, `get_opportunity_context(account_id)`, `search_product_knowledge(query)`, `get_sales_playbook(topic)`.

## 6. Common connection failures

| Symptom | Likely cause | Fix |
|---|---|---|
| Server shows red / "failed to connect" | Bob cannot find `uv` (GUI `PATH` lacks `~/.local/bin`) | Use the absolute path from `which uv` in `command` |
| Same, after moving the repo | Stale `--directory` path | Update to the current `<repo>/mcp-server` |
| Connects but only `ping` appears | Old server process still running | Toggle the server off/on or reload the Bob window |
| Slow first start / timeout | `uv` creating `.venv` on first run | Run `uv sync` once in `mcp-server/` beforehand |
| `No solution found` / resolve errors | Offline or stale lock | Go online, run `uv sync`; do not hand-edit `uv.lock` |
| Garbled protocol / immediate disconnect | Something printed to stdout | Remove prints; log to stderr only |
| Tools return "data source is currently unavailable" | `data/*.json` missing or invalid JSON (details in server stderr) | Validate the file with `python -m json.tool data/accounts.json` |
| `get_sales_playbook` returns `not_found` for a valid topic | No `data/playbooks/*.json` yet (Lane C) | Add playbook fixtures per the contract |
| Python version error | Python < 3.10 | `uv python install 3.12` then `uv sync` |

Server logs go to stderr only; view them in Bob's MCP server log/output panel. Logs contain no customer data or secrets.
