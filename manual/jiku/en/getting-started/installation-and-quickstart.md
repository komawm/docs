# Installation, API Keys & First Run

> [!NOTE]
> Installing Jiku is completely optional. [Koma](/docs/getting-started/installation/) works as a standalone Wayland tiling compositor without `jikud` or `jiku` installed.

## Installing `jikud` & `jiku`

Install prebuilt packages via [komawm/packaging](https://github.com/komawm/packaging) (`cdn.komawm.org` signed APT `jiku` package, AUR `jiku-bin`, Linuxbrew `jiku.rb`, or nFPM `.deb`/`.rpm`/`.apk`), download the `v0.0.1` multi-architecture release tarballs (`jiku-0.0.1-x86_64-unknown-linux-gnu.tar.gz` or `jiku-0.0.1-aarch64-unknown-linux-gnu.tar.gz`) from [komawm/jiku](https://github.com/komawm/jiku) / `cdn.komawm.org`, or install/build from source with **Rust `1.100.0` (Edition 2024)**.

### Prebuilt Binary Channels (`x86_64` & `aarch64`)

```bash
# Arch Linux (prebuilt AUR package)
paru -S jiku-bin

# Debian / Ubuntu (signed APT repository)
curl -fsSL https://cdn.komawm.org/apt/setup.sh | sudo bash && sudo apt install -y jiku

# Linuxbrew
curl -fsSLO https://cdn.komawm.org/install/jiku/jiku.rb && brew install --formula ./jiku.rb
```

### Cargo & Source Build

```bash
# Direct install via Cargo
cargo +1.100.0 install --git https://github.com/komawm/jiku.git jikud jiku --locked

# Or clone and build locally
git clone https://github.com/komawm/jiku.git
cd jiku
cargo +1.100.0 build --release --locked -p jikud -p jiku
./target/release/jikud --headless-check
```

## API Keys & Environment Variables

`jikud` reads API keys solely from environment variables named in `config.toml` (`api_key_env`)—never store raw keys inside `config.toml`:

| Env Variable | Default Provider | Role |
| :--- | :--- | :--- |
| `OPENCODE_GO_API_KEY` | `opencode_go` (`deepseek-v4.1-flash`) | Primary `[roles.planner]` and automatic `EmulatedStructuredTextModel` fallback |
| `GEMINI_API_KEY` | `gemini` (`gemini-decision-1`) | Optional single-prefill `DecisionsDriver` (`0` output tokens) & optional `LiveSessionDriver` |
| `KOMA_CAPABILITY_TOKEN` | Koma IPC (`koma-agent.sock`) | Scoped lease token minted via `komactl token mint jiku` |

> [!TIP]
> **No Dedicated Decision Model Key?** If `GEMINI_API_KEY` is unset (or you assign a general OpenAI/Anthropic/vLLM/Ollama provider to `[roles.decision_router]`), `DecisionBackend` automatically runs `EmulatedStructuredTextModel` via your primary `[roles.planner]` model without error.

## First Run Checklist

1. **Validate config & Lua policy offline**:
   ```bash
   jiku validate-config
   ```
2. **Mint a scoped Koma capability token** (while `koma` is running):
   ```bash
   export KOMA_CAPABILITY_TOKEN="$(komactl token mint jiku | jq -r '.token')"
   ```
3. **Start `jikud` and check status**:
   ```bash
   jikud --daemon &
   jiku status --json
   ```
4. **Run a dry-run or live task**:
   ```bash
   jiku run --dry-run "Open a terminal and check uname -a"
   ```

## Using Jiku from External Coding Agents (`Claude Code`, `Codex`, `OpenCode`, `Cursor`)

Register `jiku mcp` as a stdio MCP server in your coding agent, or point it at `jiku/skills/SKILL.md` so it calls `jiku run`, `jiku decide`, `jiku box classify`, and `jiku memory search` safely over Koma's Epoch-fenced IPC.
