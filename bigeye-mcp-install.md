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
- Docker installed and running

## 2. Install the MCP server (Docker image)

Ask Claude to install the Bigeye MCP server from the official repo:

> Install the Bigeye MCP server from https://github.com/bigeyedata/bigeye-mcp-server by cloning the repo and building the Docker image `bigeye-mcp-server:latest`.

Claude will run the equivalent of:

```bash
git clone https://github.com/bigeyedata/bigeye-mcp-server.git
cd bigeye-mcp-server
docker build -t bigeye-mcp-server:latest .
```

Verify the image exists:

```bash
docker image inspect bigeye-mcp-server:latest >/dev/null && echo "ok"
```

## 3. Generate a Bigeye API token

In the Bigeye UI: **Settings → Personal access tokens → Create token**. Copy the token — you won't see it again.

Also note your **workspace ID** (visible in the URL after login, e.g. `app.bigeye.com/w/317/...` → workspace ID is `317`).

## 4. Register with Claude Code

Open your Claude Code MCP config (`~/.claude.json` or project-level `.mcp.json`) and add the following entry under `mcpServers`. Replace `token` with the value from §3 and `317` with your workspace ID:

```json
"bigeye": {
  "type": "stdio",
  "command": "docker",
  "args": [
    "run",
    "-i",
    "--rm",
    "-e",
    "BIGEYE_API_KEY=token",
    "-e",
    "BIGEYE_API_URL=https://app.bigeye.com",
    "-e",
    "BIGEYE_WORKSPACE_ID=317",
    "-e",
    "BIGEYE_DEBUG=false",
    "bigeye-mcp-server:latest"
  ],
  "env": {}
}
```

If your Bigeye tenant is not `app.bigeye.com`, set `BIGEYE_API_URL` to your actual instance URL.

After saving the config, **reconnect** — either restart Claude Code, or run `/mcp` and reconnect the `bigeye` server.

## 5. Verify it works

Run:
```
/bigeye-config verify
```

The MCP row should flip to `[✓]` and list the features now enabled.

## 6. Feature matrix

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

## 7. Troubleshooting

**`/bigeye-config verify` shows `[!] MCP server reachable`** — server registered but unreachable. Check:
- Docker daemon is running (`docker ps`)
- Image `bigeye-mcp-server:latest` exists locally (`docker images | grep bigeye-mcp`)
- API key and workspace ID in the config are correct
- `BIGEYE_API_URL` matches your Bigeye deployment (not always `app.bigeye.com`)

**`401 Unauthorized` from MCP** — API key is wrong or expired. Regenerate in the Bigeye UI (Settings → Personal access tokens). Note: this is separate from the `~/.bigeye/credentials` used by the CLI.

**Container exits immediately / no response from MCP** — run the same `docker run …` command manually in a terminal and inspect stderr. Set `BIGEYE_DEBUG=true` in the args to enable verbose logging.

**Image not found (`Unable to find image 'bigeye-mcp-server:latest' locally`)** — the build step in §2 failed or was skipped. Rebuild from the cloned repo.

**The plugin still shows MCP warnings after registering** — run `/bigeye-config verify`; if it still reports MCP unreachable, check Claude Code's MCP logs (status bar or `/mcp` command).
