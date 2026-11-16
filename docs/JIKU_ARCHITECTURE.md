# Jiku (`jiku` / `jikud`) Native Desktop Agent Architecture Specification

> **Status**: Architecture Baseline v0.3
> **Binary & Daemon Names**: `jikud` (Background daemon), `jiku` (Detachable TUI / CLI & `jiku mcp` bridge)
> **Configuration & State**: `~/.config/jiku/{config.toml | config.lua, init.lua, skills/*.lua}` (Read-Only in sandbox), `~/.local/state/jiku/` (Read-Write), `~/JikuBox/` (Explicit file exchange dropbox)
> **Companion Compositor**: `Koma` (`komawm`) via `$XDG_RUNTIME_DIR/koma/<sig>/koma-agent.sock`

---

## 1. Positioning, Naming & Process Boundary

`Jiku` (from Japanese **軸 / じく**, the stabilizing central axis that spins and balances a top **独楽 / `Koma`**) is the first-class, out-of-process desktop GUI orchestration agent designed specifically for `Koma`.

Following the strict Unix separation established in `docs/ARCHITECTURE.md` (and analogous to the decoupling between `bitty` and `wheel`), `Koma` and `Jiku` live in **separate binaries, separate configuration trees, and separate failure domains**:

1. **Zero Network or Inference Bloat Inside `Koma`**: `Koma` remains a pure real-time Wayland compositor (`Smithay` + `calloop` + `libseat` + `Phodopus`) with zero HTTP/TLS dependencies, zero OCR/image encoders on its `240 Hz` render thread, and deterministic sub-millisecond `Mod + G` Ring 0 preemption.
2. **Rust Trunk + Embedded `Phodopus` Lua 5.4 Brain**: `jikud` compiles to a single static Rust binary handling zero-copy `SCM_RIGHTS` `memfd` frame mapping, perceptual block-hash deduplication, ROI image cropping, heterogeneous model drivers (`DecisionsDriver`, `TurnModelDriver`, `LiveSessionDriver`), SQLite WAL + FTS5 persistence, and `Landlock` kernel self-sandboxing, while embedding the same pure-Rust stackless Lua 5.4 VM (`Phodopus`) used by `Koma` for hot-reloadable policy hooks (`~/.config/jiku/init.lua`) and parameterized GUI skills (`skills/*.lua`).

---

## 2. User Identity, Filesystem Isolation & Orthogonal Dual-Layer Sandbox

Configuration and policy share one sandbox profile: `config.lua` and `init.lua` are both evaluated by the embedded Phodopus Lua 5.4 VM under an `8 MiB` `gc-arena` heap ceiling and a deterministic instruction budget, with `io`, `os`, `dofile`, and `loadfile` removed. Neither file can read the environment or the filesystem, so `api_key_env` stays a variable *name* in both `config.toml` and `config.lua`.

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
2. **Kernel Self-Locking (`Landlock` LSM + `NoNewPrivileges`)**: Immediately after startup config parsing, `jikud` enforces `prctl(PR_SET_NO_NEW_PRIVS, 1)` and applies a Linux `Landlock` ruleset restricting filesystem access to the three paths above, system TLS certificates, and outbound HTTPS/WSS model/TTS endpoints—denying `LANDLOCK_ACCESS_FS_EXECUTE` on host binaries.
3. **Declarative App Profiles Instead of Arbitrary Spawn**: When `Jiku` needs to launch a GUI application (e.g., Chromium, LibreOffice, Blender), it requests a named allowlisted profile (`profile = "chromium-research"`). `Koma` spawns the container (`bwrap` / `podman`) bound to a dedicated `wp-security-context-v1` Wayland jail socket pinned to `agent:work`, blocking `zwlr_layer_shell_v1`, clipboard snooping, and virtual keyboard injection outside the jail.
4. **Inner `Phodopus` Lua Sandbox**: All policy hooks, skills, and model-synthesized micro-transactions execute inside `Phodopus` with `io`, `os`, `package.loadlib`, and `debug` stripped, bounded by deterministic `InstructionBudget` fuel and `gc-arena` heap ceilings.
5. **Hardware Blackout & `< 1 ms` `Mod + G` Human Preemption**: Windows matching `block_out_from = "agent_capture" | "all"` (password managers, Polkit dialogs) are masked to solid `#000000` in `Koma`'s offscreen FBO before `memfd` export, and pressing `Mod + G` immediately increments `Epoch`, flushes held `VirtualSeat` keys, and aborts any in-flight `Jiku` transaction.

---

## 3. Three-Tier AI Ecosystem: Standalone `Jiku` + External Coding Agent Bridge (`SKILL.md` CLI & `MCP`)

`Jiku` works out-of-the-box both as a **standalone customizable desktop agent** (powered by any user-configured cloud or local text/VLM provider in `~/.config/jiku/config.toml`) and as a **sub-agent / tool bridge** invoked by external AI Coding Agents (**`Claude Code`**, **`Codex`**, **`GitHub Copilot`**, **`Cursor`**, **`OpenCode`**) via **MCP (`jiku mcp`)** or **CLI + `SKILL.md` (`jiku run ...`, `komactl`)**:

```
  [Claude Code / Codex / GitHub Copilot / OpenCode]   [MCP Clients (Cursor, Claude Code, etc.)]
         |                       \                                |
   (Fast Inner Loop:              \ (Sub-task Delegation:         | (Standard stdio MCP:
    SKILL.md + komactl)            \ `jiku run "..."`)            |  `jiku mcp` / `koma-mcp`)
         |                          v                             v
         |                   +---------------------------------------+
         |                   |     jikud (Native Companion Agent)    |
         |                   |  EventRing Push + ROI Hash + Phodopus |
         |                   +---------------------------------------+
         \                                       |
          \--------> $XDG_RUNTIME_DIR/koma/<sig>/koma-agent.sock <----/
                            (SCM_RIGHTS memfd + Epoch Fence)
```

* **Standalone Customizable Desktop Agent**:
  Users can run `jikud` + `jiku` directly as an autonomous desktop operator backed by their preferred primary text/multimodal LLM (OpenAI GPT, Anthropic Claude, Google Gemini, OpenRouter, or self-hosted local models via `vLLM`, `llama.cpp`, or `Ollama`).
* **External Coding Agent Bridge (`Claude Code`, `Codex`, `GitHub Copilot`, `Cursor`, `OpenCode`)**:
  External coding agents own source code editing and terminal builds, integrating with `Jiku` and `Koma` through two complementary surfaces:
  1. **CLI + `SKILL.md` (`jiku run ...`, `komactl`)**: Coding agents read the bundled `SKILL.md` to issue fast deterministic window queries via `komactl` or delegate multi-step visual GUI verification (`jiku run --workspace agent:work "verify login modal flow"`) to `jikud` without polluting the coding model's context window with dozens of raw screenshots.
  2. **MCP Server (`jiku mcp` / `jiku mcp --stateless`)**: Exposes `Jiku`'s GUI task execution, `app_id` UI quirks, and approved deterministic Lua skills as standard Model Context Protocol tools over `stdio` for `Claude Code`, `Codex`, `GitHub Copilot`, `Cursor`, and `OpenCode`.
* **Native `jikud` Advantages over Generic Computer Use**:
  1. **Push-Driven `EventRing`**: Subscribes to `window.topology`, `window.damage_settled`, `workspace.lease`, and `security.alerts`—eliminating blind screenshot polling loops.
  2. **Batched `Phodopus` Micro-Transactions**: Compiles multi-step GUI sequences (`focus -> move_to -> click -> Zero-IME type_text -> wait_settle`) into a single `Epoch`-fenced Lua coroutine executed inside `Koma` at microsecond latency.
  3. **Scene-Tree + Zero-Copy `memfd` Fusion**: Combines `mmap`-read `memfd` pixel tiles (skipping VLM calls on unchanged perceptual hashes) with exact compositor window coordinates (`WindowId`, `app_id`, logical `rect`).

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

## 5. Primary Text/VLM Foundation & Three-Driver Model Architecture in `jikud`

### 5.0 Primary Text/Multimodal Model First (`[roles.planner]`) & Progressive Optional Drivers

The **Primary Text/Multimodal Model** (`[roles.planner]` backed by `TurnModelDriver`—supporting OpenAI GPT, Anthropic Claude, Google Gemini, OpenRouter, or self-hosted local models via `vLLM` / `llama.cpp` / `Ollama`) is the **foundational model of `Jiku`**. Configuring only a primary text/VLM model is sufficient to run every core `Jiku` workflow out of the box without errors.

Rather than forcing every desktop interaction through a single endpoint when optional accelerators are present, `jikud` partitions inference across **three specialized model drivers** matched to the latency, output cardinality, and duplex requirements of each workload:

1. **`TurnModelDriver` (Foundational Primary Text/VLM Driver)**: Autoregressive turn-based HTTP/2 SSE driver (`reqwest`) powering `[roles.planner]` for open-ended planning, free-form text input, Lua skill synthesis, and automatic **`EmulatedStructuredTextModel`** fallback when no dedicated decision model is configured.
2. **`DecisionsDriver` / `DecisionBackend` (Optional Zero-Decode Acceleration + Zero-Error Emulated Fallback)**: Evaluates closed-set probability distributions (`noul`, `choice`, `score`) via **`DecisionExecutionMode::NativeDecisionsApi`** when a dedicated Decision Model (reached through Google AI Studio `POST /v1beta/decisions`, authenticated with the provider key named by `api_key_env`) is configured, or automatically falls back to **`DecisionExecutionMode::EmulatedStructuredTextModel`** on the primary text/VLM model without ever erroring out.
3. **`LiveSessionDriver` (Optional Progressive Module, Disabled by Default)**: Stateful full-duplex WebSocket driver (`tokio-tungstenite` / `BidiGenerateContent`) for real-time voice, vision, and low-latency action multiplexing (`jiku live`), enabled only when explicitly opted in via `config.toml`.

```
                      +------------------------------------------------+
                      |         Koma Compositor (koma-agent.sock)      |
                      |   SCM_RIGHTS memfd + Damage EventRing + Epoch  |
                      +------------------------------------------------+
                                |              |                 ^
         (1) Fast System-1 Gate |              | (3) 1-2 FPS     | Epoch-Fenced
             (<250 ms Prefill)  v              v     + 16kHz PCM | Non-Blocking Actions
      +----------------------------+    +----------------------------------+
      |      DecisionsDriver       |    |        LiveSessionDriver         |
      |   native decision model    |    |   Stateful Full-Duplex WebSocket |
      |   POST /v1beta/decisions   |    |  (Uplink / Downlink / ActBridge) |
      +----------------------------+    +----------------------------------+
           |                  |
  (>=0.85) |                  | (<0.85 or Open-Ended Synthesis)
  Direct   |                  v
  Dispatch |        +------------------------------------+
           |        |          TurnModelDriver           |
           +------->|      reqwest + HTTP/2 SSE          |
                    | (Planner / Free-Form Text / Lua)   |
                    +------------------------------------+
```

---

### 5.1 `DecisionsDriver` & `DecisionBackend` (`DecisionExecutionMode`: `NativeDecisionsApi` + `EmulatedStructuredTextModel` Fallback)

`DecisionBackend` provides a unified closed-set decision engine supporting two execution modes (`DecisionExecutionMode`):

1. **`DecisionExecutionMode::NativeDecisionsApi` (Optional Dedicated Decision Model Acceleration)**:
   When a dedicated Decision Model (reached through Google AI Studio's `POST https://generativelanguage.googleapis.com/v1beta/decisions`, authenticated with the provider key named by `api_key_env`) is configured, `Jiku` uses **`NativeDecisionsApi`** (`0` output tokens, single prefill pass) for closed-set tasks where decision models excel:
   * GUI `grid_225` targeting and sub-grid centroid interpolation (`interpolate_grid_225_centroid`),
   * `DecisionCompiler` multi-step shortcut sequences (`TimeSlotMacro`, `BernoulliExpectedStep`, `ThresholdProbe`),
   * 15-rule parallel visual safety gates (`q_safety_gate`),
   * `~/JikuBox/` multimodal tagging, screening, and rubric grading, and
   * L2 SQLite FTS5 trajectory and skill reranking.
2. **`DecisionExecutionMode::EmulatedStructuredTextModel` (Zero-Error Automatic Fallback to Primary Text/VLM Model)**:
   When **no** dedicated Decision Model is configured (or when the user assigns a general text/VLM model such as OpenAI GPT, Anthropic Claude, Google Gemini, OpenRouter, or self-hosted `vLLM` / `llama.cpp` / `Ollama` to the decision role), **`Jiku` never errors out**. Instead, `DecisionBackend` automatically falls back to **`EmulatedStructuredTextModel`**:
   * Invokes **`synthesize_emulated_decision_prompt`** + strict JSON Schema constraints (`response_format`) on the primary text/VLM model (`[roles.planner]` or the configured general model) to output the exact same `{"answers": { ... }}` structure (`noul`, `choice`, and `score` probabilities and confidence).
   * Downstream `DecisionCompiler` logic (`TimeSlotMacro`, `BernoulliExpectedStep`, `ThresholdProbe`), `interpolate_grid_225_centroid`, and confidence-router logic run **unchanged** across both `NativeDecisionsApi` and `EmulatedStructuredTextModel`.

#### Zero-Decode Single-Prefill Mechanism & Wire JSON Contract (`NativeDecisionsApi`)

Unlike standard generative LLMs that decode output tokens autoregressively one token at a time, a dedicated decision model performs **Single-Prefill Zero-Decode Evaluation**:

* **`0` Output Tokens Generated**: The model runs a single forward prefill pass over one shared multimodal context (text + inline image/audio/PDF/video bytes) and evaluates **`1..=1000` parallel structured questions** simultaneously in the same request, billing `0` output tokens (`usage.total_output_tokens == 0`).
* **Three Native Question Primitives**:
  1. **`noul` (`Yes/No`)**: Binary probability scalar clamped in **`[0.01, 0.99]`** for scope gates, safety checklists, and binary relevance verification.
  2. **`choice` (`2..=255` options)**: Mutually exclusive categorical probability distribution over a `criteria` map (`key -> description`), returning the top `choice` key and `probabilities` summing to **`1.0`**.
  3. **`score` (`2..=255` levels)**: Ordered rubric evaluation over a `criteria` array (`2..=255` rubric descriptions), returning the continuous expected value `score`, per-level `probabilities`, and a `legend` map.
* **Flat `~150–250 ms` Latency**: Because no autoregressive decode loop executes, evaluating `100` parallel questions over a single `memfd` frame completes in the same `~150–250 ms` wall-clock window as evaluating `1` question.

**`POST /v1beta/decisions` Request Wire Structure**:

```json
{
  "model": "<decision-model-id>",
  "input": [
    {
      "type": "image",
      "data": "<base64-encoded Koma memfd frame with grid_225 overlay>",
      "mime_type": "image/png"
    },
    {
      "type": "text",
      "text": "Goal: Click the Export button and verify dialog readiness."
    }
  ],
  "questions": {
    "q_in_scope": {
      "type": "noul",
      "instructions": "Is the Export button visible and enabled on screen?"
    },
    "q_grid_target": {
      "type": "choice",
      "instructions": "Which grid_225 cell contains the center of the Export button?",
      "criteria": {
        "L13": "Grid cell L13",
        "M13": "Grid cell M13",
        "NONE_OR_OTHER": "Target is not visible or outside the listed cells"
      }
    },
    "q_ui_readiness": {
      "type": "score",
      "instructions": "Rate how ready the Export dialog is for immediate confirmation.",
      "criteria": [
        "Dialog is occluded or still loading",
        "Dialog is visible but required fields are incomplete",
        "Dialog is fully populated and ready to export"
      ]
    }
  }
}
```

**`POST /v1beta/decisions` Response Wire Structure (`usage.total_output_tokens == 0`)**:

```json
{
  "answers": {
    "q_in_scope": {
      "type": "noul",
      "noul": 0.97,
      "confidence": 0.97
    },
    "q_grid_target": {
      "type": "choice",
      "choice": "L13",
      "confidence": 0.54,
      "probabilities": {
        "L13": 0.54,
        "M13": 0.41,
        "NONE_OR_OTHER": 0.05
      }
    },
    "q_ui_readiness": {
      "type": "score",
      "score": 2.74,
      "probabilities": {
        "1": 0.04,
        "2": 0.18,
        "3": 0.78
      },
      "legend": {
        "1": "Dialog is occluded or still loading",
        "2": "Dialog is visible but required fields are incomplete",
        "3": "Dialog is fully populated and ready to export"
      }
    }
  },
  "usage": {
    "total_input_tokens": 1471,
    "total_output_tokens": 0,
    "cached_tokens": 0
  }
}
```

#### Sub-Grid Probability-Weighted Centroid Interpolation (`interpolate_grid_225_centroid`)

When a wide UI control (such as an `"Export"` button) straddles the boundary between adjacent `grid_225` (`15x15`) cells, a dedicated decision model naturally splits its softmax probability mass across those neighboring cells (for example, `L13` with $p = 0.54$ and horizontally adjacent `M13` with $p = 0.41$). Although neither single cell exceeds the `0.85` fast-path threshold in isolation, their combined local mass is $0.54 + 0.41 = 0.95 \ge 0.85$.

Instead of discarding split-cell hits or snapping coarsely to `L13`'s center, `jikud` runs **`interpolate_grid_225_centroid`**:
1. Collects the top cell $c_0$ and any 8-connected neighboring `grid_225` cells $\mathcal{N}(c_0)$ whose individual probability $p_c \ge 0.05$.
2. Evaluates the local cluster probability sum $P_{\text{cluster}} = \sum_{c \in \mathcal{N}(c_0)} p_c$ against the fast-path confidence gate (`>= 0.85`).
3. Computes the continuous probability-weighted sub-grid centroid:
   $$(x_{\text{click}}, y_{\text{click}}) = \frac{\sum_{c \in \mathcal{N}(c_0)} p_c \cdot (x_c, y_c)}{\sum_{c \in \mathcal{N}(c_0)} p_c}$$
4. Feeds $(x_{\text{click}}, y_{\text{click}})$ directly into `Phodopus` **`MinimumJerk`** pointer trajectory generation, achieving sub-cell targeting accuracy on the exact boundary between `L13` and `M13`.

#### `DecisionCompiler`: Multi-Step Shortcut & Action Compilation Strategies

A single `choice` question's probability ranking **cannot** represent a chronological multi-step key or action sequence for three mathematical reasons:
1. **Softmax Mutual-Exclusion Dilution ($\sum P_i = 1.0$)**: If a 3-step shortcut sequence (`Ctrl+F -> Enter -> Escape`) is required, a single `choice` question forces the three required actions to compete for `1.0` total probability (~`0.33` each), falsely failing the confidence gate.
2. **Confidence $\neq$ Temporal Order**: Observing $P(\text{Enter}) = 0.55 > P(\text{Ctrl+F}) = 0.40$ means the model is slightly more certain about `Enter`, not that `Enter` should be pressed before `Ctrl+F`.
3. **Inability to Express Repeated Keys**: A set of unique `choice` option keys cannot represent sequences with duplicate operations such as `Down -> Down -> Enter`.

To compile multi-step keyboard and GUI micro-transactions inside a **single `POST /v1beta/decisions` request (`0` output tokens)**, `jikud`'s `DecisionCompiler` implements three explicit compilation strategies:

* **Strategy A (`TimeSlotMacro`) — Fixed-Horizon Ordered Sequence with Repeat Support**:
  Packs $K$ parallel `choice` questions (`slot_1`, `slot_2`, ..., `slot_K`) into one request. Every slot shares the candidate shortcut `criteria` map plus a `"STOP_DONE"` (`"NONE_OR_OTHER"`) termination sentinel. `DecisionCompiler` reads `slot_1..=slot_K` in index order and truncates the macro at the first slot where `choice == "STOP_DONE"` or slot confidence `< threshold`. Because each time slot is an independent `choice` distribution, `TimeSlotMacro` natively expresses repeated keys (e.g., `slot_1 = "Down"`, `slot_2 = "Down"`, `slot_3 = "Enter"`, `slot_4 = "STOP_DONE"`).
* **Strategy B (`BernoulliExpectedStep`) — Set-of-Actions Activation + Expected Step Ordering**:
  When selecting and ordering a subset from $M$ distinct candidate actions without repeats, `DecisionCompiler` emits two questions per candidate `<key>`:
  1. An independent binary `noul` activation gate `use_<key>` (*"Should `<key>` be executed in this transaction?"*), and
  2. A step-index `choice`/`score` distribution `order_<key>` over positions `1..=K`.
  `DecisionCompiler` retains all candidates with $P(\text{use\_key}) \ge 0.80$ and sorts them by ascending expected step index:
  $$E[\text{step}_{\text{key}}] = \sum_{k=1}^{K} k \cdot P(\text{Step}_k)$$
* **Strategy C (`ThresholdProbe`) — Order-Independent Heuristic Fallback Probing**:
  For exploratory fallback actions where strict chronological order does not matter (e.g., attempting to dismiss an unfamiliar modal popup via `Escape`, `q`, or `Space`), `DecisionCompiler` sorts candidates by descending probability, truncates all candidates below `threshold` (`0.15`), and compiles a guarded `Phodopus` probe loop that executes each surviving candidate sequentially with an intermediate `wait_settle` check that exits as soon as window topology changes.

#### Five Core Scenarios in `jikud`

1. **Single-Frame GUI System-1 Control**:
   In a single HTTP call over the active workspace's `memfd` frame (with `grid_225` overlay), `jikud` packs:
   * `q_in_scope` (`noul` Yes/No): Is the target UI element currently visible and interactive on screen?
   * `q_grid_target` (`choice` over `225` `grid_225` cells + `"not_visible"`): Which cell contains the interaction target?
   * `q_action_type` (`choice`): `click_left`, `click_right`, `double_click`, `scroll_down`, `scroll_up`, `run_macro`, `wait_settle`, or `NONE_OR_OTHER`.
   * `q_macro_pick` (`choice` over approved `~/.config/jiku/skills/*.lua` + `"NONE_OR_OTHER"`): Which deterministic Lua macro matches the current UI state?
   * `q_safety_gate` (`15` parallel `noul` Yes/No checklist rules): Screens simultaneously for visual prompt injection banners, 2FA/OTP input fields, payment/checkout confirmation buttons, destructive file deletion modals, and credential elevation prompts.
2. **Confidence-Gated Control Plane Router**:
   * **Safety Preemption**: If any of the 15 `q_safety_gate` `noul` rules fires above its risk threshold, `jikud` immediately halts autonomous execution, emits `security.verification_needed`, and yields to human **`Mod + G`** preemption or a critical D-Bus notification (`org.freedesktop.Notifications` -> `swaync`).
   * **System-1 Fast Path (`>= 0.85`)**: When `q_in_scope` is positive (`P(yes) >= 0.85`) and the top `q_action_type` / `q_grid_target` or `q_macro_pick` probability is **`>= 0.85`**, `jikud` dispatches the `Epoch`-fenced action directly to `koma-agent.sock`—completing the perception-to-action loop in `< 250 ms` without calling a generative model.
   * **System-2 Fallback (`< 0.85`)**: When confidence falls below `0.85`, `q_in_scope` is negative, or the step requires open-ended text entry, `jikud` escalates the frame and `DecisionsDriver` probability diagnostics to `TurnModelDriver` (`planner`).
3. **Live Stream / VTuber Real-Time Chat (`danmaku`) Filtering & Live2D/VRM 255-Expression/Motion Selection**:
   During live companion sessions, `DecisionsDriver` evaluates incoming chat message batches in parallel for prompt-injection/toxicity filtering and engagement priority while selecting from up to **`255` discrete Live2D/VRM facial expressions and motion clips**, publishing the selected cue directly to `jiku.sock` (`avatar.cue`).
4. **Native Multimodal `~/JikuBox/` Batch Classification, Tagging & Screening**:
   Powers `jiku box classify` over files dropped into `~/JikuBox/`—including resume screening against multi-criteria checklists, competition submission grading, multimodal image/audio/video tagging, and two-stage recommendation (stage-1 binary `noul` coarse filtering followed by stage-2 fine rubric scoring)—evaluating up to `1,000` structured questions per artifact in a single zero-decode pass.
5. **L2 SQLite FTS5 Trajectory & Skill Reranking**:
   Before `TurnModelDriver` planning, `jikud` queries `state.db` FTS5 for top-`K` candidate historical episodes and `skills/*.lua` descriptors, then packs all `K` candidates into a single `DecisionsDriver` request (`noul` relevance + `score` applicability) to rerank them with calibrated probabilities in `< 200 ms`.

#### Closed-Set Decision (`DecisionsDriver`) vs. Open-Ended Generative (`TurnModelDriver`) Boundary

| Dimension | `DecisionsDriver` (native decision model) | `TurnModelDriver` (`reqwest` + HTTP/2 SSE) |
| :--- | :--- | :--- |
| **Inference Mechanism** | Single-prefill zero-decode pass (`0` output tokens generated). | Autoregressive token-by-token decoding streamed over HTTP/2 SSE. |
| **Output Space** | Closed-set calibrated probability distributions: `noul` (`Yes/No`), `choice` (`2..=255` options), `score` (`2..=255` levels). | Open-ended text generation, multi-step reasoning plans, free-form keyboard strings, and Lua macro code. |
| **Parallelism & Latency** | `1..=1000` questions evaluated in parallel over shared media in flat `~150–250 ms`. | Sequential token generation (`~800 ms–5 s+`), scaling linearly with output token count. |
| **Primary `jikud` Workloads** | System-1 `grid_225` target selection, `>= 0.85` confidence router, 15-rule visual safety gate, Live2D 255-cue selection, `~/JikuBox/` batch triage, L2 FTS5 reranking. | System-2 `planner` recovery when confidence `< 0.85`, `Zero-IME` `type_text` payload generation, and candidate `staged_skills/*.lua` synthesis. |
| **Token & Cost Profile** | Input tokens only (`$0.10 / 1M` input tokens on Paid Tier, `$0` output tokens). | Input tokens + billed reasoning and output tokens across provider tiers. |

#### Four Mandatory Engineering Guardrails for `DecisionsDriver`

1. **Mandatory `"NONE_OR_OTHER"` / `"not_visible"` Fallback + Paired `Yes/No` (`q_in_scope`) Gate**:
   Because every `Choice` question softmax-normalizes its option probabilities to sum to **`1.0`**, omitting a fallback option forces out-of-distribution inputs into high-confidence false positives. Every `Choice` question in `jikud` **must** include an explicit `"NONE_OR_OTHER"` or `"not_visible"` option and be gated by a paired binary `Yes/No` (`noul`) question (`q_in_scope`).
2. **Literal Native Decision Model ID & Request-Level Question Batching**:
   Callers must pass the provider's exact native decision model identifier (versioned aliases such as `-latest` are rejected). The `/v1beta/decisions` endpoint supports neither Context Caching nor the asynchronous Batch API; instead, `jikud` amortizes input token cost by packing up to **`1,000` questions** into a single request's `questions` map over the shared multimodal payload.
3. **Decompose Coarse `Score` Rubrics into `5..=10` Binary `Yes/No` (`noul`) Checklists**:
   Whenever a grading or safety rubric can be expressed as verifiable criteria, `jikud` decomposes coarse `Score` questions into **`5..=10` orthogonal binary `Yes/No` (`noul`) checklist questions** and computes the weighted score in Rust/Lua, yielding substantially tighter calibration and per-criterion auditability in `audit.jsonl`.
4. **Media Transport Constraints & AI Studio Free vs. Paid Tier Privacy Boundary**:
   * **Media Encoding**: Multimodal inputs must be supplied either as inline bytes (`image/webp` or `image/png` encoded in-memory directly from `Koma`'s read-only `SCM_RIGHTS` `memfd`) or via the Google Files API. `gs://` Cloud Storage URIs and YouTube URLs are rejected by `/v1beta/decisions`, and per-question `instructions` accept **plain text only**.
   * **Quota & Data-Logging Boundary**: AI Studio **Free Tier** provides `~200 RPM` / `10,000 RPD` / `50,000 TPM` (where Google logs submitted prompts and media for model improvement), whereas **Paid Tier** bills `$0.10 / 1M` input tokens (`$0` output) with zero training retention. Regardless of tier, `Koma`'s Ring 0 **`#000000` Protected Surface Blackout** (`block_out_from = "agent_capture" | "all"`) zeroes out password managers, Polkit prompts, and secret windows in the compositor's offscreen FBO before `memfd` export—ensuring sensitive pixels never reach `jikud` or Google AI Studio even on the Free Tier.

---

### 5.2 `TurnModelDriver` (`reqwest` + HTTP/2 SSE)

When a task requires open-ended generation—or when `DecisionsDriver` routes a step to System-2 (`confidence < 0.85`)—`jikud` invokes `TurnModelDriver` over multiplexed HTTP/2 Server-Sent Events (`reqwest`):

* **Core Responsibilities**:
  1. **Multi-Step `planner` & Error Recovery**: Decomposes complex cross-application goals, inspects L1 `app_id` quirks and `DecisionsDriver`-reranked L2 FTS5 episodes, and recovers from unexpected UI modal states.
  2. **Open-Ended Text Entry (`Zero-IME` `type_text`)**: Generates arbitrary natural-language replies, search queries, file names, and form payloads injected directly via `Koma`'s `zwp_text_input_v3` / `VirtualSeat` pipeline.
  3. **Candidate `staged_skills/*.lua` Synthesis**: Synthesizes parameterized `Phodopus` Lua macros from verified multi-step trajectories, strips unsafe tokens, and writes them to `~/.local/state/jiku/staged_skills/` for human `jiku skills approve` promotion.
* **Heterogeneous Provider Support**: Connects to **OpenAI-compatible gateways** (`kind = "openai_compatible"` or `"opencode_go"`, optional `"thinking": {"type": "disabled"}` toggle, deterministic session UUID headers, and the model ID you configure), **Google AI Studio**, **Vertex AI** (via Application Default Credentials / ADC), **Anthropic** (`Messages` API with prefix prompt caching), and **OpenAI-compatible** self-hosted endpoints (`vLLM`, `llama.cpp`, `Ollama`), mapping heterogeneous visual grounding outputs (`0..1000` bounding boxes, normalized points, or `9-anchor` window offsets) through a unified **`ActionNormalizer`**.

---

### 5.3 `LiveSessionDriver` (`tokio-tungstenite` Stateful Full-Duplex WebSocket for `jiku live`)

#### Why Real-Time Companion / AI VTuber / Gaming Mode Requires Stateful Full-Duplex WebSocket

Real-time multimodal companion workflows (`jiku live`—spanning interactive desktop pair-piloting, Neuro-sama-style AI VTuber streaming, and live gaming co-pilots) cannot be built on half-duplex HTTP+SSE (`TurnModelDriver`):

1. **Continuous Server-Side KV-Cache State**: Half-duplex HTTP must re-transmit conversation and visual history on every turn; a **Stateful Full-Duplex WebSocket** maintains a persistent server-side KV cache across continuous audio/video streams.
2. **True Bidirectional Multiplexing**: The user speaks into PipeWire (`16 kHz` PCM) while `Koma` pushes `1–2 FPS` screen damage frames and live stream chat (`danmaku`) arrives—all while the model is simultaneously streaming back `24 kHz` voice audio, lip-sync cues, and asynchronous GUI tool calls over the same socket.
3. **Sub-100 ms Native Barge-In (Server VAD)**: When the user interrupts mid-sentence, server-side Voice Activity Detection (VAD) emits an immediate `interrupted: true` control frame over the WebSocket so local audio playback and outdated GUI actions halt immediately.

`LiveSessionDriver` abstracts this stateful full-duplex pipeline across **Gemini Multimodal Live API** (`BidiGenerateContent`), **OpenAI Realtime API**, **Qwen-Omni Realtime**, and **local WebRTC/WebSocket speech-to-speech pipelines**.

#### Three Concurrent Tokio Tasks Inside `LiveSessionDriver`

```
  PipeWire Mic (16kHz PCM) --+
  Koma memfd (1-2 FPS / 0 FPS)+--> [1. Uplink Task] ========(WSS realtimeInput)========>
  Live Chat / Danmaku Queue -+     (Context Compression + SessionResumption / GoAway)
                                                                                       |
  PipeWire Sink (24kHz PCM) <----- [2. Downlink Task] <=====(WSS serverContent)========+
  jiku.sock (`avatar.cue`)  <----- (RMS/Freq Lip-Sync + Barge-In Buffer Flush)         |
                                                                                       |
  koma-agent.sock <--------------- [3. Action Bridge Task] <=(WSS toolCall)============+
  (Local Epoch Fence)              (NON_BLOCKING Dispatch + INTERRUPT/WHEN_IDLE/SILENT)
```

1. **`Uplink` Task (Audio + Perceptual-Hash-Gated Vision + Session Lifecycle)**:
   * **Audio Stream**: Captures `16 kHz`, `16-bit mono PCM` audio chunks (`20–100 ms` cadence) from PipeWire and streams them as `realtimeInput` media chunks.
   * **Damage-Driven `1–2 FPS` Screen Stream (`0 FPS` When Static)**: Subscribes to `Koma`'s `window.damage_settled` EventRing and compares `memfd` perceptual block hashes (`Hamming distance >= threshold`). Frames are encoded and transmitted at **`1–2 FPS` only when visible screen damage occurs**, automatically dropping to **`0 FPS` when the screen is static**—saving **~80% of visual token consumption** during voice-heavy sessions.
   * **Optional Live Chat Queue**: Multiplexes filtered viewer `danmaku` / chat turns (pre-screened by `DecisionsDriver`) into the session stream.
   * **Unbounded Session Longevity**: Configures `contextWindowCompression` (`triggerTokens` threshold + `slidingWindow` compaction) so multi-hour sessions never overflow context limits, paired with `sessionResumption` (`SessionResumptionUpdate` token persistence + `GoAway` pre-emptive zero-downtime reconnection across the cloud provider's 10-minute WebSocket connection ceiling).
2. **`Downlink` Task (Direct PipeWire Audio + Real-Time Lip-Sync + Instant Barge-In Flush)**:
   * **Native `24 kHz PCM` Audio Playout**: Streams incoming `24 kHz PCM` audio chunks directly to a dedicated PipeWire virtual sink—bypassing external HTTP TTS latency when running in native speech-to-speech mode.
   * **Real-Time RMS/Frequency Lip-Sync & Gaze Envelopes**: Computes per-frame RMS amplitude and frequency-band vowel formants from the `24 kHz` PCM stream alongside virtual pointer `(u, v)` coordinates, broadcasting low-latency `avatar.cue` packets over `jiku.sock`.
   * **Barge-In & `Proactive Audio` Gating**: On receiving server VAD `serverContent: { interrupted: true }`, `Downlink` **immediately flushes the PipeWire playback ring buffer** and emits a zeroed lip-sync reset frame on `jiku.sock` so the avatar stops speaking within milliseconds. Supports **`Proactive Audio`** mode where the companion listens continuously without responding until directly addressed or triggered by a salient screen event.
3. **`Action Bridge` Task (`NON_BLOCKING` Tool Dispatch + Local `Epoch` Fence)**:
   * **Asynchronous `NON_BLOCKING` Execution**: Subscribes to model `toolCall` requests (`click`, `move_to`, `run_koma_macro`, etc.) declared with `NON_BLOCKING` behavior so the companion can continue speaking and observing while `Koma` executes GUI actions in `agent:work`.
   * **Hardware-Grade Local `Epoch` Fence Against Cloud Cancellation Lag**: Cloud `toolCallCancellation` frames over WAN WebSockets can lag tens or hundreds of milliseconds behind a user's voice barge-in or physical **`Mod + G`** takeover. Every action dispatched by `Action Bridge` carries the local **`Epoch` fence**: if either `Downlink` detects `interrupted: true` or `Koma` increments `Epoch` on `Mod + G`, in-flight actions are rejected synchronously at the `koma-agent.sock` boundary before they can touch the workspace.
   * **Scheduled `toolResponse` Delivery**: Returns execution outcomes back over the WebSocket tagged with explicit continuation scheduling (`INTERRUPT` for critical errors/safety blocks, `WHEN_IDLE` for normal action completion, or `SILENT` for background telemetry updates).

---

## 6. Detachable TUI, Notifications, TTS & Live2D / VRM Companion Bus

When used directly as a standalone desktop assistant (without an external MCP host), `jikud` exposes a local control & event bus at **`$XDG_RUNTIME_DIR/jiku.sock`** (`0600`):

### 6.1 Detachable `jiku` TUI / CLI & Asynchronous User Notifications

* **Stateless Frontend (`jiku`)**: Closing the `jiku` TUI (`ratatui`) or terminal window **never** stops `jikud`; background tasks and `jiku live` companion sessions continue inside `agent:work`, and running `jiku` (or `jiku attach`) reconnects to `jiku.sock` to stream live steps, approve staged skills, or pause/abort tasks.
* **Proactive User Notifications**: On task completion, error, or human-verification gates (`security.verification_needed` triggered by `DecisionsDriver`'s `q_safety_gate`, e.g., 2FA / login / payment prompts), `jikud` dispatches desktop notifications via **D-Bus `org.freedesktop.Notifications`** (integrating natively with `swaync` action buttons such as *"Peek Workspace"* or *"Approve"*), plus optional webhook plugins for remote alerts.

### 6.2 Progressive Modular Roadmap: Optional TTS (`jiku-tts`), Live Voice (`jiku live`) & Avatar Subscriber Bus

> **Progressive Modular Status (`v0.0.1`)**: Core desktop orchestration (`[roles.planner]` + `DecisionBackend`, situational AT-SPI2 `@snap:eN` + `SystemGroundingPack`, 4-stage `context_budget` compaction waterfall, `2x2` `VirtualPaint` ablation harness, and 12-tool dual-framing `jiku mcp`) works with zero audio or GUI overlay dependencies. In `v0.0.1`, modular `jiku-tts` (`espeak_ng`, `irodori`, `voicevox`, `openai_speech`, `noop` with 20 ms lip-sync cue extraction and barge-in `AudioPlaybackSink`) and the HTTP/WebSocket `jiku avatar serve` VRM stage are available when enabled, whereas native Wayland layer-shell companion renderers (`MMD`, `Inochi2D`) and live full-duplex PipeWire hardware microphone capture remain deferred to `v0.1.0`.

When explicitly enabled in `config.toml`, voice synthesis and 2D/3D avatars attach as **decoupled `jiku.sock` EventBus subscribers** so `jikud` stays lean and headless-safe:

* **i18n & Pluggable `TtsProvider` (`jiku-tts` in Turn Mode) vs. Native PCM (`LiveSessionDriver`)**: Explicit locale configuration (`zh-CN`, `ja-JP`, `en-US`) paired with a `TtsProvider` trait supporting **VOICEVOX Engine** (`/audio_query` + `/synthesis` for natural Japanese voicebanks), local **Piper / CosyVoice**, or OpenAI-compatible `/v1/audio/speech` streamed to **PipeWire** during turn-based workflows, while `LiveSessionDriver` streams native `24 kHz PCM` directly to PipeWire.
* **Avatar Companion Protocol (`avatar.cue`: `VRM`, `MMD`, `Live2D Cubism`, `Inochi2D`)**: `jikud` broadcasts structured `AvatarCue` events over `jiku.sock` containing:
  1. **Semantic Emotion, Activity State & 255-Cue Selection** (`Idle`, `Thinking`, `Acting`, `WaitingHuman`, `Success`, `Alert`, plus discrete `expression_id` / `motion_id` selected by `DecisionsDriver`),
  2. **Normalized Gaze Target** `(u, v)` tracking `Jiku`'s active virtual pointer or highlighted window region, and
  3. **Dual Lip-Sync Envelopes**: Either deterministic **Phoneme / Mora Timing Envelopes** (extracted from VOICEVOX `AudioQuery`) or real-time **RMS / Frequency-Band Envelopes** (computed by `LiveSessionDriver`'s `Downlink` task from `24 kHz PCM` audio, with instant reset on `interrupted: true`).
  A separate `wlr-layer-shell` overlay client (rendering `VRM`, `MMD`, `Live2D Cubism`, or `Inochi2D` models) can subscribe to `jiku.sock` at any time without adding a single OpenGL dependency to `jikud` or `Koma`.
