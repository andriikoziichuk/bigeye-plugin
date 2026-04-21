# Bigeye CLI — Installation & Setup Guide

End-to-end instructions for getting `bigeye` working on macOS (zsh) and Linux. Written after hitting the `command not found: bigeye` gotcha firsthand — the PATH fix is called out explicitly.

---

## 1. Prerequisites

- **Python 3.9 or newer.** Check with `python3 --version`. If older, install a newer Python via `pyenv` or Homebrew (`brew install python@3.12`).
- **pip3** (comes with Python).
- A Bigeye account with credentials and a known workspace ID.

Optional but recommended: **pipx** — it installs CLI tools in isolated environments and handles PATH for you, sidestepping the main gotcha below.

```bash
brew install pipx
pipx ensurepath
```

---

## 2. Install the CLI

Pick **one** of the two options.

### Option A — pipx (recommended)

```bash
pipx install bigeye-cli
```

`pipx ensurepath` (run once when you installed pipx) puts `~/.local/bin` on your PATH, so `bigeye` will just work.

### Option B — pip3 (what most people try first)

```bash
pip3 install bigeye-cli
```

Watch the output. You will almost certainly see a warning like:

```
WARNING: The script bigeye is installed in '/Users/you/Library/Python/3.12/bin'
which is not on PATH.
```

That directory is the problem. Keep reading — section 3 fixes it.

---

## 3. Fix the PATH (macOS / zsh)

This is the step everyone trips on. If `bigeye --version` prints `zsh: command not found: bigeye`, you are here.

Find where pip actually put the script:

```bash
python3 -m site --user-base
```

That prints something like `/Users/you/Library/Python/3.12`. The script lives in `<that>/bin`.

Add it to your shell PATH permanently:

```bash
echo 'export PATH="$(python3 -m site --user-base)/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Verify:

```bash
which bigeye
bigeye --version
```

You should see a path and a version like `Bigeye CLI Version: 0.6.0`.

### Linux / bash

Same fix, but edit `~/.bashrc` instead of `~/.zshrc`. On most Linux distros pip user-base is `~/.local`, so you can simplify to:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## 4. Configure credentials

The CLI reads two INI files. Default locations are `~/.bigeye/credentials` and `~/.bigeye/config.ini`. Create them manually or use the interactive `bigeye configure` command.

### Option A — interactive

```bash
bigeye configure
```

It will prompt for base URL, username, password (or browser auth), and workspace info, then write both files for you.

### Option B — create the files by hand

Create the directory:

```bash
mkdir -p ~/.bigeye
```

**`~/.bigeye/credentials`**

```ini
[DEFAULT]
base_url = https://app.bigeye.com
user = you@yourcompany.com
password = your_bigeye_password
```

**`~/.bigeye/config.ini`**

```ini
[DEFAULT]
workspace_id = 123
```

Replace `123` with your numeric workspace ID. You can find it in the Bigeye web UI URL after logging in.

Lock down permissions so the password file isn't world-readable:

```bash
chmod 600 ~/.bigeye/credentials
```

### Browser authentication (alternative to password)

If you prefer not to store a password, run `bigeye configure` and choose `browser_auth`. The CLI reuses your Chrome / Firefox session. Caveats: only valid while the browser session is active, and not supported if your org uses SSO.

### Multiple workspaces

Add a named section to each file:

```ini
# ~/.bigeye/config.ini
[DEFAULT]
workspace_id = 123

[data-science]
workspace_id = 456
```

Then target it per command: `bigeye -w data-science issues get-issues -op ./out`.

### Non-default file locations

Point the CLI at custom paths with env vars (handy for CI):

```bash
export BIGEYE_API_CRED_FILE=/path/to/credentials.ini
export BIGEYE_API_CONFIG_FILE=/path/to/config.ini
```

Or per-command with `-b` and `-c` flags.

---

## 5. Verify it works

```bash
bigeye --version
bigeye configure list              # shows configured workspaces
bigeye catalog --help              # any read-only command works here
```

If a real command succeeds without an auth error, you're done.

---

## 6. Useful commands (quick tour)

```bash
bigeye --help                                  # top-level menu
bigeye issues get-issues -op ./issues-dump     # dump all issues to a folder
bigeye catalog --help                          # explore warehouses / schemas / tables
bigeye metric --help                           # metric management
bigeye bigconfig --help                        # bigconfig apply / plan
bigeye collections --help                      # collections
bigeye lineage --help                          # lineage
```

---

## 7. Troubleshooting

**`zsh: command not found: bigeye`** — PATH issue. Go back to section 3.

**`Config file not found. Please run the bigeye configure command.`** — You haven't created `~/.bigeye/config.ini` yet. Section 4.

**`401 Unauthorized` / auth errors** — Wrong `user`/`password`, wrong `base_url`, or your workspace needs SSO. Try `bigeye configure` with browser auth, or confirm the base URL with your admin (it's not always `app.bigeye.com`).

**Multiple Pythons on your Mac** — `which python3` and `which pip3` should point at the same installation. If not, install with the matching pip (e.g. `/opt/homebrew/bin/pip3 install bigeye-cli`) or use pipx.

**Upgrading** — `pip3 install --upgrade bigeye-cli` or `pipx upgrade bigeye-cli`.

**Uninstalling** — `pip3 uninstall bigeye-cli` or `pipx uninstall bigeye-cli`. Delete `~/.bigeye/` to remove credentials.
