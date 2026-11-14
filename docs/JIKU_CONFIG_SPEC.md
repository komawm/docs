# Jiku (`jiku` / `jikud`) Configuration & Bus Protocol Specification

> **Document Path**: `docs/JIKU_CONFIG_SPEC.md`
> **User Config Directory**: `~/.config/jiku/` (`config.toml`, `init.lua`, `skills/*.lua`)
> **Runtime Socket**: `$XDG_RUNTIME_DIR/jiku.sock` (`0600`, same-UID `SO_PEERCRED`)
> **Companion Document**: `docs/JIKU_ARCHITECTURE.md`

---

## 1. Directory Layout & Sandbox Permissions

```text
~/.config/jiku/                  # Mounted Read-Only (ro) inside jikud sandbox
├── config.toml                  # Static infrastructure: providers, role routing, sandbox, TTS, notify
├── init.lua                     # Phodopus policy hooks (memory shaping, notification rules, TTS triggers)
└── skills/                      # Human-approved deterministic GUI macros (*.lua)
    ├── libreoffice_export.lua
    └── browser_table_collect.lua

~/.local/state/jiku/             # Mounted Read-Write (rw) inside jikud sandbox
├── state.db                     # SQLite WAL + FTS5 (L1 app_quirks + L2 episodes)
├── audit.jsonl                  # Append-only action & Epoch ledger
└── staged_skills/               # Candidate Lua skills awaiting `jiku skills approve`

~/JikuBox/                       # Mounted Read-Write (rw) explicit human <-> Jiku file dropbox
```

---

## 2. `config.toml` Schema Reference

### 2.1 `[daemon]` & `[koma]` Connection

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `daemon.locale` | `string` | `"zh-CN"` | Output language for summaries, notifications, and TTS (`"zh-CN"`, `"ja-JP"`, `"en-US"`). |
| `daemon.socket_name` | `string` | `"jiku.sock"` | Control & EventBus socket created under `$XDG_RUNTIME_DIR/`. |
| `daemon.dropbox_dir` | `string` | `"~/JikuBox"` | Explicit read-write exchange directory mounted into the sandbox. |
| `koma.default_workspace` | `string` | `"agent:work"` | Default `Headless` `Deck` workspace leased via `koma-agent.sock`. |
| `koma.default_overlay` | `string` | `"grid_225"` | Capture overlay requested on `capture.frame` (`"none"`, `"grid_225"`). |
| `koma.perceptual_hash_threshold` | `integer` | `4` | Hamming distance threshold below which unchanged `memfd` tiles skip VLM re-inference. |

### 2.2 `[providers.<id>]` Templates & `[roles]` Routing

Supported `kind` templates:
* `"google_gemini"` — Native Gemini API supporting `gemini-decision-1` (`grid_225` + macro tool calls), Gemini Computer Use (`0..1000` normalized coordinates), and multimodal vision.
* `"openai_compatible"` — Covers OpenAI, DeepSeek, OpenRouter, vLLM, `llama.cpp`, and Ollama (`/v1/chat/completions`).
* `"anthropic"` — Native Anthropic Messages API with prompt caching and Computer Use coordinate normalization.

Role assignments under `[roles]`:
* `planner` — High-level task decomposition and recovery planning.
* `actor` — Per-step visual grounding, `grid_225` cell selection, or `0..1000` coordinate emission.
* `fast_guard` — Optional low-latency model for modal dialog detection and post-action verification.

### 2.3 `[memory]`, `[notify]`, `[tts]` & `[avatar]`

* **`[memory]`**: `backend = "sqlite_fts5"` (default), `l0_frame_ring_size = 4`, `stage_new_skills = true`, optional `external_mcp_command` for external `MemoryProvider` bridging.
* **`[notify]`**: `desktop_dbus = true` (`org.freedesktop.Notifications` -> `swaync`), `urgency_on_verification = "critical"`, optional `webhook_url_env`.
* **`[tts]`**: `enabled = false | true`, `provider = "voicevox" | "piper" | "openai_speech"`, `endpoint = "http://127.0.0.1:50021"`, `speaker_id = 3`, `speak_on = ["task_completed", "verification_needed"]`.
* **`[avatar]`**: `emit_cues = true` — broadcasts real-time `AvatarCue` frames (emotion tag, `(u, v)` virtual cursor gaze, and mora/phoneme timing envelopes) to any subscribed Live2D / VRM `wlr-layer-shell` companion client on `jiku.sock`.

---

## 3. `jiku` CLI & Detachable TUI Subcommands

```bash
# Launch interactive ratatui TUI attached to running jikud (closing TUI leaves jikud running)
jiku

# Submit a background GUI task from terminal or an external Coding Agent (Claude Code / Codex)
jiku run --workspace agent:work "Export ~/JikuBox/draft.odt to PDF in LibreOffice"

# Inspect live daemon status, leased workspaces, and current Epoch
jiku status

# Review and promote a staged Lua skill into ~/.config/jiku/skills/ (runs outside jikud ro mount)
jiku skills list
jiku skills diff libreoffice_pdf_export
jiku skills approve libreoffice_pdf_export

# Expose Jiku as an MCP server over stdio (--stateless disables episode history for master agents)
jiku mcp --stateless
```

---

## 4. `jiku.sock` EventBus Wire Envelope (TUI, TTS & Live2D Subscribers)

Clients connecting to `$XDG_RUNTIME_DIR/jiku.sock` use the same 4-byte little-endian length-prefixed JSON framing as `koma-proto` and can subscribe to `["task.progress", "skill.staged", "tts.utterance", "avatar.cue"]`:

```json
{
  "seq": 88,
  "topic": "avatar.cue",
  "payload": {
    "emotion": "thinking",
    "gaze_uv": [0.62, 0.35],
    "utterance_locale": "ja-JP",
    "mora_envelope": [
      { "phoneme": "k", "vowel": "o", "duration_ms": 95, "pitch": 5.82 },
      { "phoneme": "m", "vowel": "a", "duration_ms": 110, "pitch": 5.95 }
    ]
  }
}
```
