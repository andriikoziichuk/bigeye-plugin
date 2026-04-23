# Bigeye MCP Server — Installation & Setup Guide

Optional companion to the Bigeye CLI. The CLI handles issues, monitor deploys, and table enumeration. The MCP server unlocks these plugin features:

- Root-cause analysis with lineage tracing
- Issue cluster / cascade detection
- Dimension coverage scoring
- Incident creation and management
- Display-number → internal ID lookup (so `/bigeye-rca 10921` works with the number shown in the UI)
- `deployed-by-plugin` tag tracking on created monitors
- Data-source picker in the config wizard

Without MCP, the plugin still runs — you'll see `Note: feature X unavailable — see bigeye-mcp-install.md` warnings on affected skills, and a few operations hard-fail (coverage scoring, incident creation, display-name lookup).

---

## 1. Prerequisites

- Claude Code (you're reading this in it)
- Bigeye account and a **personal access token** (API key from the Bigeye UI — not your CLI password)
- Either `uvx` (recommended, zero-install) OR Python 3.10+ with `pip`

## 2. Install the MCP server

> **TBD during implementation.** Verify the exact published Bigeye MCP package (pip name, source repo, or uvx target) against the current Bigeye docs and fill in two variants here:
>
> **Option A — uvx (zero-install):** single command to point Claude Code at the server without local install.
>
> **Option B — pip/pipx:** long-lived install with a persistent process.

## 3. Register with Claude Code

Add an MCP server entry to your Claude Code MCP config (typically `.mcp.json` in the project root or user-global MCP settings). Example stanza (adjust paths to match whatever you settle on in §2):

```json
{
  "mcpServers": {
    "bigeye": {
      "command": "uvx",
      "args": ["bigeye-mcp"],
      "env": {
        "BIGEYE_API_KEY": "<your-api-key>",
        "BIGEYE_WORKSPACE_ID": "<your-workspace-id>",
        "BIGEYE_BASE_URL": "https://app.bigeye.com"
      }
    }
  }
}
```

Alternatively, read credentials from `~/.bigeye/credentials` if the MCP server supports it — check the server's docs.

Restart Claude Code after editing the config.

## 4. Verify it works

Run:
```
/bigeye-config verify
```

The MCP row should flip to `[✓]` and list the features now enabled.

## 5. Feature matrix

| Plugin feature | CLI | MCP |
|---|---|---|
| List issues, triage summary | yes | — |
| Ack / close individual issues | yes | — |
| Deploy monitors (freshness) | yes | — |
| Deploy monitors (gaps / bulk) | yes | **required (coverage scoring)** |
| Root-cause lineage trace | — | **required** |
| Issue cluster detection | — | **required** |
| Dimension coverage scoring | — | **required** |
| Incident creation | — | **required** |
| Display-name → internal-ID lookup | — | **required** |
| `deployed-by-plugin` tagging | — | **required** |

## 6. Troubleshooting

**`/bigeye-config verify` shows `[!] MCP server reachable`** — server registered but unreachable. Check:
- MCP server process is running (for pip/pipx installs)
- API key and workspace ID are correct
- `BIGEYE_BASE_URL` matches your Bigeye deployment (not always `app.bigeye.com`)

**`401 Unauthorized` from MCP** — API key is wrong or expired. Regenerate in the Bigeye UI (Settings → Personal access tokens). Note: this is separate from the `~/.bigeye/credentials` used by the CLI.

**`uvx` cold-start is slow** — first call to an uvx-launched MCP server downloads the package. Subsequent calls are fast.

**The plugin still shows MCP warnings after registering** — run `/bigeye-config verify`; if it still reports MCP unreachable, check Claude Code's MCP logs (usually in the status bar or via `/mcp` command).
