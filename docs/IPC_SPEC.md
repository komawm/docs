# Koma (`komawm`) IPC Protocol & Capability Specification

> **Status**: Protocol Baseline v0.1 (Draft Accepted)
> **Owning Crate**: `crates/koma-proto` (Wire types) & `crates/koma` (Socket server)
> **Companion Document**: `docs/ARCHITECTURE.md`

## 1. Scope and Design Goals

This specification defines the wire framing, dual-socket topology, `CapabilityToken` authorization model, monotonic `Epoch` concurrency fencing, RPC method catalog, and asynchronous event stream implemented by `koma-proto`.

In alignment with `Koma`'s Unix philosophy (acting as a workspace-isolated desktop counterpart to Android's [`adb`](https://developer.android.com/tools/adb) while pushing [`open-computer-use`](https://github.com/iFurySt/open-computer-use) primitives directly into the Wayland compositor), the IPC layer satisfies four hard invariants:

1. **Zero Compositor Blocking**: All socket reads, writes, and event broadcasts execute non-blockingly on [`calloop`](https://github.com/Smithay/calloop). Slow or wedged IPC clients are bounded by ring-buffer watermarks and dropped before they can delay a `240 Hz` hardware VSync frame.

2. **Least-Privilege Workspace Isolation**: External AI agents and MCP servers connect to a dedicated restricted socket (`koma-agent.sock`) and cannot observe or inject input into human `Headed` workspaces without explicit administrative delegation.

3. **Zero TOCTOU Mis-Clicks**: Every state-mutating request against a workspace is fenced by a monotonically increasing 64-bit `epoch` counter, guaranteeing deterministic rejection of stale in-flight agent actions whenever a human preempts control.

4. **Zero-Copy Binary Bulk Transfer**: Large payloads (screenshots, `DMA-BUF` GPU planes, and rich clipboard buffers) cross process boundaries via POSIX `SCM_RIGHTS` file descriptors (`memfd` / `DMA-BUF`) rather than multi-megabyte JSON Base64 strings whenever the peer runs locally.

## 2. Dual-Socket Topology and Wire Framing

### 2.1 Socket Paths and Peer Discovery

When `koma` starts a session, it creates a mode-`0700` runtime directory under `$XDG_RUNTIME_DIR/koma/<instance_signature>/` and exports `KOMA_INSTANCE_SIGNATURE` to child processes (following the multi-instance convention popularized by [`bspwm`](https://github.com/baskerville/bspwm) and [`Hyprland`](https://github.com/hyprwm/hyprland)):

| Socket Filename       | File Mode | Intended Clients                                               | Authentication & Default Authority                                                                                                                                                                                                                                                                                 |
| --------------------- | --------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **`koma-admin.sock`** | `0600`    | `komactl`, `koma-overview`, status bars, human keybind scripts | Verified via kernel peer credentials (`SO_PEERCRED` on Linux, `LOCAL_PEERCRED` on FreeBSD/OpenBSD) and blocked for sandboxed clients tagged via [`security-context-v1`](https://wayland.app/protocols/security-context-v1). Grants full workspace lifecycle, token minting, macro recording, and `Headed` control. |
| **`koma-agent.sock`** | `0600`    | `koma-mcp`, autonomous agents, untrusted automation scripts    | Connection starts in `Unauthenticated` state; the first frame **must** be `auth.authenticate` carrying a valid `CapabilityToken`. Grants access strictly to token-scoped workspaces.                                                                                                                               |

### 2.2 Binary Frame Header and `SCM_RIGHTS` Ancillary FDs

To eliminate newline-escaping overhead while remaining trivial to parse in Rust, Go, Python, or Node.js, every message on both sockets uses a 4-byte little-endian length prefix followed by a UTF-8 JSON envelope:

- **Header**: `u32` little-endian payload length in bytes (`1` to `16,777,216`; frames exceeding `16 MiB` trigger immediate socket disconnect with `ERR_FRAME_TOO_LARGE`).

- **Body**: UTF-8 JSON object conforming to `IpcRequest`, `IpcResponse`, or `IpcEventEnvelope`.

- **Ancillary Control Message (`SCM_RIGHTS`)**: Up to `4` file descriptors (`DMA-BUF` plane FDs or sealed read-only `memfd` descriptors) may accompany a single frame. JSON fields reference attached descriptors by zero-based index (`"fd_index": 0`).

### 2.3 Top-Level Rust Wire Envelope (`koma-proto`)

```
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IpcRequest {
    pub id: u64,
    pub method: String,
    #[serde(default)]
    pub params: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IpcResponse {
    pub id: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<IpcError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IpcError {
    pub code: u16,
    pub symbol: ErrorSymbol,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current_epoch: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub retryable: Option<bool>,
}

```

## 3. `CapabilityToken` Model and Protected Surfaces

### 3.1 Token Structure and Scope Rules

A `CapabilityToken` is an ephemeral 256-bit cryptographically random secret (`koma_cap_<43-char-base64url>`) stored exclusively in compositor RAM and never written to disk. Administrators (or `koma` when spawning `koma-mcp`) mint tokens via `auth.mint_token` on `koma-admin.sock`:

```
{
  "id": 1,
  "method": "auth.mint_token",
  "params": {
    "label": "claude-code-mcp",
    "ttl_secs": 28800,
    "can_create_headless": true,
    "max_owned_workspaces": 4,
    "workspace_grants": {
      "ws_ref_docs": "observe_only"
    },
    "allow_clipboard_bridge_from": ["ws_ref_docs"]
  }
}

```

Each `WorkspaceGrant` resolves to one of three monotonically ordered privilege levels:

1. **`observe_only`**: Permits `scene.inventory`, `scene.tree`, `capture.frame`, and read-only event subscriptions on that workspace. Rejects all `win.*`, `vseat.*`, `ws.destroy`, and `lua.exec_tx` calls.

2. **`control`**: Permits acquiring `WorkspaceLease`, mutating window stack state (`win.*`), injecting `vSeat` input (`vseat.*`), and running bounded `Phodopus` transactions (`lua.exec_tx`), subject to `Epoch` fencing.

3. **`owner`**: Includes `control` plus permission to adjust headless frame policies (`ws.set_frame_policy`), spawn bound processes (`ws.spawn_bound`), and destroy the workspace (`ws.destroy`). Automatically granted for any headless workspace created by the token holder when `can_create_headless` is `true`.

**Hard Isolation Rule**: A token on `koma-agent.sock` can **never** receive `control` or `owner` over a workspace currently bound to a physical monitor in `HumanPreempted` mode.

### 3.2 Protected Surface Blackout Invariant

Regardless of workspace grant, `koma-render` and `koma-seat` classify the following surfaces as **Protected Surfaces**:

- Active session lock surfaces (`ext-session-lock-v1`);

- System privilege escalation dialogs (`polkit-gnome-authentication-agent`, `hyprpolkitagent`, `pinentry-*`);

- Configured sensitive `app_id` patterns (e.g., `org.keepassxc.KeePassXC`, `com.bitwarden.desktop`, `1password`).

When a Protected Surface is mapped:

1. `capture.frame` and `capture.export_dmabuf` paint its bounding box (including transient `xdg_popup` children) solid opaque `#000000` before export and set `"has_protected_blackout": true` in frame metadata.

2. Any `vseat.*` action targeting or intersecting a Protected Surface immediately aborts with `ERR_PROTECTED_SURFACE` (`4032`) and emits `security.verification_needed`.

## 4. `Lease + Epoch` Concurrency Fencing Protocol

### 4.1 Monotonic Epoch Transitions

Every workspace initializes with `epoch = 1` (`u64`) and `lease = Unheld`. The compositor increments `epoch` atomically (`epoch += 1`) on **every** lease ownership or human-takeover boundary:

| Transition Event                                 | Previous Lease State            | New Lease State                 | Epoch Mutation & Side Effects                                                                                                                                          |
| ------------------------------------------------ | ------------------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`lease.acquire`** (or `auto_acquire` on write) | `Unheld`                        | `AgentExclusive(A)`             | `epoch = N + 1`; returned to agent `A`                                                                                                                                 |
| **`lease.release`** (or agent socket disconnect) | `AgentExclusive(A)`             | `Unheld`                        | `epoch = N + 1`; synthesizes `vSeat` key/button releases                                                                                                               |
| **Human enters `Peek`** (`ws.set_mode("peek")`)  | `AgentExclusive(A)`             | `AgentExclusive(A)`             | **`epoch` unchanged (`N`)**; `seat0` input is shielded so agent `A` continues uninterrupted                                                                            |
| **Human presses `Mod + G` (`Takeover`)**         | `AgentExclusive(A)` or `Unheld` | `HumanPreempted`                | **`epoch = N + 1`**; flushes held virtual keys/buttons in `< 1 ms`, cancels `Phodopus` `HostOpHandle` coroutines, routes `seat0` focus in, emits `workspace.preempted` |
| **Human presses `Mod + G` (Release Takeover)**   | `HumanPreempted`                | `AgentExclusive(A)` or `Unheld` | **`epoch = N + 2`**; detaches `seat0`, emits `workspace.resumed { new_epoch: N + 2 }`                                                                                  |

### 4.2 Deterministic Four-Step Gate on Every Mutating RPC

Every mutating RPC (`win.*`, `vseat.*`, `lua.exec_tx`) **must** include `"ws_id"` and `"expected_epoch"`. Inside the single-threaded `calloop` dispatcher, `koma` validates in strict order before mutating any state:

1. **Capability Check**: Token holds `control` or `owner` on `ws_id` -> else `4030 ERR_CAPABILITY_DENIED`.

2. **Human Preemption Check**: `ws.lease != HumanPreempted` -> else `4091 ERR_HUMAN_PREEMPTED` (includes `current_epoch`).

3. **Writer Mutex Check**: `ws.lease` is held by `caller_session_id` (or `Unheld` when `"auto_acquire": true`) -> else `4092 ERR_LEASE_HELD_BY_OTHER`.

4. **Epoch Fence Check**: `params.expected_epoch == ws.epoch` -> else **`4090 ERR_STALE_EPOCH`** (includes `current_epoch`).

**Client Recovery Contract**: Upon receiving `ERR_STALE_EPOCH` or `ERR_HUMAN_PREEMPTED`, an agent **must never** blindly retry the failed action with the new epoch; it must wait for `workspace.resumed` (if preempted), invoke `capture.frame` or `scene.tree` to read the updated UI state and new `epoch`, and recompute its decision.

### 4.3 Canonical Error Code Registry

| Code   | `ErrorSymbol`             | Retryable | Meaning                                                                   |
| ------ | ------------------------- | --------- | ------------------------------------------------------------------------- |
| `4000` | `ERR_INVALID_PARAMS`      | `false`   | Malformed JSON or out-of-range coordinate/parameter                       |
| `4001` | `ERR_FRAME_TOO_LARGE`     | `false`   | Payload exceeded `16 MiB` wire ceiling                                    |
| `4010` | `ERR_UNAUTHENTICATED`     | `false`   | RPC sent on `koma-agent.sock` prior to `auth.authenticate`                |
| `4030` | `ERR_CAPABILITY_DENIED`   | `false`   | Token lacks required grant (`observe_only` vs `control` / `owner`)        |
| `4032` | `ERR_PROTECTED_SURFACE`   | `false`   | Target is a lockscreen, Polkit agent, or denylisted password manager      |
| `4040` | `ERR_NOT_FOUND`           | `false`   | Unknown `ws_id`, `win_id`, or `macro_id`                                  |
| `4090` | `ERR_STALE_EPOCH`         | `false`   | `expected_epoch != ws.epoch`; caller must re-observe before acting        |
| `4091` | `ERR_HUMAN_PREEMPTED`     | `true`    | Human currently holds `Takeover` on `ws_id`; await `workspace.resumed`    |
| `4092` | `ERR_LEASE_HELD_BY_OTHER` | `true`    | Another agent session holds `AgentExclusive` write lease                  |
| `4290` | `ERR_QUOTA_EXCEEDED`      | `false`   | Exceeded workspace count ceiling, `Phodopus` `Fuel` budget, or heap quota |
| `5040` | `ERR_SETTLE_TIMEOUT`      | `true`    | Action delivered, but surface damage did not settle within `timeout_ms`   |

## 5. RPC Method Schemas by Namespace

### 5.1 Authentication & Lease Control (`auth.*`, `lease.*`)

```
// Request: Authenticate on koma-agent.sock
{
  "id": 1,
  "method": "auth.authenticate",
  "params": {
    "token": "koma_cap_9vK2mPq8...",
    "client_name": "koma-mcp-stdio",
    "protocol_version": "0.1"
  }
}

// Response
{
  "id": 1,
  "result": {
    "session_id": "sess_01jd8x9",
    "can_create_headless": true,
    "grants": { "ws_ref_docs": "observe_only" }
  }
}

```

- **`lease.acquire`**: `{ "ws_id": "ws_work_1", "ttl_ms": 60000 }` -> `{ "epoch": 12, "expires_at_ms": 1794580060000 }`.

- **`lease.heartbeat`**: `{ "ws_id": "ws_work_1", "expected_epoch": 12, "ttl_ms": 60000 }` -> `{ "epoch": 12 }`.

- **`lease.release`**: `{ "ws_id": "ws_work_1", "expected_epoch": 12 }` -> `{ "epoch": 13 }`.

### 5.2 Workspace & Sandboxed Process Lifecycle (`ws.*`)

```
// Request: Create an isolated headless workspace and spawn an app bound to it
{
  "id": 2,
  "method": "ws.create",
  "params": {
    "name": "wps-thesis",
    "mode": "headless",
    "viewport": { "width": 1920, "height": 1080, "scale": 1.0 },
    "default_layout": "deck",
    "acquire_lease": true
  }
}

// Response
{
  "id": 2,
  "result": {
    "ws_id": "ws_01",
    "epoch": 1,
    "vseat_id": "vseat_01"
  }
}

```

- **`ws.spawn_bound`**:

  - Params: `{ "ws_id": "ws_01", "expected_epoch": 1, "argv": ["wps", "thesis.docx"], "isolation_preset": "private_dbus_and_profile", "audio_policy": "muted_virtual_sink" }`.

  - Behavior: Allocates a dedicated client `WAYLAND_SOCKET`, tracks [`xdg-activation-v1`](https://wayland.app/protocols/xdg-activation-v1) tokens and [`xdg-foreign-unstable-v2`](https://wayland.app/protocols/xdg-foreign-unstable-v2) portal dialogs back to `ws_01`, and tags [PipeWire](https://docs.pipewire.org/page_overview.html) properties for background audio muting.

- **`ws.set_mode`** (`koma-admin.sock` for `takeover`): `{ "ws_id": "ws_01", "mode": "headless" | "peek" | "takeover", "output": "eDP-1" }`.

- **`ws.focus`** (`koma-admin.sock` only): `{ "ws_id": "ws_01" }` or `{ "name": "2" }` -> Switches the focused workspace exactly like the `WorkspaceFocus` action (`Mod + 1..0`): output mapping, geometry resync, idle inhibitors, foreign-toplevel updates and the transition animation all follow the keybind path. The session lock gate applies, so the call is rejected while the session is locked.

  Only an **existing** workspace is accepted; an unknown id or name returns `ErrNotFound` instead of creating a workspace, because a status-bar click must not have that side effect (the keybind path keeps its create-on-demand behaviour). Response: `{ "focused": "2", "active_ws_id": "ws_02" }`.

  Shell helper: `komactl ws focus <ws_id|name>`. For a native Waybar module, `ext-workspace-v1` is still the long-term answer; this method covers scripted and per-module bar wiring until then.

### 5.3 Spatial Inventory, Window Stack & Damage Synchronization (`scene.*`, `win.*`)

```
// Request: Low-token global spatial inventory for agent context
{ "id": 3, "method": "scene.inventory", "params": {} }

// Response
{
  "id": 3,
  "result": {
    "workspaces": [
      {
        "ws_id": "ws_01",
        "name": "wps-thesis",
        "mode": "headless",
        "frame_tier": "idle_heartbeat",
        "epoch": 4,
        "lease": { "state": "agent_exclusive", "holder": "sess_01jd8x9", "is_self": true },
        "viewport": { "width": 1920, "height": 1080, "scale": 1.0 },
        "active_window": { "win_id": "win_9a_g1", "app_id": "wps", "title": "thesis.docx" },
        "stash_windows": [
          { "win_id": "win_9b_g1", "app_id": "et", "title": "metrics.xlsx" }
        ]
      }
    ]
  }
}

```

- **`scene.tree`**: `{ "ws_id": "ws_01", "win_id": "win_9a_g1", "include_popups": true }` -> Returns exact surface-local and workspace-global bounding boxes for the toplevel (matching [`ext-foreign-toplevel-list-v1`](https://wayland.app/protocols/ext-foreign-toplevel-list-v1) generation-safe IDs) and any open `xdg_popup` menus.

- **`win.activate`**: `{ "ws_id": "ws_01", "win_id": "win_9b_g1", "expected_epoch": 4 }` -> Promotes a `Stash` window to the top of the `Deck` and waits for initial frame commit.

- **`win.set_geometry`**: `{ "ws_id": "ws_01", "win_id": "win_9a_g1", "expected_epoch": 4, "mode": "deck" | "floating" | "fullscreen", "rect": { "x": 0, "y": 0, "w": 1280, "h": 800 } }`.

- **`scene.wait_settle`**: `{ "ws_id": "ws_01", "quiet_ms": 60, "timeout_ms": 1000 }` -> Suspends until no `wl_surface.damage_buffer` commits occur for `quiet_ms`.

### 5.4 Zero-Copy Capture & Compositor Overlays (`capture.*`)

```
// Request: Render-on-Read single-window snapshot with 15x15 (225-cell) warpd grid overlay
{
  "id": 4,
  "method": "capture.frame",
  "params": {
    "ws_id": "ws_01",
    "win_id": "win_9a_g1",
    "overlay": {
      "kind": "grid_225",
      "sub_cell": null
    },
    "max_edge": 1920,
    "format": "webp",
    "transport": "shm_fd"
  }
}

// Response (accompanied by 1 sealed read-only memfd in SCM_RIGHTS at fd_index 0)
{
  "id": 4,
  "result": {
    "epoch": 4,
    "width": 1920,
    "height": 1080,
    "byte_len": 148290,
    "fd_index": 0,
    "has_protected_blackout": false,
    "grid_cells": 225
  }
}

```

- **Overlay Modes**: `"none"`, `"som"` (draws numbered bounding boxes from `AT-SPI2` / semantic hints), or `"grid_225"` (draws a `15x15` [`warpd`](https://github.com/rvaiya/warpd)-style labeled grid tailored to the `255`-option `choice` ceiling of native decisions-API `choice` models).

- **`capture.export_dmabuf`**: Exports multi-planar `DMA-BUF` FDs, DRM `fourcc`, `modifier`, `stride`, and `offset` metadata via `SCM_RIGHTS` (aligned with [`ext-image-capture-source-v1`](https://wayland.app/protocols/ext-image-capture-source-v1) and [`ext-image-copy-capture-v1`](https://wayland.app/protocols/ext-image-copy-capture-v1)) for zero-CPU-copy ring recorders like [`wl-screenrec`](https://github.com/rosalyntg/wl-screenrec) or local GPU tensor import.

### 5.5 Virtual Seat Input, Kinematics & Zero-IME Injection (`vseat.*`)

```
// Request: Kinematic pointer drag with minimum-jerk velocity profile and damage-settle sync
{
  "id": 5,
  "method": "vseat.drag",
  "params": {
    "ws_id": "ws_01",
    "expected_epoch": 4,
    "button": "left",
    "from": { "x": 312, "y": 142 },
    "to": { "x": 468, "y": 142 },
    "kinematics": {
      "profile": "minimum_jerk",
      "arc_curvature": 0.12,
      "duration_ms": 110
    },
    "settle": { "quiet_ms": 50, "timeout_ms": 500 }
  }
}

```

- **Device & Coordinate Modes**: `vseat.pointer_move`, `vseat.click`, and `vseat.drag` accept `"device": "pointer" | "relative" | "tablet"` (driving [`wl_pointer`](https://wayland.app/protocols/wayland), `zwp_relative_pointer_v1`, or [`tablet-v2`](https://wayland.app/protocols/tablet-v2) respectively) and `"profile": "instant" | "minimum_jerk" | "spring" | "hooke" | "hooke_spring" | "bezier"` with optional Hooke/Bezier fields (`mass`, `damping`, `damping_ratio`, `stiffness`, `epsilon`, `curve`, `bezier`, `duration_ms`, `arc_curvature`). `vseat.drag` routes button presses/releases and motion cleanly through Smithay `ClickGrab`, and `vseat.click` accepts optional `modifiers` and `label`.

- **Extended Precision & Visual Indicator RPCs (`v0.0.1`)**:
  - `vseat.path` / `vseat.stroke`: Multi-waypoint trajectories (`"spline": "auto" | "catmull_rom" | "bezier"`, centripetal $\alpha = 0.5$ interpolation, `250 Hz` adaptive sub-frame resampling, optional mouse `button` hold for spline drawing).
  - `vseat.relative_move`, `vseat.wheel`, `vseat.hit_test`, `vseat.cursor_label`, and `vseat.cursor_settle`: Relative pointer deltas, wheel scrolling, surface hit-testing without actuation, floating `LabelPill` + `caret_rect` caption control, and smooth cursor settling.
  - `DeliverySemantics`: IPC errors populate `disposition` (`DeliveryDisposition` + `RetryDisposition`) so callers distinguish `NotDelivered` / `DeliveryUncertain` from verified execution.
  - `koma-mcp` stdio server lazily connects to `koma-agent.sock`, auto-detects `Content-Length` vs `NDJSON` framing per message, and exposes all 17 core tools (`koma_ping`..`koma_cursor_label`).

- **`vseat.key`**: `{ "ws_id": "ws_01", "expected_epoch": 4, "modifiers": ["Ctrl", "Shift"], "key": "End", "action": "tap" | "down" | "up", "hold_ms": 30 }`.

- **`vseat.inject_text`**: `{ "ws_id": "ws_01", "expected_epoch": 4, "text": "Chapter 1: System Architecture\n", "strategy": "auto" }` -> Executes the 3-tier Zero-IME cascade ([`text-input-unstable-v3`](https://wayland.app/protocols/text-input-unstable-v3) direct `commit_string` -> isolated `vSeat` clipboard paste -> [`wtype`](https://github.com/atx/wtype)-style ephemeral XKB keymap).

- **`vseat.paste_mime`**: `{ "ws_id": "ws_01", "expected_epoch": 4, "mime_type": "text/tab-separated-values", "data_utf8": "Metric\tLatency\nDecision-1\t150ms\n" }` (or `"fd_index": 0` for large HTML/image payloads).

### 5.6 `Phodopus` Batch Transactions & Macro Recording (`lua.*`, `macro.*`)

```
// Request: Execute a parameterized Phodopus Lua macro atomically under Epoch 4
{
  "id": 6,
  "method": "lua.exec_tx",
  "params": {
    "ws_id": "ws_01",
    "expected_epoch": 4,
    "macro_id": "wps.apply_heading_style",
    "args": { "level": 1, "indent_px": 32 },
    "fuel_budget": 100000,
    "memory_limit_bytes": 4194304,
    "timeout_ms": 2000
  }
}

```

- **`macro.record_start` / `macro.record_stop`** (`koma-admin.sock` only): Captures `seat0` demonstrations on a target window, denoises pointer jitter into 9-anchor relative coordinates, and returns parameterized Lua 5.4 source ready to save under `~/.config/koma/lua/macros/`.

## 6. Asynchronous Event Stream Specification (`events.subscribe`)

Clients subscribe to push notifications over a dedicated or multiplexed socket connection using `events.subscribe`:

```
{
  "id": 7,
  "method": "events.subscribe",
  "params": {
    "workspaces": ["ws_01"],
    "topics": [
      "workspace.lifecycle",
      "workspace.lease",
      "window.topology",
      "window.damage_settled",
      "security.alerts"
    ]
  }
}

```

### 6.1 Unsolicited Event Frame Envelope

Subscribed connections receive `IpcEventEnvelope` frames (distinguished from `IpcResponse` by the absence of `"id"` and presence of `"seq"` + `"topic"`):

```
{
  "seq": 1042,
  "timestamp_ns": 1794580012948102,
  "topic": "workspace.lease",
  "ws_id": "ws_01",
  "epoch": 5,
  "event": {
    "kind": "workspace.preempted",
    "reason": "human_hotkey_takeover",
    "flushed_keys": ["Shift_L"],
    "cancelled_lua_tx": true
  }
}

```

### 6.2 Canonical Event Variant Catalog

| Topic                       | `event.kind`                                              | Trigger & Payload Fields                                                                                                                            |
| --------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`workspace.lifecycle`**   | `workspace.created` / `mode_changed` / `destroyed`        | Emitted on creation, `Headless` <-> `Peek` <-> `Takeover` mode flips, or frame-tier transitions (`frame_tier`).                                     |
| **`workspace.lease`**       | `workspace.epoch_changed` / `preempted` / `resumed`       | Emitted on every `epoch` increment; carries `new_epoch`, `holder`, `flushed_keys`, and `cancelled_lua_tx`.                                          |
| **`window.topology`**       | `window.mapped` / `activated` / `popup_opened` / `closed` | Carries `win_id`, `app_id`, `title`, `rect`, `is_popup`, and `portal_parent_win_id` (for routed `xdg-desktop-portal` dialogs).                      |
| **`window.damage_settled`** | `window.settled`                                          | Emitted when a burst window settles for the configured quiet interval (`quiet_ms`, `dirty_rect_union`).                                             |
| **`security.alerts`**       | `security.verification_needed`                            | Emitted when a Protected Surface (Polkit/password prompt) maps or an agent explicitly signals a 2FA / human verification gate (`reason`, `win_id`). |
| **`stream.control`**        | `stream.lagged`                                           | Emitted when a slow subscriber overflows its `256`-event non-blocking ring buffer (`dropped_count`, `latest_seq`).                                  |

### 6.3 Non-Blocking Backpressure Contract

Each subscribed socket owns a bounded `256`-slot ring buffer inside `koma`. If a subscriber stops reading:

1. Transient `window.damage_settled` events coalesce first;

2. If the ring remains full, oldest non-lease events are evicted and `dropped_count` increments;

3. Critical `workspace.preempted` and `workspace.epoch_changed` state transitions are never silently lost—upon buffer drain, the subscriber immediately receives `stream.lagged` followed by the latest authoritative `epoch` snapshot.

---

## 7. Administrative Sandbox Jail & Hot-Reload RPCs (`koma-admin.sock`)

In addition to Agent capture/input RPCs on `koma-agent.sock`, `koma-admin.sock` exposes administrative methods used by `komactl` and allowlisted `Jiku` App Profile launchers:

| Method                            | Parameters                                                                       | Result & Security Semantics                                                                                                                                                                                                                        |
| :-------------------------------- | :------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`sandbox.create_wayland_jail`** | `{ "workspace": "agent:work", "app_id": "chromium", "sandbox_engine": "bwrap" }` | Lazily creates/resolves the target `Headless` `Deck` workspace, binds an isolated mode-`0600` Wayland socket tagged with `ClientState { restricted = true, jailed_workspace = Some(ws_id) }`, and returns `{ "ws_id", "socket_path", "jail_id" }`. |
| **`sandbox.revoke_wayland_jail`** | `{ "ws_id": "ws_02" }`                                                           | Unlinks the jailed Wayland socket and removes its `calloop` listener when the container exits (`komactl sandbox run` RAII drop guard).                                                                                                             |
| **`config.validate`**             | `{ "path": null }`                                                               | Evaluates `~/.config/koma/init.lua` inside an isolated shadow `PhodopusSandbox` + compiles regex rules without mutating compositor state.                                                                                                          |
| **`config.reload`**               | `{ "path": null }`                                                               | Atomically swaps declarative config, keybinds, gestures, and rules if shadow validation succeeds.                                                                                                                                                  |
