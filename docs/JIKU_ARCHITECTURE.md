# Jiku (`jiku` / `jikud`) Native Desktop Agent Architecture Specification

> **Status**: Architecture Baseline v0.2
> **Binary & Daemon Names**: `jikud` (Background daemon), `jiku` (Detachable TUI / CLI & `jiku mcp` bridge)
> **Configuration & State**: `~/.config/jiku/{config.toml, init.lua, skills/*.lua}` (Read-Only in sandbox), `~/.local/state/jiku/` (Read-Write), `~/JikuBox/` (Explicit file exchange dropbox)
> **Companion Compositor**: `Koma` (`komawm`) via `$XDG_RUNTIME_DIR/koma/<sig>/koma-agent.sock`

---

## 1. Positioning, Naming & Process Boundary

`Jiku` (from Japanese **軸 / じく**, the stabilizing central axis that spins and balances a top **独楽 / `Koma`**) is the first-class, out-of-process desktop GUI orchestration agent designed specifically for `Koma`.

Following the strict Unix separation established in `docs/ARCHITECTURE.md` (and analogous to the decoupling between `bitty` and `wheel`), `Koma` and `Jiku` live in **separate binaries, separate configuration trees, and separate failure domains**:

1. **Zero Network or Inference Bloat Inside `Koma`**: `Koma` remains a pure real-time Wayland compositor (`Smithay` + `calloop` + `libseat` + `Phodopus`) with zero HTTP/TLS dependencies, zero OCR/image encoders on its `240 Hz` render thread, and deterministic sub-millisecond `Mod + G` Ring 0 preemption.
2. **Rust Trunk + Embedded `Phodopus` Lua 5.4 Brain**: `jikud` compiles to a single static Rust binary handling zero-copy `SCM_RIGHTS` `memfd` frame mapping, perceptual block-hash deduplication, ROI image cropping, async HTTP/2 SSE model streaming, SQLite WAL + FTS5 persistence, and `Landlock` kernel self-sandboxing, while embedding the same pure-Rust stackless Lua 5.4 VM (`Phodopus`) used by `Koma` for hot-reloadable policy hooks (`~/.config/jiku/init.lua`) and parameterized GUI skills (`skills/*.lua`).

---

## 2. User Identity, Filesystem Isolation & Orthogonal Dual-Layer Sandbox

### 2.1 Same-UID Session Topology (Why No Separate `/home/jiku` OS User)

`jikud` runs under the **active desktop user's UID** (managed by `systemd --user`) rather than a separate `/home/jiku` system account:

* **Preserving `$XDG_RUNTIME_DIR` (`0700`) & `SO_PEERCRED` Integrity**: On modern Linux sessions (`pam_systemd`), `/run/user/<UID>` is a mode-`0700` `tmpfs`. Running under a different UID would break access to `koma-agent.sock` and restricted Wayland jail sockets unless directory ACLs were weakened, undermining `Koma`'s `SO_PEERCRED` same-UID peer verification and creating file-ownership friction when exchanging artifacts.
* **Mount-Namespace `$HOME` Masking (`Empty Home + Explicit Allowlist`)**: Instead of a separate UNIX UID, `jikud` launches inside an unprivileged mount namespace (`ProtectHome=tmpfs` in `systemd --user` or `bwrap --tmpfs $HOME`) that replaces `$HOME` with an empty in-memory `tmpfs` and bind-mounts **only three explicit paths**:

| Host Path | Mount Mode Inside `jikud` | Purpose & Security Invariant |
| :--- | :--- | :--- |
| **`~/.config/jiku/`** | **Read-Only (`ro`)** | Holds `config.toml`, `init.lua`, and approved `skills/*.lua`. Read-only mounting guarantees `jikud` can **never self-modify** its own configuration, provider endpoints, or approved skills at runtime. |
| **`~/.local/state/jiku/`** | **Read-Write (`rw`)** | Holds `state.db` (SQLite WAL + FTS5 memory), audit logs, perceptual hash caches, and `staged_skills/` awaiting human approval. |
| **`~/JikuBox/`** | **Read-Write (`rw`)** | Explicit human <-> `Jiku` file dropbox for input assets and exported reports. `~/.ssh`, `~/.gnupg`, `~/.config/koma`, browser profiles, and source repositories **do not exist** in `jikud`'s filesystem view. |
| **`$XDG_RUNTIME_DIR/koma/<sig>/koma-agent.sock`** | **Socket Bind (`rw`)** | Scoped Agent RPC & `SCM_RIGHTS` `memfd` socket (`koma-admin.sock` and the host's unrestricted `wayland-0` socket are never mounted). |

### 2.2 Strict Capability Stripping: Why `Jiku` Has Zero Generic Shell Access

Unlike AI Coding Agents (`Claude Code`, `Codex`, `Copilot`, `OpenCode`) whose core job is editing source trees and running arbitrary `sh`/`bash` pipelines, **`Jiku` deliberately omits any generic Shell execution tool**:

1. **Blocking Visual Prompt Injection -> RCE**: `Jiku` continuously inspects untrusted visual content (web pages, chat windows, PDFs, third-party GUI apps). Without `sh`/`execve` privileges, even a successful visual prompt injection is strictly confined to synthetic pointer/keyboard events inside an isolated `Headless` workspace and cannot escalate to arbitrary host command execution.
2. **Kernel Self-Locking (`Landlock` LSM + `NoNewPrivileges`)**: Immediately after startup config parsing, `jikud` enforces `prctl(PR_SET_NO_NEW_PRIVS, 1)` and applies a Linux `Landlock` ruleset restricting filesystem access to the three paths above, system TLS certificates, and outbound HTTPS model/TTS endpoints—denying `LANDLOCK_ACCESS_FS_EXECUTE` on host binaries.
3. **Declarative App Profiles Instead of Arbitrary Spawn**: When `Jiku` needs to launch a GUI application (e.g., Chromium, LibreOffice, Blender), it requests a named allowlisted profile (`profile = "chromium-research"`). `Koma` spawns the container (`bwrap` / `podman`) bound to a dedicated `wp-security-context-v1` Wayland jail socket pinned to `agent:work`, blocking `zwlr_layer_shell_v1`, clipboard snooping, and virtual keyboard injection outside the jail.
4. **Inner `Phodopus` Lua Sandbox**: All policy hooks, skills, and model-synthesized micro-transactions execute inside `Phodopus` with `io`, `os`, `package.loadlib`, and `debug` stripped, bounded by deterministic `InstructionBudget` fuel and `gc-arena` heap ceilings.
5. **Hardware Blackout & `< 1 ms` `Mod + G` Human Preemption**: Windows matching `block_out_from = "agent_capture" | "all"` (password managers, Polkit dialogs) are masked to solid `#000000` in `Koma`'s offscreen FBO before `memfd` export, and pressing `Mod + G` immediately increments `Epoch`, flushes held `VirtualSeat` keys, and aborts any in-flight `Jiku` transaction.

---

## 3. Three-Tier AI Ecosystem: Native `Jiku` + `SKILL.md` CLI + `MCP`

`Koma` and `Jiku` support both first-class autonomous operation and zero-friction integration with external AI Coding Agents:

```
  [Claude Code / Codex / OpenCode]          [Desktop MCP Clients (Cursor, etc.)]
         |                  \                            |
   (Fast Inner Loop:         \ (Sub-task Delegation:     | (Standard stdio MCP:
    SKILL.md + komactl)       \ `jiku run "..."`)        |  `jiku mcp` / `koma-mcp`)
         |                     v                         v
         |              +---------------------------------------+
         |              |     jikud (Native Companion Agent)    |
         |              |  EventRing Push + ROI Hash + Phodopus |
         |              +---------------------------------------+
         \                                  |
          \---> $XDG_RUNTIME_DIR/koma/<sig>/koma-agent.sock <---/
                      (SCM_RIGHTS memfd + Epoch Fence)
```

* **Native `jikud` Advantages over Generic Computer Use**:
  1. **Push-Driven `EventRing`**: Subscribes to `window.topology`, `window.damage_settled`, `workspace.lease`, and `security.alerts`—eliminating blind screenshot polling loops.
  2. **Batched `Phodopus` Micro-Transactions**: Compiles multi-step GUI sequences (`focus -> move_to -> click -> Zero-IME type_text -> wait_settle`) into a single `Epoch`-fenced Lua coroutine executed inside `Koma` at microsecond latency.
  3. **Scene-Tree + Zero-Copy `memfd` Fusion**: Combines `mmap`-read `memfd` pixel tiles (skipping VLM calls on unchanged perceptual hashes) with exact compositor window coordinates (`WindowId`, `app_id`, logical `rect`).
* **Orthogonal Division with Coding Agents**: Coding Agents (`Claude Code`, `Codex`) own source code and terminal builds, using a compact `SKILL.md` + `komactl` for fast window queries or delegating end-to-end visual verification (`jiku run "verify login modal flow in agent:work"`) without polluting the coding model's context window with dozens of raw screenshots; pure GUI clients attach via `jiku mcp`.

---

## 4. Pluggable 3-Tier Memory & Context Architecture (`ContextProvider`)

Inspired by autonomous agents such as `Hermes Agent`—while deliberately trimming away conversational persona bloat and coding-specific background reflection—`Jiku` implements a focused **"GUI Muscle Memory"** core behind an extensible async Rust trait:

```rust
#[async_trait::async_trait]
pub trait ContextProvider: Send + Sync {
    /// Assembles bounded prompt context (active app quirks + relevant FTS5 episodes) before planning.
    async fn prefetch(&self, query: &PrefetchQuery) -> anyhow::Result<PrefetchedContext>;
    /// Appends a single verified step (`obs_hash`, `action`, `epoch`, `outcome`) to trajectory storage.
    async fn record_step(&self, step: &EpisodeStepRecord) -> anyhow::Result<()>;
    /// Writes a candidate reusable Lua macro into `staged_skills/` for human review (`write_approval`).
    async fn stage_skill(&self, candidate: &StagedSkillProposal) -> anyhow::Result<StagedSkillId>;
    /// Flushes WAL state on episode completion or daemon shutdown.
    async fn flush(&self) -> anyhow::Result<()>;
}
```

### 4.1 Built-In Three-Tier Storage (`~/.local/state/jiku/state.db`)

1. **L0 Sliding Visual Ring (In-Memory)**: Retains only the most recent `3..=5` changed ROI crops + structured window-tree diffs. Older visual frames are immediately compacted into single-line structured action records so long GUI workflows never blow up VLM token budgets.
2. **L1 Per-`app_id` UI Quirks Cards (Prefix-Cache Friendly)**: Short, bounded (~150-word) operational notes keyed by Wayland `app_id` (e.g., `org.blender.Blender`, `wps-office-et`, `chromium`), injected **only** at session start or when that `app_id` maps into the target workspace—preserving LLM prompt prefix caches.
3. **L2 Trajectory FTS5 Index & `staged_skills/` Approval Gate**:
   * Single-file SQLite database in `WAL` mode with native **FTS5** full-text indexing over task goals, `app_id`, window titles, and recovery notes—zero mandatory local embedding model overhead.
   * **Staged Skill Write-Approval Gate**: Because `~/.config/jiku/skills/` is mounted read-only, newly synthesized Lua macros from successful runs are sanitized (scanning for invisible Unicode / prompt-injection patterns) and written to `~/.local/state/jiku/staged_skills/<name>.lua`. The user inspects and promotes them explicitly via `jiku skills diff <name>` and `jiku skills approve <name>`.

### 4.2 Three Extension Seams

* **Lua Policy Hooks (`~/.config/jiku/init.lua`)**: `jiku.memory.on_prefetch(ctx)` and `jiku.memory.on_episode_end(ep)` allow custom filtering, `app_id` prompt shaping, or exporting Markdown run summaries into `~/JikuBox/` without recompiling Rust.
* **External `MemoryProvider` Plugins (`config.toml`)**: Optional `sqlite-vec` local vector adapter or external MCP memory bridge (`provider = "mcp_bridge"`).
* **Stateless Passthrough (`jiku mcp --stateless`)**: When driven by an external master agent (`Claude Code` or `Hermes Agent`) that already manages conversation memory, `Jiku` bypasses episode history recall and serves only L1 `app_id` UI quirks + approved deterministic GUI skills.

---

## 5. Native Runtime: Model Templates, Detachable TUI, Notifications, TTS & Live2D Bus

When used directly as a standalone desktop assistant (without an external MCP host), `jikud` exposes a local control & event bus at **`$XDG_RUNTIME_DIR/jiku.sock`** (`0600`):

### 5.1 Declarative Model Templates & Heterogeneous Role Routing

`config.toml` separates **Provider Templates** (`openai_compatible`, `anthropic`, `google_gemini`) from **Role Assignments**:

* **`planner`**: High-reasoning model decomposing multi-app goals and selecting parameterized `skills/*.lua` macros.
* **`actor` (Decision / Computer Use Models)**: Fast visual grounding & action models—natively supporting specialized decision APIs (such as `gemini-decision-1` `grid_225` / macro selection and Gemini Computer Use `0..1000` normalized coordinates) as well as general VLMs via a unified **`ActionNormalizer`** that maps model outputs into `Koma` logical workspace coordinates or `9-anchor` window offsets.
* **`fast_guard`**: Lightweight local or flash model verifying modal popups, error banners, and completion states.

### 5.2 Detachable `jiku` TUI / CLI & Asynchronous User Notifications

* **Stateless Frontend (`jiku`)**: Closing the `jiku` TUI (`ratatui`) or terminal window **never** stops `jikud`; background tasks continue inside `agent:work`, and running `jiku` (or `jiku attach`) reconnects to `jiku.sock` to stream live steps, approve staged skills, or pause/abort tasks.
* **Proactive User Notifications**: On task completion, error, or human-verification gates (`security.verification_needed`, e.g., 2FA / login / payment prompts), `jikud` dispatches desktop notifications via **D-Bus `org.freedesktop.Notifications`** (integrating natively with `swaync` action buttons such as *"Peek Workspace"* or *"Approve"*), plus optional webhook plugins for remote alerts.

### 5.3 Multi-Language (`i18n`), TTS Audio Pipeline & Live2D / VTuber Subscriber Bus

Voice synthesis and 2D/3D avatars attach as **decoupled `jiku.sock` EventBus subscribers** so `jikud` stays lean and headless-safe:

* **i18n & Pluggable `TtsProvider`**: Explicit locale configuration (`zh-CN`, `ja-JP`, `en-US`) paired with a `TtsProvider` trait supporting **VOICEVOX Engine** (`/audio_query` + `/synthesis` for natural Japanese voicebanks), local **Piper / CosyVoice**, or OpenAI-compatible `/v1/audio/speech` streamed to **PipeWire**.
* **Live2D / VRM Companion Protocol**: `jikud` broadcasts structured `AvatarCue` events over `jiku.sock` containing:
  1. **Semantic Emotion & Activity State** (`Idle`, `Thinking`, `Acting`, `WaitingHuman`, `Success`, `Alert`),
  2. **Normalized Gaze Target** `(u, v)` tracking `Jiku`'s active virtual pointer or highlighted window region, and
  3. **Phoneme / Mora Lip-Sync Envelope** (extracted directly from VOICEVOX `AudioQuery` mora timings or RMS amplitude frames).
  A separate `wlr-layer-shell` overlay client (rendering Live2D Cubism or VRM models) can subscribe to `jiku.sock` at any time without adding a single OpenGL dependency to `jikud` or `Koma`.
