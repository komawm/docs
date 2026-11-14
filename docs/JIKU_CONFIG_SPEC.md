# Jiku (`jiku` / `jikud`) Configuration & Bus Protocol Specification

> **Document Path**: `docs/JIKU_CONFIG_SPEC.md`
> **User Config Directory**: `~/.config/jiku/` (`config.toml`, `init.lua`, `skills/*.lua`)
> **Runtime Socket**: `$XDG_RUNTIME_DIR/jiku.sock` (`0600`, same-UID `SO_PEERCRED`)
> **Companion Document**: `docs/JIKU_ARCHITECTURE.md`

---

## 1. Directory Layout & Sandbox Permissions

```text
~/.config/jiku/                  # Mounted Read-Only (ro) inside jikud sandbox
├── config.toml                  # Static infrastructure: providers, 3-driver role routing, jikubox triage, TTS, notify
├── init.lua                     # Phodopus policy hooks (memory shaping, notification rules, TTS triggers)
└── skills/                      # Human-approved deterministic GUI macros (*.lua)
    ├── libreoffice_export.lua
    └── browser_table_collect.lua

~/.local/state/jiku/             # Mounted Read-Write (rw) inside jikud sandbox
├── state.db                     # SQLite WAL + FTS5 (L1 app_quirks + L2 episodes)
├── audit.jsonl                  # Append-only action, safety-gate & Epoch ledger
└── staged_skills/               # Candidate Lua skills awaiting `jiku skills approve`

~/JikuBox/                       # Mounted Read-Write (rw) explicit human <-> Jiku file dropbox
├── inbox/                       # Incoming files for `jiku box classify` zero-decode batch triage
└── triaged/                     # Structured JSON/Markdown reports and sorted outputs
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
| `koma.perceptual_hash_threshold` | `integer` | `4` | Hamming distance threshold below which unchanged `memfd` tiles skip VLM re-inference and `LiveSessionDriver` drops screen uplink to `0 FPS`. |

### 2.2 `[providers.<id>]` Templates, Foundational `[roles.planner]` & External Agent Integration

`Jiku` works out-of-the-box both as a **standalone customizable desktop agent** (configured with any cloud or local LLM provider in `config.toml`) and as a **sub-agent / tool bridge** invoked by external AI coding agents (**`Claude Code`**, **`Codex`**, **`GitHub Copilot`**, **`Cursor`**, **`OpenCode`**) via **MCP (`jiku mcp`)** or **CLI + `SKILL.md` (`jiku run ...`, `komactl`)**.

Supported provider `kind` templates across `jikud`'s architecture:
* `"google_gemini"` — Google AI Studio (`GEMINI_API_KEY`) and Vertex AI ADC supporting `DecisionsDriver` (`POST /v1beta/decisions` with literal model ID `"gemini-decision-1"`), `TurnModelDriver` (`reqwest` HTTP/2 SSE + Gemini Computer Use `0..1000` coordinates), and optional `LiveSessionDriver` (`BidiGenerateContent` stateful full-duplex WebSocket).
* `"openai_compatible"` — Covers `TurnModelDriver` (`/v1/chat/completions` across OpenAI GPT, DeepSeek, OpenRouter, and self-hosted local models via `vLLM`, `llama.cpp`, and `Ollama`), automatic `EmulatedStructuredTextModel` decision fallback via JSON Schema `response_format`, and optional `LiveSessionDriver` (OpenAI Realtime API, Qwen-Omni Realtime, and local WebRTC/WebSocket speech-to-speech endpoints).
* `"anthropic"` — Native Anthropic `Messages` API (`TurnModelDriver` HTTP/2 SSE for Claude models) with prefix prompt caching, Computer Use coordinate normalization, and `EmulatedStructuredTextModel` decision fallback.

Role assignments under `[roles]`:
* **`[roles.planner]` (Foundational Primary Text/Multimodal Model — Required)** — The primary text/VLM model (OpenAI GPT, Anthropic Claude, Google Gemini, OpenRouter, or self-hosted local models via `vLLM` / `llama.cpp` / `Ollama`) is the **foundational model of `Jiku`**. It handles high-level task decomposition, System-2 fallback recovery when `decision_router` confidence `< 0.85`, free-form `type_text` generation, candidate `staged_skills/*.lua` synthesis, and serves as the automatic zero-error **`EmulatedStructuredTextModel`** host whenever no dedicated Decision Model is configured.
* **`[roles.decision_router]` (`DecisionBackend`: Optional `NativeDecisionsApi` Acceleration + Automatic `EmulatedStructuredTextModel` Fallback)** — Evaluates closed-set tasks (GUI `grid_225` targeting, `DecisionCompiler` shortcut sequences, 15-rule safety gates, `~/JikuBox/` multimodal tagging/grading, and FTS5 reranking).
* **`[roles.actor]`** (`DecisionsDriver` / `TurnModelDriver`) — Per-step visual grounding, `grid_225` cell selection, or `0..1000` coordinate emission.
* **`[roles.fast_guard]`** (`DecisionsDriver` / `TurnModelDriver`) — Low-latency modal dialog detection and post-action verification.

### 2.3 `[roles.decision_router]` (`DecisionBackend` & `DecisionExecutionMode`)

Configures `DecisionBackend` for closed-set evaluation (System-1 GUI `grid_225` targeting, `DecisionCompiler` shortcut sequences, 15-rule visual safety gating, `~/JikuBox/` multimodal tagging/grading, Live2D 255-cue selection, and L2 FTS5 trajectory reranking).

`DecisionBackend` automatically selects its **`DecisionExecutionMode`** based on the configured model and **never errors out** if a dedicated decision model is absent:
1. **`DecisionExecutionMode::NativeDecisionsApi`**: Selected when `model = "gemini-decision-1"` (`POST /v1beta/decisions` via `GEMINI_API_KEY`). Executes in a single prefill pass with **`0` output tokens** for closed-set tasks where decision models excel.
2. **`DecisionExecutionMode::EmulatedStructuredTextModel` (Zero-Error Automatic Fallback)**: Selected automatically when **no** dedicated Decision Model is configured (or when the user assigns a general text/VLM model to `[roles.decision_router]`). `Jiku` invokes **`synthesize_emulated_decision_prompt`** + strict JSON Schema constraints (`response_format`) on the primary text/VLM model (`[roles.planner]` or the configured general model) to output the exact same `{"answers": { ... }}` structure (`noul`, `choice`, and `score` probabilities and confidence). Downstream `DecisionCompiler` logic (`TimeSlotMacro`, `BernoulliExpectedStep`, `ThresholdProbe`) and `interpolate_grid_225_centroid` run **unchanged** across both modes.

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `provider` | `string` | `"google_ai_studio"` | Provider reference (if omitted or set to a general text/VLM provider, automatically runs `EmulatedStructuredTextModel` on `[roles.planner]`). |
| `model` | `string` | `"gemini-decision-1"` | Literal `"gemini-decision-1"` enables `NativeDecisionsApi` (`0` output tokens); any general text/VLM model (or omitting `[roles.decision_router]`) automatically selects `EmulatedStructuredTextModel` without error. |
| `execution_mode` | `string` | `"auto"` | `"auto"` (`NativeDecisionsApi` when `model == "gemini-decision-1"`, otherwise `EmulatedStructuredTextModel`), `"native_decisions_api"`, or `"emulated_structured_text_model"`. |
| `confidence_threshold` | `float` | `0.85` | Minimum probability required on `q_in_scope` and top action/target to dispatch directly to `Koma`; `< 0.85` escalates to `fallback_role`. |
| `fallback_role` | `string` | `"planner"` | Primary `TurnModelDriver` role (`[roles.planner]`) used for System-2 escalation (`< 0.85`) and automatic `EmulatedStructuredTextModel` fallback. |
| `max_questions_per_request` | `integer` | `1000` | Maximum parallel structured questions (`1..=1000`) packed into a single evaluation pass. |
| `require_none_or_other` | `bool` | `true` | Enforces `"NONE_OR_OTHER"` / `"not_visible"` fallback option + paired `q_in_scope` (`noul`) gate on every `Choice` question across both `NativeDecisionsApi` and `EmulatedStructuredTextModel`. |
| `safety_gate_rules` | `integer` | `15` | Number of parallel binary `noul` safety checklist questions (prompt injection, 2FA, payment, credential dialogs) evaluated per frame. |
| `media_mime_type` | `string` | `"image/webp"` | In-memory encoding format (`"image/webp"` or `"image/png"`) exported from `Koma`'s `memfd` (protected surfaces masked to `#000000`). |

#### `[roles.decision_router.compiler]` (`DecisionCompilerConfig`) & `[roles.decision_router.compiler.grid]` (`GridSpec`)

All `DecisionCompiler` thresholds, sentinel tokens, and decision-grid dimensions are configurable with sensible defaults (avoiding hardcoded compiler constants):

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `compiler.grid.cols` | `integer` | `15` | Decision grid column count (`GridSpec`, `1..=64`; default `15x15 = 225` cells). |
| `compiler.grid.rows` | `integer` | `15` | Decision grid row count (`GridSpec`, `1..=64`; default `15x15 = 225` cells). |
| `compiler.fast_path_confidence` | `float` | `0.85` | Minimum confidence threshold required on `q_in_scope` and the selected action/target for direct System-1 fast-path execution (`0.0..=1.0`). |
| `compiler.min_cell_prob` | `float` | `0.05` | Minimum cell probability retained when interpolating top-`K` probability-weighted cell centroids (`interpolate_grid_225_centroid`, `0.0..=1.0`). |
| `compiler.time_slot_min_confidence` | `float` | `0.75` | Minimum per-slot confidence before `TimeSlotMacro` truncates a multi-step shortcut sequence (`0.0..=1.0`). |
| `compiler.bernoulli_activation_threshold` | `float` | `0.80` | Minimum `P(Yes)` probability required to activate a conditional `BernoulliExpectedStep` (`0.0..=1.0`). |
| `compiler.probe_min_prob` | `float` | `0.15` | Minimum probability required for `ThresholdProbe` candidate retention (`0.0..=1.0`). |
| `compiler.stop_sentinel` | `string` | `"stop_done"` | Non-empty sentinel choice token signaling early sequence completion inside `TimeSlotMacro`. |
| `compiler.fallback_token` | `string` | `"NONE_OR_OTHER"` | Non-empty open-world escape option enforced across `Choice` questions (`require_none_or_other`). |

### 2.4 `[roles.live_companion]` (`LiveSessionDriver` — Optional Progressive Module, Disabled by Default)

Configures `jiku live` real-time voice, vision, and `Epoch`-fenced non-blocking action sessions (`tokio-tungstenite`). As part of `Jiku`'s **progressive modular roadmap**, real-time voice/live streaming (`jiku live`) is a decoupled optional module that remains **disabled by default** (`enabled = false`) unless explicitly enabled in `config.toml`. Audio sample rates (`audio_in_sample_rate_hz`, `audio_out_sample_rate_hz`) and screen capture cadence (`max_screen_fps`) are configurable within validated bounds with sensible defaults:

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `enabled` | `bool` | `false` | Explicitly enables the optional `LiveSessionDriver` module for `jiku live` (disabled by default). |
| `provider` | `string` | `"google_ai_studio"` | Provider backing the stateful full-duplex WebSocket session when enabled. |
| `protocol` | `string` | `"gemini_bidi"` | Wire protocol: `"gemini_bidi"` (`BidiGenerateContent`), `"openai_realtime"`, `"qwen_omni_realtime"`, or `"local_ws"`. |
| `model` | `string` | `"gemini-2.5-flash-live"` | Multimodal live session model identifier. |
| `audio_in_sample_rate_hz` | `integer` | `16000` | Configurable PipeWire uplink microphone capture rate (`8000..=48000` Hz, default `16000` Hz, `16-bit mono PCM`, `20–100 ms` chunks). |
| `audio_out_sample_rate_hz` | `integer` | `24000` | Configurable PipeWire downlink playback rate (`8000..=48000` Hz, default `24000` Hz PCM) with real-time RMS/frequency lip-sync extraction. |
| `max_screen_fps` | `integer` | `2` | Configurable maximum `memfd` screen frame uplink rate (`1..=60` FPS, default `2` FPS) when `window.damage_settled` reports changes. |
| `static_screen_zero_fps` | `bool` | `true` | Drops visual uplink to `0 FPS` when perceptual hash is unchanged, saving `~80%` visual tokens. |
| `proactive_audio` | `bool` | `true` | Enables `Proactive Audio` gating so the model stays silent unless addressed or triggered. |
| `context_compression_trigger_tokens` | `integer` | `24000` | Token threshold triggering server-side `contextWindowCompression`. |
| `sliding_window_tokens` | `integer` | `16000` | Target token window retained after sliding-window compression. |
| `session_resumption` | `bool` | `true` | Tracks `SessionResumptionUpdate` handles and auto-reconnects on `GoAway` across the 10-minute WebSocket ceiling. |
| `default_tool_scheduling` | `string` | `"WHEN_IDLE"` | Default `NON_BLOCKING` `toolResponse` continuation scheduling (`"INTERRUPT"`, `"WHEN_IDLE"`, `"SILENT"`). |

### 2.5 `[jikubox.triage]` (Multimodal Batch Classification & Screening via `DecisionBackend`)

Configures `jiku box classify` batch evaluation over `~/JikuBox/` using `DecisionBackend` (`NativeDecisionsApi` when `gemini-decision-1` is configured, or automatic `EmulatedStructuredTextModel` fallback on `[roles.planner]`):

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `enabled` | `bool` | `true` | Enables structured batch screening and tagging for `~/JikuBox/`. |
| `driver` | `string` | `"decision_router"` | Routes batch evaluation through `DecisionBackend` (`NativeDecisionsApi` or `EmulatedStructuredTextModel` fallback). |
| `max_questions_per_batch` | `integer` | `1000` | Questions packed per multimodal file (`1..=1000`; `0` output tokens under `NativeDecisionsApi`). |
| `decompose_rubrics_to_noul` | `bool` | `true` | Automatically decomposes coarse `Score` rubrics into `5..=10` binary `Yes/No` (`noul`) checklist questions for higher calibration. |
| `two_stage_ranking` | `bool` | `true` | Runs binary `noul` coarse screening before fine-grained rubric scoring. |

### 2.6 `[memory]`, `[notify]` & Progressive Optional Modules (`[tts]`, `[avatar]`)

* **`[memory]`**: `backend = "sqlite_fts5"` (default), `l0_frame_ring_size = 4`, `fts5_rerank_with_decisions = true` (reranks top-`K` FTS5 candidates via `DecisionBackend` using `NativeDecisionsApi` or `EmulatedStructuredTextModel`), `stage_new_skills = true`, optional `external_mcp_command` for external `MemoryProvider` bridging.
* **`[notify]`**: `desktop_dbus = true` (`org.freedesktop.Notifications` -> `swaync`), `urgency_on_verification = "critical"`, optional `webhook_url_env`.
* **`[tts]` (`jiku-tts` — Progressive Optional Module, Disabled by Default)**: `enabled = false` (default), `provider = "voicevox" | "piper" | "openai_speech"`, `endpoint = "http://127.0.0.1:50021"`, `speaker_id = 3`, `speak_on = ["task_completed", "verification_needed"]` (decoupled optional module used in turn mode when explicitly enabled; bypassed in native `24 kHz PCM` `jiku live` mode).
* **`[avatar]` (Live2D / VRM Subscriber Bus — Progressive Optional Module, Disabled by Default)**: `emit_cues = false` (default), `expression_palette_size = 255` — when explicitly enabled (`emit_cues = true`), broadcasts real-time `AvatarCue` frames (emotion tag, discrete `expression_id` / `motion_id` up to `255` options, `(u, v)` virtual cursor gaze, and either VOICEVOX mora envelopes or live `24 kHz` RMS/frequency lip-sync envelopes) to any subscribed Live2D / VRM `wlr-layer-shell` companion client on `jiku.sock`.

### 2.7 Example `config.toml` Snippet

```toml
# 1. Foundational Primary Text/Multimodal Model (Required — OpenAI, Anthropic, Gemini, OpenRouter, or local vLLM/llama.cpp/Ollama)
[roles.planner]
provider = "openai_or_local"
model = "gpt-5.4" # or "claude-sonnet-4-6", "gemini-2.5-pro", "qwen3-vl-32b-instruct"

# 2. Optional Decision Model Acceleration (DecisionBackend)
# - If model = "gemini-decision-1", runs DecisionExecutionMode::NativeDecisionsApi (0 output tokens, single prefill).
# - If omitted or set to a general text/VLM model, Jiku NEVER errors out: it automatically falls back to
#   DecisionExecutionMode::EmulatedStructuredTextModel via synthesize_emulated_decision_prompt + JSON Schema response_format
#   returning the identical {"answers": { ... }} structure so DecisionCompiler runs unchanged.
[roles.decision_router]
provider = "google_ai_studio"
model = "gemini-decision-1"
execution_mode = "auto"
confidence_threshold = 0.85
fallback_role = "planner"
max_questions_per_request = 1000
require_none_or_other = true
safety_gate_rules = 15
media_mime_type = "image/webp"

[roles.decision_router.compiler]
fast_path_confidence = 0.85
min_cell_prob = 0.05
time_slot_min_confidence = 0.75
bernoulli_activation_threshold = 0.80
probe_min_prob = 0.15
stop_sentinel = "stop_done"
fallback_token = "NONE_OR_OTHER"

[roles.decision_router.compiler.grid]
cols = 15
rows = 15

[jikubox.triage]
enabled = true
driver = "decision_router"
max_questions_per_batch = 1000
decompose_rubrics_to_noul = true
two_stage_ranking = true

# 3. Progressive Optional Modules (Decoupled & Disabled by Default unless explicitly enabled)
[tts]
enabled = false
provider = "voicevox"
endpoint = "http://127.0.0.1:50021"
speaker_id = 3

[roles.live_companion]
enabled = false
provider = "google_ai_studio"
protocol = "gemini_bidi"
model = "gemini-2.5-flash-live"
audio_in_sample_rate_hz = 16000
audio_out_sample_rate_hz = 24000
max_screen_fps = 2
static_screen_zero_fps = true
proactive_audio = true
context_compression_trigger_tokens = 24000
sliding_window_tokens = 16000
session_resumption = true
default_tool_scheduling = "WHEN_IDLE"

[avatar]
emit_cues = false
expression_palette_size = 255
```

---

## 3. `jiku` CLI, Detachable TUI & External Coding Agent Bridge (`Claude Code`, `Codex`, `GitHub Copilot`, `Cursor`, `OpenCode`)

```bash
# Launch interactive ratatui TUI attached to running jikud (closing TUI leaves jikud running)
jiku

# Submit a background GUI task from terminal or an external Coding Agent (Claude Code / Codex / GitHub Copilot / Cursor / OpenCode)
# (Routes via DecisionBackend >=0.85 fast-path — NativeDecisionsApi or EmulatedStructuredTextModel — with automatic [roles.planner] escalation)
jiku run --workspace agent:work "Export ~/JikuBox/draft.odt to PDF in LibreOffice"

# Fast deterministic window/workspace inspection via komactl + SKILL.md for external coding agents
komactl tree --json

# Expose Jiku as an MCP server over stdio for Claude Code, Codex, GitHub Copilot, Cursor, or OpenCode
# (--stateless disables episode history recall when the external master coding agent manages its own memory)
jiku mcp --stateless

# Run batch classification, tagging & rubric screening on ~/JikuBox/
# (Uses NativeDecisionsApi 0-output-token pass when gemini-decision-1 is configured, or EmulatedStructuredTextModel fallback)
jiku box classify ~/JikuBox/inbox --rubric ~/.config/jiku/triage_rubric.toml --out ~/JikuBox/triaged/report.json

# Start or attach to an optional Stateful Full-Duplex WebSocket companion session (requires [roles.live_companion] enabled = true)
jiku live --workspace agent:work --proactive-audio

# Inspect live daemon status, active DecisionExecutionMode, leased workspaces, and current Epoch
jiku status

# Review and promote a staged Lua skill into ~/.config/jiku/skills/ (runs outside jikud ro mount)
jiku skills list
jiku skills diff libreoffice_pdf_export
jiku skills approve libreoffice_pdf_export
```

---

## 4. `jiku.sock` EventBus Wire Envelope (TUI, TTS & Live2D Subscribers)

Clients connecting to `$XDG_RUNTIME_DIR/jiku.sock` use the same 4-byte little-endian length-prefixed JSON framing as `koma-proto` and can subscribe to `["task.progress", "skill.staged", "tts.utterance", "avatar.cue"]`.

### 4.1 Turn-Mode VOICEVOX Mora Lip-Sync Envelope (`avatar.cue`)

When `TurnModelDriver` + `TtsProvider` (`voicevox`) speaks a turn summary, `avatar.cue` carries exact phoneme/mora durations and pitch contours:

```json
{
  "seq": 88,
  "topic": "avatar.cue",
  "payload": {
    "driver": "turn_tts",
    "emotion": "thinking",
    "expression_id": 14,
    "motion_id": 3,
    "gaze_uv": [0.62, 0.35],
    "interrupted": false,
    "utterance_locale": "ja-JP",
    "mora_envelope": [
      { "phoneme": "k", "vowel": "o", "duration_ms": 95, "pitch": 5.82 },
      { "phoneme": "m", "vowel": "a", "duration_ms": 110, "pitch": 5.95 }
    ]
  }
}
```

### 4.2 Live-Mode `24 kHz PCM` RMS / Frequency-Band Lip-Sync Envelope (`avatar.cue`)

When `LiveSessionDriver`'s `Downlink` task streams native `24 kHz PCM` audio to PipeWire (or flushes playback upon server VAD `serverContent: { interrupted: true }` barge-in), `avatar.cue` broadcasts real-time RMS amplitude, three-band vowel formant energies, and `DecisionsDriver` 255-cue selections:

```json
{
  "seq": 142,
  "topic": "avatar.cue",
  "payload": {
    "driver": "live_session",
    "emotion": "acting",
    "expression_id": 128,
    "motion_id": 42,
    "gaze_uv": [0.48, 0.71],
    "interrupted": false,
    "sample_rate_hz": 24000,
    "rms_envelope": {
      "frame_ms": 20,
      "rms_db": -14.2,
      "mouth_open_0_1": 0.68,
      "freq_bands_hz": {
        "low_200_800": 0.74,
        "mid_800_2500": 0.59,
        "high_2500_6000": 0.21
      }
    }
  }
}
```
