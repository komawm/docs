# Koma (`komawm`) System Architecture Specification

> **Status**: Architecture Baseline v0.1 (Draft Accepted)
> **Repository & Namespace**: `github.com/komawm/koma` (Compositor binary: `koma`, CLI controller: `komactl`, User configuration entry: `~/.config/koma/init.lua`)
> **Target Platforms**: Linux and FreeBSD / OpenBSD (Wayland-native; legacy X11 clients supported strictly via isolated compatibility bridges)

## 1. Vision and Unix Design Philosophy

`Koma` (from Japanese *コマ / 齣*, simultaneously denoting **tiled comic panels, rendered video frames, and game pieces**) is a Wayland tiling compositor purpose-built as **first-class infrastructure for concurrent AI Agent Computer Use** while serving as an uncompromising, keyboard-driven daily driver for developers.

On mobile platforms, Android's built-in [`adb`](https://developer.android.com/tools/adb) (`screencap`, `screenrecord`, and `input`) enabled a rich ecosystem of GUI automation agents by offering clean OS-level primitives. On Linux and BSD desktops, Wayland's client isolation rightly eliminated X11's global snooping flaws, but left external automation tools such as [`open-computer-use`](https://github.com/iFurySt/open-computer-use) struggling against missing background input channels, focus stealing, and broken root-window screenshots. `Koma` resolves this tension at the compositor foundation while strictly upholding three Unix principles:

1. **A Pure Window Manager, Never a Monolithic Desktop Environment**: `Koma` restricts its kernel scope to buffer composition, deterministic window geometry, multi-seat input routing, and zero-copy frame export. It intentionally excludes built-in status bars, wallpaper daemons, notification centers, WebViews, OCR engines, and LLM inference runtimes. Higher-level tools attach orthogonally over Unix domain sockets and standard Wayland protocols.

2. **Strict Separation of Mechanism and Policy**: Hardware synchronization, GPU memory safety, concurrency locks, and capability isolation live in a memory-safe Rust microkernel. Tiling algorithms, keybinding state machines, window routing rules, and timed automation macros live in an embedded, deterministically budgeted pure-Rust stackless Lua 5.4 runtime (`Phodopus`).

3. **Portable Linux and BSD Foundation**: Event dispatch runs on [`calloop`](https://github.com/Smithay/calloop) (natively backing onto `epoll` on Linux and `kqueue` on FreeBSD/OpenBSD), paired with [`libseat` / `seatd`](https://www.reddit.com/r/linuxquestions/comments/1ez8igt/whats_the_difference_between_seatd_and_logind/) for `systemd`-free DRM and input device management across Linux and [OpenBSD Wayland desktop environments](https://www.linux.se/tag/wayland/). `Koma` contains zero native X11 window-management code; legacy X11 applications run via on-demand, per-workspace [`xwayland-satellite`](https://github.com/Supreeeme/xwayland-satellite) instances.

## 2. Three-Ring Microkernel and Cargo Workspace Architecture

Modern tiling compositors face a sharp extensibility trade-off. In-process C++ `.so` plugin loaders used by [`Hyprland`](https://github.com/hyprwm/hyprland) and [`Wayfire`](https://github.com/WayfireWM) deliver raw speed, but suffer from frequent ABI breakage and risk `SIGSEGV` crashes that terminate the entire user session. Traditional C-FFI scripting VMs embedded in [`AwesomeWM`](https://github.com/awesomeWM/awesome), [`Qtile`](https://github.com/qtile/qtile), or early [`Pinnacle`](https://github.com/pinnacle-comp/pinnacle) via [`mlua`](https://github.com/mlua-rs/mlua) freeze the compositor's `240 Hz` render loop if a script enters an infinite loop or performs blocking I/O. Conversely, pure out-of-process window management via [`river-window-management-v1`](https://wayland.app/protocols/river-window-management-v1) in [`River 0.4`](https://github.com/riverwm/river) (detailed in [Separating the Wayland Compositor and Window Manager](https://isaacfreund.com/blog/river-window-management/)) isolates crashes cleanly, but cannot directly orchestrate offscreen GPU framebuffers or virtual `wl_seat` multiplexing from outside the compositor.

`Koma` synthesizes these paradigms into a **Three-Ring Architecture**:

| Architectural Ring | Owning Crates | Responsibilities and Capability Scope | Fault and Resource Isolation | 
| ----- | ----- | ----- | ----- | 
| **Ring 0: Rust Mechanism Microkernel** | `koma-model`, `koma-render`, `koma-seat`, `koma` | Built on [`Smithay`](https://github.com/smithay/smithay): physical DRM/KMS scanout, lazy offscreen FBO pools, `vSeat` focus and clipboard multiplexing, surface damage tracking, and double-buffered geometry barriers | Safe-Rust single-writer state machine; unbounded external callbacks are structurally prohibited on the VSync path | 
| **Ring 1: In-Process `Phodopus` Policy Sandbox** | `koma-lua` (consuming `phodopus`) | Evaluates `~/.config/koma/init.lua` (aligned with Neovim and [`hyprland.lua`](https://github.com/hyprwm/Hyprland/blob/main/example/hyprland.lua) ergonomics), executes pure-function layout generators, and runs timed GUI macros and batch agent transactions | Stackless `gc-arena` Lua VM derived from [`Piccolo`](https://github.com/kyren/piccolo) with deterministic `Fuel` instruction metering and hard heap quotas; runaway scripts interrupt cleanly and fall back to built-in layouts | 
| **Ring 2: Out-of-Process Ecosystem Daemons** | `koma-proto`, `komactl`, `koma mcp` (subcommand), `koma-overview` | Dual-socket IPC inspired by [`bspwm`](https://github.com/baskerville/bspwm) serving the stateless CLI, MCP server, `AT-SPI2` accessibility crawlers, hardware video recorders, and workspace thumbnail viewers | Separate OS processes; daemon crashes or restarts have zero impact on the compositor or running client windows |

### 2.1 Cargo Workspace Crate Topology

To keep incremental Rust builds fast and quarantine heavy Wayland/GPU C-library bindings away from core state-machine tests and lightweight CLI binaries, the Cargo workspace is partitioned into four dependency tiers across nine crates:

| Tier | Crate | Kind | Dependencies & Role | 
| ----- | ----- | ----- | ----- | 
| **Tier 0: Pure Contracts & State** | `koma-proto` | `lib` | Zero Wayland/GPU dependencies (`serde` only). Defines dual-socket IPC wire schemas, `CapabilityToken` scopes, `Epoch` fencing errors, kinematic curve descriptors, and event payloads. | 
| **Tier 0: Pure Contracts & State** | `koma-model` | `lib` | Zero `Smithay` dependencies. Implements deterministic `Workspace` state, `Deck / Stash` stacks, `WorkspaceLease + Epoch` state machines, the 4-tier frame clock, double-buffered layout staging, and kinematic curve math. Unit-testable in milliseconds without a display server. | 
| **Tier 1: Sandboxed Scripting** | `koma-lua` | `lib` | Depends only on `phodopus`, `koma-model`, and `koma-proto`. Implements the `koma.*` Host ABI, `HostOpHandle` suspension descriptors, macro recording denoiser/compiler, and `LuaLS` type-stub generation. | 
| **Tier 2: Compositor Subsystems** | `koma-render` | `lib` | `Smithay` EGL/GBM (`GlesRenderer`) and Vulkan backends, primary-iGPU DRM binding, `LazyFbo` pool (`Render-on-Read`), GPU-composited SoM and `warpd` grid overlays, sensitive-window blackout masks, and `DMA-BUF` export. | 
| **Tier 2: Compositor Subsystems** | `koma-seat` | `lib` | Physical `libinput` `seat0` pass-through, per-workspace `vSeat` multiplexing, 3-tier Zero-IME text/MIME injection, and `xdg-foreign-v2` / `xdg-activation-v1` / `security-context-v1` protocol enforcement. | 
| **Tier 2: Compositor Subsystems** | `koma` | `bin` | Main compositor executable wiring `calloop`, `libseat` DRM/KMS and Winit nested backends, `koma-lua` host adapter, Unix IPC sockets, and on-demand `xwayland-satellite` supervision. | 
| **Tier 3: Ring 2 Userland Tools** | `komactl` | `bin` | Sub-millisecond stateless CLI controller (`adb`-style workspace, input, capture, macro recording/playback, and `gen-types` commands). Links only `koma-proto` and `koma-lua`. | 
| **Tier 3: Ring 2 Userland Tools** | `koma mcp` | `koma` subcommand | Standard `stdio` MCP server exposing scoped Computer Use tools and an embedded `Phodopus` Lua batch-transaction REPL for external LLM agents. |
| **Tier 3: Ring 2 Userland Tools** | `koma-overview` | `bin` | Standalone Wayland client (`wgpu` + `wlr-layer-shell`) providing both status-bar hover thumbnail popups and a full-screen multi-agent live overview deck. | 

### 2.2 `koma-lua` Host ABI and Stackless `calloop` Trampoline

`Phodopus` declares zero dependency on Tokio, boots in `~35 µs` with an `~11 KB` baseline heap, and crosses host async boundaries via typed suspension handles:

* **In-Frame Pure Layout Transactions (`koma.layout` / `koma.rule`)**: When workspace windows change, `koma-model` opens a transaction modeled after [`river-window-management-v1`](https://wayland.app/protocols/river-window-management-v1), passing an immutable window-tree snapshot to Lua with a strict per-frame budget (`50,000 Fuel`, `2 MiB` heap ceiling). Once Lua returns target `(x, y, w, h)` rectangles, `koma` dispatches all `xdg_toplevel.configure` events atomically to prevent resize flicker.

* **Cross-Frame Coroutine Suspension (`HostOpHandle`)**: When a macro or agent script invokes `vseat:wait_settle()` or `koma.sleep_ms(80)`, `koma-lua` yields `SequencePoll::Suspend(HostOpHandle)`, parking the coroutine inside its `gc-arena` heap without holding native Rust stack frames. `calloop` continues driving physical `240 Hz` output frames unimpeded and calls `executor.resume_host_op()` once the timer or surface damage-settle condition resolves.

* **Static Type Stubs and Indexing Convention**: Running `komactl gen-types` emits [`LuaLS`](https://github.com/LuaLS/lua-language-server) (`LuaCATS` `---@class`) definition files directly from Rust binding metadata (mirroring [`wezterm-types`](https://github.com/DrKJeff16/wezterm-types) for Neovim and VS Code autocomplete). Across the ABI, **collection tables use idiomatic Lua `1-based` iteration, while pixel coordinates, grid indices, monitor IDs, and timestamps strictly remain `0-based`**.

```
// crates/koma-lua/src/adapter.rs — Host-side calloop suspension contract
pub enum PendingHostOp {
    SleepTimer { deadline: Instant },
    WaitDamageSettle { ws_id: WorkspaceId, quiet_for: Duration, timeout_at: Instant },
    PointerTrajectory { ws_id: WorkspaceId, trajectory_id: TrajectoryId },
}

pub struct KomaLuaSandbox {
    runtime: PhodopusRuntime, // Isolated gc-arena with hard memory_limit quota
    pending_ops: Slab<(HostOpHandle, PendingHostOp)>,
}

```

## 3. Dual-Mode Workspaces, Window Stacks, and Adaptive Frame Clock

### 3.1 Decoupling Logical Workspaces from Physical Outputs

Existing headless monitor commands in compositors often suffer from unconfigured refresh-rate stalls or assertion crashes (see [Hyprland headless performance discussion #11617](https://github.com/hyprwm/Hyprland/discussions/11617) and [headless creation crash analysis #14929](https://github.com/hyprwm/Hyprland/discussions/14929)). In `Koma`, every `Workspace` is a symmetrical first-class container owning a stable `LogicalViewport` (e.g., `1920x1080@1.0` or matched to the primary display) and a dedicated `vSeat`. Its backing output is a hot-swappable enum:

* **`PresentationTarget::Physical(OutputId)` (`Headed`)**: Attached directly to a hardware DRM/KMS connector with VSync and direct scanout.

* **`PresentationTarget::Offscreen(LazyFboHandle)` (`Headless`)**: Detached from physical monitors. Toggling between `Headless` and `Headed` swaps only the presentation target pointer without resizing windows or reflowing web layouts.

### 3.2 Dual Window Organization: Scrolling Tiling vs. Agent `Deck / Stash`

Multi-pane splits suit human side-by-side comparison, but degrade VLM OCR legibility and invite cross-window mis-clicks for AI agents. `Koma` supports full geometry primitives (`resize`, `fullscreen`, `float`) alongside two tailored defaults:

1. **Human Workspace Default — Scrollable Strip & Dynamic Tiling**: Combines [`Niri`](https://github.com/YaLTeR/niri/wiki/index)-style infinite horizontal columns (preserving fixed viewport widths without squishing existing windows) with [`Sway`](https://github.com/swaywm/sway)-style binary splits.

2. **Agent Workspace Default — `Deck` Monocle Stack + `Window Stash`**: Building on [`i3` tabbed/stacked containers](https://github.com/i3/i3/blob/next/docs/userguide), the active window occupies `100%` of the canonical viewport while sibling windows reside in the workspace's background `Stash` stack, swappable in sub-milliseconds via `win.activate(win_id)`.

3. **Protocol-Level Per-Window Capture**: Even inside multi-window tiled workspaces, `Koma` implements [`ext-image-capture-source-v1`](https://wayland.app/protocols/ext-image-capture-source-v1) (aligned with [Smithay capture-source architecture #1900](https://github.com/Smithay/smithay/issues/1900)) and generation-tagged [`ext-foreign-toplevel-list-v1`](https://wayland.app/protocols/ext-foreign-toplevel-list-v1) handles to render isolated, background-free snapshots of a single toplevel surface plus its transient `xdg_popup` menus.

### 3.3 GPU Pipeline Division and Four-Tier Adaptive Frame Clock

Following [Smithay's architectural guidance on `wgpu` #431](https://github.com/Smithay/smithay/discussions/431), **`koma-render` uses Smithay's native EGL/GBM (`GlesRenderer`) and Vulkan pipelines** for zero-copy multi-planar `DMA-BUF` modifier import and explicit buffer reclamation (incorporating [Niri's NVIDIA VRAM lifecycle practices](https://github.com/YaLTeR/niri/wiki/Nvidia)), while the standalone **`koma-overview` client uses `wgpu` + `wlr-layer-shell`**.

To achieve **`0%` idle compositor GPU overhead** without starving client `requestAnimationFrame` loops in Chromium, Firefox, or GTK4, `Koma` decouples lightweight `wl_surface.frame` protocol ticks from heavy GPU framebuffer composition:

| Workspace Tier | Trigger Condition | Client `frame` Callback Rate | Compositor GPU Composition Rate | VRAM and Compute Footprint | 
| ----- | ----- | ----- | ----- | ----- | 
| **1. `Headed`** | Bound to a physical display | Locked to hardware VSync | `60–240 Hz` live scanout | Standard primary desktop cost | 
| **2. `Headless Burst`** | `1.0 s` window following `vSeat` input or surface damage | `60 Hz` (drives client async UI transitions to completion) | **`0 Hz`** (`Render-on-Read`: composites `1` frame only when `capture` is called) | `0` idle GPU shaders; borrows a pooled FBO only during snapshot readout | 
| **3. `Preview`** | Status-bar hover or active `koma-overview` | `5–10 Hz` | `5–10 Hz` hardware-downsampled to `384x216` | `~330 KB` thumbnail buffer per workspace, exported zero-copy via [`ext-image-copy-capture-v1`](https://wayland.app/protocols/ext-image-copy-capture-v1) | 
| **4. `Idle` -> `Frozen`** | Drops to `1 Hz` when settled; `0 Hz` after `10 s` without lease activity | `1 Hz` heartbeat -> `0 Hz` halted | **`0 Hz`** (all offscreen FBOs released) | **Both compositor and client GPU compute drop to `0%`** | 

Because Waybar's GTK3 tooltips cannot dynamically refresh distinct per-button images without stylesheet reload flicker (see [Waybar image tooltip limitation #1999](https://github.com/Alexays/Waybar/issues/1999)), `koma-overview --daemon` runs as a companion process: hovering a workspace button for `150 ms` spawns a borderless `wlr-layer-shell` live thumbnail card directly beneath the bar (compatible with stock Waybar and [`Ironbar`](https://github.com/jakestanger/ironbar/blob/master/docs/modules/Launcher.md)), while `Mod + Tab` expands the full-screen multi-agent overview grid (akin to [`Quickshell` workspace previews](https://github.com/Shanu-Kumawat/quickshell-overview)).

## 4. Concurrency Control: `Lease + Epoch` Preemptive Locks

### 4.1 Preventing Torn Input and Stale-Observation Mis-Clicks

Unprotected human entry into an active agent workspace causes two severe race conditions:

1. **Torn Input State**: Interleaving physical mouse/key events mid-macro while a virtual `Shift` or mouse drag is held corrupts selections or leaves stuck virtual modifiers.

2. **TOCTOU Stale Clicks**: If an agent captures a frame at `t = 0 ms`, a human scrolls the page at `t = 80 ms`, and the model's click arrives at `t = 150 ms`, the click hits the wrong UI control.

### 4.2 Three-State `WorkspaceLease` and Monotonic `epoch: u64` Fencing

Every workspace maintains a single-writer/multi-reader `WorkspaceLease` paired with a monotonically increasing `epoch: u64`:

* **`AgentExclusive { holder: AgentId, epoch: u64 }` (Background Write Lock & `Peek Read-Only` Shield)**: At most one agent holds write access to a workspace at a time. When the human switches to view an active agent workspace, it opens in **`Peek Read-Only` mode**—displaying a subtle border indicator while shielding the workspace from accidental `seat0` physical pointer/key jitter so running macros proceed undisturbed.

* **`HumanPreempted { prev_holder: Option<AgentId>, epoch: u64 }` (`Mod + G` Atomic Takeover)**: Pressing the explicit takeover chord (`Mod + G`) executes a `1 ms` atomic handoff:

  1. Synthesizes release events in reverse order for all currently pressed virtual keys and buttons on that workspace's `vSeat`;

  2. Cancels any suspended `Phodopus` macro coroutine via `cancel_host_op`;

  3. Increments `epoch` by `1`—immediately fencing and rejecting any in-flight IPC write requests carrying stale epochs with `Err(StaleEpoch { current })`;

  4. Transfers focus to `seat0` and emits `WorkspacePreempted`. Releasing takeover (`Mod + G`) increments `epoch` again (`N + 2`), forcing the agent to re-observe fresh state before resuming.

### 4.3 Multi-Workspace Spatial Context Primitives for Agents

An agent session can orchestrate multiple authorized workspaces without losing track of context or thrashing focus:

* **`scene.inventory()`**: Lock-free, low-token JSON tree listing authorized workspaces, lease states, current `epoch` numbers, active top-of-deck windows, and background `Stash` windows.

* **`win.activate(ws_id, win_id, expected_epoch)`**: Promotes a background `Stash` window to the top of the workspace's `Deck`.

* **`capture.frame(ws_id, win_id?)` (Stateless Cross-Workspace Peek)**: Reads a snapshot from another authorized workspace (e.g., a read-only reference PDF workspace) without disturbing focus in the agent's active workspace.

* **`vseat.bridge_clipboard(src_ws, dst_ws, mime_filter?)`**: Explicitly transfers clipboard payloads across otherwise isolated `vSeat` instances.

## 5. Virtual Seats (`vSeat`), Kinematic Pointers, and Zero-IME Text Injection

### 5.1 Per-Workspace `vSeat` Protocol Stack

Standard Wayland desktops expose a single [`wl_seat`](https://wayland.app/protocols/wayland), causing external injection protocols ([`wlr-virtual-pointer-unstable-v1`](https://wayland.app/protocols/wlr-virtual-pointer-unstable-v1) and [`virtual-keyboard-unstable-v1`](https://wayland.app/protocols/virtual-keyboard-unstable-v1)) to contend over focus and clipboards. Extending the concept behind [`ext-transient-seat-v1`](https://wayland.app/protocols/ext-transient-seat-v1), `koma-seat` instantiates a dedicated `vSeat` per headless workspace exposing four device classes:

1. **Absolute Pointer and Keyboard (`wl_pointer` / `wl_keyboard`)** for standard desktop apps and browsers.

2. **Relative Pointer and Constraints (`zwp_relative_pointer_v1` / `pointer-constraints`)** for 3D viewport orbiting in Blender and first/third-person games such as *Minecraft*.

3. **Virtual Graphics Tablet ([`tablet-v2`](https://wayland.app/protocols/tablet-v2))** for sub-pixel absolute positioning in rhythm games (*osu!lazer*) and digital painting, while keeping physical tablet drivers cleanly passed through on `seat0`.

4. **Isolated Data Device (`wl_data_device`)** providing a private clipboard per workspace.

### 5.2 Compositor-Native Kinematic Pointer Engine

`koma-seat` separates **spatial path geometry** $P(s)$ from **temporal velocity profiles** $s(t)$, emitting `120 Hz / 240 Hz` monotonic `wl_pointer.motion` + `wl_pointer.frame` streams directly from `calloop`:

* **`instant`**: Zero-latency teleportation for high-throughput local GUI batching.

* **`minimum_jerk`**: Single-arc cubic Bézier path paired with the neuro-motor fifth-order polynomial $s(\tau) = 10\tau^3 - 15\tau^4 + 6\tau^5$ (smooth bell-shaped velocity with zero boundary velocity/acceleration) and Fitts's Law duration scaling.

* **`spring`**: Second-order `VelocityVerlet` spring-damper solver modeling natural micro-overshoot and settle dynamics for hover menus and canvas drags.

* **`lua_custom`**: User- or agent-supplied `Phodopus` trajectory closures `fn(t) -> (x, y)` with physiological micro-tremor synthesis.

### 5.3 Three-Tier Zero-IME Direct Text and Rich-MIME Injection

To inject multilingual CJK prose, code, or structured tables into editors (such as WPS Office, LibreOffice, browsers, or IDEs) in milliseconds without routing through external input method daemons like `fcitx5`, `vseat.inject_text` and `vseat.paste_mime` cascade across three tiers:

| Priority | Injection Channel | Protocol Mechanism | Target Compatibility and Advantage | 
| ----- | ----- | ----- | ----- | 
| **Tier 1** | **`text-input-v3` Direct Server Commit** | Because the compositor itself is the [`text-input-unstable-v3`](https://wayland.app/protocols/text-input-unstable-v3) server (requiring no external [`input-method-unstable-v2`](https://wayland.app/protocols/input-method-unstable-v2) daemon), `koma-seat` sends `commit_string(utf8)` + `done()` directly to the focused surface | Firefox, Chromium, Ghostty, GTK4, Qt6, Wayland-native Blender; commits full paragraphs in `~1 ms` with zero candidate-popup flicker | 
| **Tier 2** | **Isolated `vSeat` Clipboard Atomic Paste** | Stages the payload in the workspace's private `vSeat` clipboard (and matching `xwayland-satellite` `CLIPBOARD` selection) and synthesizes `Ctrl+V` without touching human `seat0` | WPS Office for Linux (Qt/XWayland), LibreOffice, Wine apps; natively supports **`text/html` styled blocks** and **`text/tab-separated-values` multi-cell spreadsheet pastes** | 
| **Tier 3** | **Ephemeral XKB Keymap Remapping** | Temporarily maps unused keycodes to target Unicode keysyms (similar to [`wtype`](https://github.com/atx/wtype)), triggers key press/release, and restores the keymap | Fallback for custom-rendered inputs that neither bind `text-input-v3` nor accept clipboard paste | 

## 6. Timed Macro System and Dual-Brain (Dedicated Decision Model + Local) Control Loop

### 6.1 Native Demonstration Recording and Parameterized `Phodopus` Macros

For shortcut-dense workflows—such as WPS/Excel ribbon formatting and ruler dragging, Blender modal modeling (`G` -> axis lock -> numeric value), and DAW timeline editing—`komactl macro record` provides [`Selenium`](https://github.com/SeleniumHQ/selenium?featured_on=pythonbytes)-style demonstration capture directly inside the compositor:

1. **Denoising and 9-Anchor Compilation**: Captures exact key press/release holds, inter-key intervals, and pointer drags on `seat0`, coalescing jittery pointer motion into clean `pointer_drag` keyframes expressed relative to **9-point window edge/corner anchors** (e.g., `right - 24, top + 80`).

2. **Zero-Token Replay**: Emits clean, parameterized `.lua` functions executable thousands of times inside `Phodopus` with zero LLM token overhead.

### 6.2 System 1 (Dedicated Decision Model) + System 2 Dual-Brain Synergy

Pairing `Koma` with a dedicated decision model through a native decisions API (`50–100 ms` model compute, `150–250 ms` end-to-end latency, zero output tokens billed, evaluating up to `1,000` parallel questions per pass with low calibration error as detailed in the [Google DeepMind announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-decisions-api/)) forms a high-speed **System 1 / System 2** architecture:

* **Discrete Action Spaces Tailored to the `255`-Choice Ceiling**:

  * **Macro Skill Selection**: Up to `255` registered `Phodopus` macros for the active application are passed as a `choice` question, letting the decision model trigger a complete 20-step formatting or modeling combo in `150 ms` with zero output tokens.

  * **SoM & Two-Stage `15x15` (`225`-Cell) Grid Addressing**: When `AT-SPI2` nodes are available, `choice` picks directly among visible Set-of-Mark IDs; for raw canvas UIs (replacing brittle [`xdotool`](https://github.com/jordansissel/xdotool) pixel guessing), `koma-render` composites a two-level [`warpd`](https://github.com/rvaiya/warpd)-inspired **`15x15` (`225` <= `255`)** grid onto the offscreen snapshot, converging to `~10x6` pixel precision in two `150 ms` passes.

* **Single-Pass Safety Gating and Video Trajectory Grading**: Combined with a lightweight `DMA-BUF` ring-buffer recorder (modeled on [`wl-screenrec`](https://github.com/rosalyntg/wl-screenrec) and [`gpu-screen-recorder`](https://manpages.debian.org/unstable/gpu-screen-recorder-cli/gpu-screen-recorder.1.en.html)), a single request simultaneously evaluates action selection (`choice`), destructive-action gating (`noul`), progress scoring (`score`), and auth/challenge detection (such as [Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/get-started/)).

* **1-Second Human-in-the-Loop Handoff**: Because headless workspaces run genuine headed Wayland browsers without WebDriver/CDP injection flags and can mount authorized user profiles, routine browsing avoids headless-bot false positives; whenever `noul` detects a 2FA, Passkey, or verification prompt, `Koma` emits `HumanVerificationNeeded` so the user can press `Mod + G`, confirm in one second, and return the workspace to background execution.

* **Zero-Copy Local Gaming Agents (Neuro-sama Heterogeneous Pattern)**: Inspired by Neuro-sama's separation of millisecond vision policies, pathfinding bots, and conversational LLMs (see [Neuro-sama architectural history](https://arxiv.org/html/2509.20817v1) and [`VedalAI/neuro-game-sdk`](https://github.com/VedalAI/neuro-game-sdk/blob/main/API/PROPOSALS.md)), `koma-render` can downsample offscreen `DMA-BUF` textures on-GPU and share them zero-copy with local inference runtimes—supporting `2–5 ms` policy networks (`200+ Hz`) and `40–150 ms` micro-VLMs (aligned with [ROAR real-time gaming benchmarks](https://arxiv.org/html/2610.24282v2), [LiteVLM](https://arxiv.org/pdf/2506.07416), [DeepMind SIMA 2](https://arxiv.org/html/2512.04797v1), and [8 GB RTX 4060 local throughput baselines](https://modelfit.io/gpu/rtx-4060/)).

## 7. Seven Production Isolation, Security, and Power Invariants

1. **Single-Instance Application Escape Prevention**: To prevent apps like Firefox, Chromium, VS Code, or WPS from delegating new windows to an existing foreground instance over D-Bus/locks, `ws.spawn_bound` allocates per-client `WAYLAND_SOCKET` descriptors, tracks [`xdg-activation-v1`](https://wayland.app/protocols/xdg-activation-v1) tokens, and supplies isolated `--user-data-dir` and private session D-Bus presets.

2. **Cross-Process Portal Dialog Routing**: Full [`xdg-foreign-unstable-v2`](https://wayland.app/protocols/xdg-foreign-unstable-v2) parent-handle resolution automatically routes out-of-process `xdg-desktop-portal` file choosers into the originating headless workspace and `vSeat` rather than leaking onto the human's primary screen.

3. **Background Audio Muting and Isolated Capture**: `Koma` tags spawned processes with workspace metadata so a lightweight [PipeWire / WirePlumber](https://docs.pipewire.org/page_overview.html) Lua rule routes headless workspaces to muted virtual null-sinks (retaining monitor ports for per-workspace agent audio capture) and restores physical audio output upon `Headed` promotion.

4. **Canonical Viewports and 9-Anchor Coordinates**: Locking headless workspaces to deterministic viewport dimensions (`Deck` mode) plus edge-anchored macro coordinates prevents layout resizes from invalidating recorded macros.

5. **Dual-Socket Capability Partitioning and Protected Surface Blackout**: Separates `koma-admin.sock` (human control) from `koma-agent.sock` (scoped `CapabilityToken` access restricted strictly to agent-owned headless workspaces); enforces [`security-context-v1`](https://wayland.app/protocols/security-context-v1) to block sandboxed Flatpak/container escalation; and masks lockscreens, Polkit prompts, and password managers black in snapshots while rejecting synthetic input.

6. **Hybrid GPU (`iGPU + dGPU` PRIME) `D3cold` Sleep Preservation**: `koma-render` binds strictly to the boot integrated GPU DRM node for compositor duties so background workspaces never wake a discrete NVIDIA GPU from `D3cold` sleep unless a workload explicitly requests `DRI_PRIME=1` or local CUDA interop.

7. **Live Lua Reload and Session Survival**: Reloading `~/.config/koma/init.lua` swaps only the `Phodopus` arena without dropping Wayland client sockets, pairs with Winit nested mode during development, and targets [`xx-session-management-v1`](https://wayland.app/protocols/xx-session-management-v1) for crash-resilient window-state restoration.

## 8. Phased Implementation Roadmap

* **Phase 0 (Nested PoC)**: `Smithay` Winit backend running `1` headed viewport + `1` offscreen headless workspace, isolated `vSeat` focus, `text-input-v3` direct string commit, and `Render-on-Read` frame export.

* **Phase 1 (Bare-Metal Daily Driver & `Phodopus`)**: DRM/KMS + `libseat` session startup, `xwayland-satellite` integration, `koma-lua` hot-reloadable layouts/rules, `komactl gen-types`, and `wlr-layer-shell` compatibility.

* **Phase 2 (Locks, Kinematics & Macro Compiler)**: `WorkspaceLease + Epoch` preemption fencing, `Deck / Stash` stacks, kinematic pointer curves, isolated MIME clipboard paste, and `komactl macro record`.

* **Phase 3 (Ecosystem Daemons & Dual-Brain Agents)**: `koma mcp` stdio server, `koma-overview` hover thumbnailer and live deck, `DMA-BUF` ring-buffer recording integration, and reference decision-model macro/grid agent loops.


---

## 9. Window Engine, GPU Rendering & Companion `Jiku` Baseline (v0.2)

### 9.1 Per-Workspace Dual-Layer `CSpace` (`Dwindle` Default + `Scrolling` + `Deck` + `Scratchpad`)

`koma-model` implements a symmetrical dual-layer workspace container (`WorkspaceState` combining an active tiled layout with a Z-ordered `FloatingStack` plus `special:<name>` Scratchpad overlays):

* **Human `Headed` Default — `Dwindle` (`crates/koma-model/src/dwindle.rs`)**: Modeled on Hyprland's `DwindleAlgorithm`, dynamically splitting the hovered or active tile by aspect ratio (`force_split`, `preserve_split`, `default_split_ratio`), automatically downgrading fixed-size dialogs (`max_size` smaller than target tile or `xdg_toplevel.parent()`) to centered floating windows, and supporting `pseudotile` plus 4-quadrant `smart_split` drop-zone previews during `Mod + MouseLeft` drags.
* **Optional Infinite Tape — `Scrolling` (`crates/koma-model/src/scrolling.rs`)**: Modeled on Niri's `ScrollingSpace`, featuring:
  1. Multi-tile vertical column stacking (`1..=N` `ScrollingTile`s per `ScrollingColumn` with `TileHeight::{Auto, Preset}` and `preset_window_heights`),
  2. Bidirectional `consume_or_expel_window_{left,right}` (`Mod + [` / `Mod + ]`) and explicit `consume_window_into_column` / `expel_window_from_column` (`Mod + ,` / `Mod + .`),
  3. Per-column **`ColumnDisplay::{Normal, Tabbed}`** (`Mod + W` `toggle_column_tabbed_display`) with anti-aliased SDF rounded **`tab-indicator`** pills (`Left`/`Right`/`Top`/`Bottom`, `hide_when_single_tab`, `place_within_column`, click-to-switch),
  4. `preset_column_widths` cycling (`Mod + R` / `Mod + Ctrl + R`), `CenterFocusedColumn` (`Never`, `Always`, `OnOverflow`), velocity-inheriting `camera_spring`, 1:1 3-finger touchpad swipe tracking with `0.997` kinetic deceleration projection, and `30 px` / `100 ms` / `1500 px/s` drag edge auto-scroll.
* **Agent `Headless` Default — `Deck / Stash`**: Keeps the active window at 100% canonical `1920x1080` resolution for crisp VLM grounding while background helper windows reside in `Stash`.
* **`special:<name>` Scratchpad Overlays**: Invoked via `Mod + S` (`ScratchpadToggle`), composited above the active physical workspace with a `#090b10` translucent dim scrim (`append_scratchpad_dim_scrim`) without disturbing underlying tile trees.

### 9.2 GPU Rendering, SDF Rounded Clipping & Multi-Pass `Dual Kawase Blur`

* **Velocity-Preserving 2nd-Order `Spring` (`crates/koma-model/src/animation.rs`)**: Analytical closed-form underdamped/critically-damped solver (`WindowAnimationTable` & `camera_spring`) inheriting instantaneous velocity across mid-flight retargets; automatically bypassed (`0 ms`) on `Headless` workspaces and during live `Mod + MouseRight` divider drags.
* **SDF Rounded Corners & Borders (`crates/koma-render/src/shaders.rs`, `elements.rs`)**: 1-pixel analytical smoothstep Signed Distance Field clipping for `WaylandSurfaceRenderElement`s (`KomaClippedSurfaceElement`), hollow border rings, and solid `tab-indicator` pills (`KomaRoundedBorderElement`).
* **`Dual Kawase Blur` Pyramid (`crates/koma-render/src/blur_pipeline.rs`)**: Multi-pass downsample/upsample FBO pyramid with hash dithering noise, contrast/brightness modulation, blur damage radius expansion, `xray` backdrop caching, and zero-overhead bypass on `Headless` workspaces.

### 9.3 Bare-Metal Session, `xwayland-satellite`, Shadow-VM Hot-Reload & Wayland Jails

* **Bare-Metal `DRM/KMS` + `libseat` (`crates/koma/src/backend_tty.rs`)**: Rootless `LibSeatSession`, `udev` hotplug, `libinput` gestures, atomic KMS VBlank page-flip loop, and hybrid iGPU + NVIDIA dGPU multi-GPU format negotiation (`Abgr2101010`, `Argb8888`, `Abgr8888`).
* **On-Demand `xwayland-satellite` (`crates/koma/src/xwayland_satellite.rs`)**: Dual abstract + filesystem `/tmp/.X11-unix/X<N>` socket activation with automatic crash re-arming and per-workspace `DISPLAY` isolation.
* **`systemd --user` & `greetd` Integration (`resources/koma-session`, `koma.service`, `greetd-config.toml`)**: `sd_notify` `READY=1` synchronization ensuring `WAYLAND_DISPLAY` and `DISPLAY` are imported into `systemd --user` and D-Bus activation environments before `xdg-desktop-autostart.target` (`waybar`, `fcitx5`, `swaync`) starts.
* **Shadow-VM Transactional Hot-Reload (`crates/koma/src/config_watcher.rs`)**: `inotify` directory + symlink-safe fingerprint watcher evaluating `~/.config/koma/init.lua` and `lua/*.lua` inside an isolated shadow `PhodopusSandbox` before atomic swap; syntax or regex errors preserve live state and illuminate a `4 px` `#f85149` top alert bar.
* **`wp-security-context-v1` & `komactl sandbox run` (`crates/koma/src/security_context.rs`, `crates/komactl/src/sandbox_runner.rs`)**: Filters privileged globals (`zwlr_layer_shell_v1`, `ext_session_lock_manager_v1`, `zwlr_data_control_manager_v1`, `zwp_virtual_keyboard_manager_v1`, nested `wp_security_context_manager_v1`) from restricted clients and issues per-workspace `0600` jailed Wayland sockets mounted into `Bubblewrap` or rootless `Podman` containers.
* **`ext-workspace-v1` Status-Bar Workspace Model (`crates/koma/src/ext_workspace.rs`)**: Advertised to unrestricted clients only. One `ext_workspace_group_handle_v1` owns every output, one `ext_workspace_handle_v1` per Koma workspace publishes the `WorkspaceId` as the protocol `id`, the workspace name, unique 1D `coordinates` in strip order, and the `active` (displayed) / `hidden` state bits; property events are delta-only and batched by `done`, and `workspace.activate` routes through `KomaState::focus_workspace` so a bar click lands in exactly the same state as `Mod + 1..0` (ignored while locked). `urgent`, `deactivate`, `assign`, `remove` and `create_workspace` are not advertised and are ignored if sent.

### 9.4 Three-Tier Agent Ecosystem & Companion `Jiku` Daemon

`Koma` pairs with **`Jiku` (`jikud` / `jiku`)**, its dedicated same-UID sandboxed companion GUI agent (specified in **`docs/JIKU_ARCHITECTURE.md`** and **`docs/JIKU_CONFIG_SPEC.md`**), alongside `komactl` + `SKILL.md` for terminal Coding Agents (`Claude Code`, `Codex`) and `jiku mcp` / `koma mcp` for standard MCP desktop hosts.
