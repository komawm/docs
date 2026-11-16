# Installation & First Run

> [!NOTE]
> Installing Jiku is optional. [Koma](/docs/getting-started/installation/) works as a standalone Wayland tiling compositor without `jikud` or `jiku`.

![Running jiku CLI checks inside a Koma terminal](https://cdn.komawm.org/media/jiku-terminal.webp "Checking Jiku status and running CLI commands in a Koma terminal.")

## Installing `jikud` & `jiku`

Install prebuilt packages from [komawm/packaging](https://github.com/komawm/packaging) (signed APT `jiku` package, AUR `jiku-bin`, Linuxbrew `jiku.rb`, or `.deb`/`.rpm`/`.apk` archives), download the `v0.0.1` release tarballs (`jiku-0.0.1-x86_64-unknown-linux-gnu.tar.gz` or `jiku-0.0.1-aarch64-unknown-linux-gnu.tar.gz`) from [komawm/jiku](https://github.com/komawm/jiku), install the release binaries from npm (`@koma-wm/jiku`), or build from source.

### Prebuilt Binary Channels (`x86_64` & `aarch64`)

```bash
# Arch Linux (AUR prebuilt package)
paru -S jiku-bin

# Debian / Ubuntu (signed APT repository)
curl -fsSL https://cdn.komawm.org/apt/setup.sh | sudo bash && sudo apt install -y jiku

# Linuxbrew
curl -fsSLO https://cdn.komawm.org/install/jiku/jiku.rb && brew install --formula ./jiku.rb

# npm / Bun (registry scope `@koma-wm`; `komawm` was already registered)
bun add -g @koma-wm/jiku
# or
npm install -g @koma-wm/jiku
```

The registry carries `v0.0.1` for `linux-x64` and `linux-arm64` on glibc, with
`latest` and `development` both pointing at it. Newer versions appear only after a
`komawm/packaging` release dispatch, so a version that is not on the registry yet
is expected rather than a broken install. musl/Alpine, macOS, and Windows are not
supported; the launcher refuses them with an explicit message. To pin the
prerelease channel explicitly, use `@koma-wm/jiku@development`.

### Build from Source

```bash
# Direct install from repository
cargo +1.100.0 install --git https://github.com/komawm/jiku.git jikud jiku --locked

# Or clone and build locally
git clone https://github.com/komawm/jiku.git
cd jiku
cargo +1.100.0 build --release --locked -p jikud -p jiku
./target/release/jikud --headless-check
```

### Agent Skill (`npx skills`)

The repository ships an installable skill for coding agents:

```bash
# Jiku: goal-level desktop orchestration
npx skills add komawm/jiku --skill jiku-desktop-orchestration -g

# Koma: compositor workspaces, capture, and input primitives
npx skills add komawm/koma --skill koma-desktop -g
```

The skill is MIT licensed and carries its own `LICENSE`, independent of the
`GPL-3.0-or-later` product license, so a copied skill stays self-contained.

If the installed package was built from a tag that contains
`skills/jiku-desktop-orchestration/`, `npx skills experimental_sync` also links that
bundled copy from a project dependency (`bun add -d @koma-wm/jiku`). Tags that predate
the skill catalog, including `v0.0.1`, bundle nothing, so use `npx skills add` there.

## API Keys & Environment Variables

`jikud` reads credentials only from environment variables named by `api_key_env` in `config.toml` or `config.lua`. Never store raw API keys inside configuration files.

| Env Variable | Default Provider | Role |
| :--- | :--- | :--- |
| `JIKU_PLANNER_API_KEY` | `primary` (`[providers.primary]`) | Primary `[roles.planner]` text/VLM model and automatic JSON fallback for decisions |
| `JIKU_DECISION_API_KEY` | `decision` (`[providers.decision]`) | Optional dedicated decision model and optional live voice session |
| `KOMA_CAPABILITY_TOKEN` | Koma IPC (`koma-agent.sock`) | Scoped lease token minted with `komactl token mint jiku` |

> [!TIP]
> **No dedicated decision model key?** If the configured decision provider key is unset (or you assign any OpenAI-compatible, Anthropic, vLLM, or Ollama provider to `[roles.decision_router]`), Jiku falls back to `[roles.planner]` using structured JSON output without error.

## First Run Checklist

1. **Validate config and Lua policy offline**:
   ```bash
   jiku validate-config
   ```
2. **Mint a scoped Koma capability token** (while `koma` is running):
   ```bash
   export KOMA_CAPABILITY_TOKEN="$(komactl token mint jiku | jq -r '.token')"
   ```
3. **Start `jikud` and verify status**:
   ```bash
   jikud --daemon &
   jiku status --json
   ```
4. **Test with a dry-run task and local diagnostics**:
   ```bash
   jiku run --dry-run "Open a terminal and check uname -a"
   jiku a11y snapshot --json
   jiku context inspect --max-tokens 4096
   jiku tts say "Jiku is ready"
   jiku avatar serve --bind 127.0.0.1:4190
   jiku bench run --offline
   ```

## Using Jiku from External Coding Agents (`Claude Code`, `Codex`, `OpenCode`, `pi`, `Cursor`)

Both `jiku mcp` (12 orchestration tools) and `koma-mcp` (17 compositor tools) auto-detect `Content-Length` and `NDJSON` stdio framing per message. Register them in `Claude Code`, `Codex`, `Cursor`, `pi`, or OpenCode (`~/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "koma": {
      "type": "local",
      "command": ["koma-mcp"],
      "enabled": true
    },
    "jiku": {
      "type": "local",
      "command": ["jiku", "mcp"],
      "enabled": true
    }
  }
}
```

Mint the token with `komactl token mint <label>` and export it in the shell that starts the
agent host; `koma-mcp` reads `KOMA_CAPABILITY_TOKEN` from its environment, so the token never has
to live in configuration. If your host does not inherit the environment, set it in that host's
own environment block. Never pass `--auto-mint-admin` to an agent-controlled MCP server: it would
let the agent mint its own grants.
`jiku status` needs a running Koma session; without one it fails by design, which is not an
installation error.

Install the [agent skill](#agent-skill-npx-skills) instead of copying a `SKILL.md` path, so the agent
invokes `jiku run`, `jiku decide`, `jiku a11y`, `jiku context inspect`, `jiku box classify`, and
`jiku memory search` under Koma's Epoch-fenced IPC.
