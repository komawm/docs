# Koma (`komawm`) Lua Configuration & Macro API Specification

> **Document Path**: `docs/LUA_API_SPEC.md`
>
> **Target Crate**: `koma-lua` (Tier 1 Sandboxed Scripting Engine, embedding `Phodopus` pure-Rust stackless Lua 5.4)
>
> **User Entry Point**: `~/.config/koma/init.lua` (Modular imports jailed to `~/.config/koma/lua/`)
>
> **Type Stubs Command**: `komactl gen-types` (Emits [`LuaLS`](https://github.com/LuaLS/lua-language-server) `LuaCATS` annotations modeled on [`wezterm-types`](https://github.com/DrKJeff16/wezterm-types))

## 1. Design Philosophy & Execution Model

`Koma` unifies declarative desktop configuration and deterministic GUI macro automation inside a single embedded pure-Rust Lua 5.4 runtime (`Phodopus`, derived from [`kyren/piccolo`](https://github.com/kyren/piccolo)). The API design synthesizes three proven foundations:

1. **First-Class Handle Ergonomics**: Inspired by [`hyprwm/hyprland`](https://github.com/hyprwm/hyprland)'s [`hyprland.lua`](https://github.com/hyprwm/Hyprland/blob/main/example/hyprland.lua) interface, keybindings, window rules, layer rules, and macros return typed handles (`BindHandle`, `RuleHandle`, `MacroHandle`) supporting live toggling (`:set_enabled(bool)`) and removal (`:remove()`) without full reload.

2. **Two-Phase Flicker-Free Rule Evaluation**: Modeled on [`YaLTeR/niri`](https://github.com/YaLTeR/niri/wiki/index)'s `window-rule` pipeline and [`river-window-management-v1`](https://wayland.app/protocols/river-window-management-v1) atomic frame transactions, `Koma` separates **Initial Configure Properties** (resolved before the client's first buffer commit) from **Dynamic Reactive Properties** (re-evaluated on live title, focus, urgency, or screencast state changes).

3. **Stackless Coroutine Suspension over `calloop`**: Unlike blocking shell scripts, timed macros and interactive keybind callbacks execute as stackless `Phodopus` coroutines bridged to [`Smithay`](https://github.com/smithay/smithay)'s [`calloop`](https://github.com/Smithay/calloop) event loop via `SequencePoll::Suspend(HostOpHandle)`. Waiting on timers, kinematic pointer curves, or surface damage settlement never blocks `240 Hz` physical KMS scanout.

### 1.1 Two Execution Phases & Sandbox Quotas

Every Lua evaluation inside `koma-lua` runs under deterministic `gc-arena` memory ceilings and instruction `Fuel` metering:

| Execution Phase | Trigger | Allowed APIs | Default `Fuel` Budget | Heap Ceiling | Host Yielding (`HostOpHandle`) | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| **1. Config Load / Reload** | Startup or `komactl reload` | Declarative registration (`koma.monitor`, `koma.workspace`, `koma.input`, `koma.appearance`, `koma.bind`, `koma.rule.*`, `koma.macro.define`, `koma.on`) | `200,000` instructions | `4 MiB` | Forbidden (pure synchronous table build) | 
| **2. In-Frame Layout Hook** | Window map, unmap, or resize transaction | Pure geometry callbacks (`koma.layout.register`) | `50,000` instructions | `2 MiB` | Forbidden (must finish within single frame) | 
| **3. Async Action / Macro** | Keybind callback, IPC `lua.exec_tx`, or [`gemini-decision-1`](https://aistudio.google.com/docs/models/gemini-decision-1) choice dispatch | `MacroContext` (`ctx:*` input, text injection, sleep, damage-settle sync, window queries) | `100,000` per resume slice | `4 MiB` per coroutine | Allowed (`SleepTimer`, `WaitDamageSettle`, `PointerTrajectory`) | 

### 1.2 Indexing, Filesystem Jail & Live Reload Safety

* **Indexing Convention**: All Lua list/array tables passed to or returned from `koma.*` use idiomatic Lua **`1-based` indexing**. All pixel coordinates `(x, y)`, output positions, `0.0..1.0` normalized ratios, `Epoch` counters, and durations (`_ms`) strictly use **`0-based` numerical values**.

* **Sandboxed `require` Jail**: Standard `io`, `os.execute`, `debug`, and `package.loadlib` libraries are stripped from the `Phodopus` global environment. `require("foo.bar")` resolves exclusively within `~/.config/koma/lua/foo/bar.lua` and `~/.config/koma/lua/foo/bar/init.lua` (preventing symlink escape outside `~/.config/koma/`). Process spawning goes strictly through structured `koma.act.spawn({ ... })` or `ctx:spawn({ ... })` calls audited by Ring 0.

* **Atomic Shadow Arena Swap**: On `komactl reload`, `koma-lua` evaluates `init.lua` inside a shadow `Phodopus` arena. If syntax or schema validation fails, the previous arena remains active, Wayland client sockets and `WorkspaceLease` epochs stay untouched, and `koma` renders an overlay diagnostic banner displaying the exact Lua traceback.

* **Immutable Ring 0 Rescue Chords**: Regardless of Lua state, `koma-seat` reserves `Mod + G` (Human Preemptive Lease Takeover: `1 ms` virtual modifier flush + `epoch + 1` increment) and `Ctrl + Alt + F1..F12` (VT switch via [`libseat`](https://www.reddit.com/r/linuxquestions/comments/1ez8igt/whats_the_difference_between_seatd_and_logind/)) in compiled Rust prior to Lua dispatch.

## 2. Display, Output & Dual-Mode Workspace API

### 2.1 Physical Monitor Configuration (`koma.monitor`)

`koma.monitor(spec)` matches physical DRM connectors either by connector name (`"eDP-1"`, `"HDMI-A-1"`) or by EDID descriptor fields (`make`, `model`, `serial`) for dock-agnostic multi-monitor portability.

```
-- Primary laptop high-refresh display
koma.monitor({
    output = "eDP-1",
    mode = "2560x1600@240.000", -- Or "preferred", or { width = 2560, height = 1600, refresh_hz = 240.0 }
    position = { x = 0, y = 0 },
    scale = 1.6,                -- Native wp-fractional-scale-v1 + wp-viewporter
    transform = "normal",       -- "normal" | "90" | "180" | "270" | "flipped" | "flipped-90" | ...
    vrr = "on_demand",          -- false | true | "on_demand" (enabled only when matching window VRR rule is active)
    max_bpc = 10,               -- Optional connector color depth clamp (8 | 10 | 12)
    focus_at_startup = true,
    backdrop_color = "#111216",
})

-- External monitor matched by EDID rather than volatile DP-x connector index
koma.monitor({
    match = { make = "Dell Inc.", model = "DELL U2723QE" },
    mode = "preferred",
    position = "auto-right-of:eDP-1",
    scale = 1.5,
})

-- Dedicated VR headset connector leased directly via wp-drm-lease-v1
koma.monitor({
    match = { make = "Valve", model = "Index HMD" },
    drm_lease = true,
})

```

Custom timings for specialized displays or KVMs can pass a `modeline` table (`clock_mhz`, `hdisplay`, `hsync_start`, `hsync_end`, `htotal`, `vdisplay`, `vsync_start`, `vsync_end`, `vtotal`, `hsync_polarity`, `vsync_polarity`). Setting `off = true` disables the output via DPMS/atomic modeset.

### 2.2 Symmetrical Dual-Mode Workspaces (`koma.workspace`)

Unlike traditional compositors where offscreen outputs are ad-hoc fake monitors, `koma.workspace(spec)` declares persistent logical workspaces decoupled from physical connectors:

```
-- Human daily-driver workspace bound to physical output
koma.workspace({
    name = "1:code",
    presentation = "headed",
    preferred_output = "eDP-1",
    layout = "scrolling", -- "scrolling" | "bsp" | "deck"
    gaps = { inner = 8, outer = 12 },
})

-- Deterministic Headless Agent Workspace (0% idle GPU via LazyFbo + 4-tier clock)
koma.workspace({
    name = "agent:office",
    presentation = "headless",
    viewport = { width = 1920, height = 1080, scale = 1.0 },
    layout = "deck", -- Active window fills 100% viewport; background windows live in Stash
    frame_clock = {
        burst_hz = 60,        -- 1.0 s window after vSeat input or surface damage
        preview_hz = 8,       -- Thumbnail refresh rate when koma-overview is visible
        idle_freeze_ms = 10000,
    },
    isolate_vseat = true,     -- Dedicated wl_seat, focus, and clipboard detached from seat0
})

```

### 2.3 Input Devices & Visual Appearance (`koma.input`, `koma.device`, `koma.appearance`)

```
koma.input({
    mod_key = "Super",        -- "Super" | "Alt" (auto-switches to "Alt" when running nested under winit)
    keyboard = {
        layout = "us",
        variant = "",
        options = "caps:escape",
        repeat_delay_ms = 220,
        repeat_rate_hz = 35,
        numlock_on_startup = true,
    },
    pointer = {
        accel_profile = "flat", -- "adaptive" | "flat"
        accel_speed = 0.0,      -- -1.0 .. 1.0
        follow_mouse = "normal", -- "off" | "normal" | "focus_only"
    },
    touchpad = {
        tap_to_click = true,
        natural_scroll = true,
        disable_while_typing = true,
        scroll_factor = 1.0,
    },
    tablet = {
        map_to_output = "eDP-1", -- Compatible with kernel tablet-v2 and OpenTabletDriver virtual devices
        left_handed = false,
    },
})

-- Per-hardware libinput override
koma.device({
    name = "wacom-one-by-wacom-s-pen",
    map_to_output = "eDP-1",
})

koma.appearance({
    border = {
        enabled = true,
        width = 2,
        active_color = { gradient = { "#58a6ff", "#7ee787" }, angle = 45 },
        inactive_color = "#30363d",
        urgent_color = "#f85149",
        agent_leased_color = "#d2a8ff", -- Visual badge when a workspace holds AgentExclusive lease
    },
    focus_ring = { enabled = false },
    corner_radius = 10,
    shadow = { enabled = true, softness = 16, spread = 4, offset = { x = 0, y = 4 }, color = "#00000088" },
})

```

## 3. Keybindings, Modal Submaps & Gestures API

### 3.1 Fast-Path Action Descriptors vs. Lua Coroutine Callbacks (`koma.bind`)

`koma.bind(chord, target, opts?)` supports two target types:

1. **Compiled Action Descriptors (`koma.act.*`)**: Pre-compiled into Rust `Action` enums during `init.lua` load. Pressing the key executes directly in Ring 0 (`koma-model` / `koma-seat`) in single-digit microseconds without waking the `Phodopus` VM.

2. **Lua Coroutine Functions (`function(ctx) ... end`)**: Spawned on the `Phodopus` coroutine executor when dynamic branching, state inspection, or multi-step macro orchestration is desired.

```
---@type BindHandle
local term_bind = koma.bind("Mod + Return", koma.act.spawn({ "ghostty" }), {
    desc = "Launch Ghostty terminal",
    cooldown_ms = 150,
})

-- Built-in window, column, workspace, and Agent Deck/Stash actions
koma.bind("Mod + Q", koma.act.window.close(), { desc = "Close focused window" })
koma.bind("Mod + F", koma.act.window.fullscreen_toggle(), { desc = "Toggle fullscreen" })
koma.bind("Mod + V", koma.act.window.float_toggle(), { desc = "Toggle floating state" })
koma.bind("Mod + H", koma.act.focus.left(), { desc = "Focus column/window left" })
koma.bind("Mod + L", koma.act.focus.right(), { desc = "Focus column/window right" })
koma.bind("Mod + BracketLeft",  koma.act.deck.cycle_prev(), { desc = "Pop previous window from Stash to Deck" })
koma.bind("Mod + BracketRight", koma.act.deck.cycle_next(), { desc = "Cycle active Deck window into Stash" })
koma.bind("Mod + Tab", koma.act.overview.toggle(), { desc = "Toggle koma-overview workspace grid" })

-- Interactive pointer grabs (move / resize) and scroll triggers
koma.bind("Mod + MouseLeft",  koma.act.window.drag_move(),   { desc = "Interactive window move grab" })
koma.bind("Mod + MouseRight", koma.act.window.drag_resize(), { desc = "Interactive window resize grab" })
koma.bind("Mod + WheelDown",  koma.act.workspace.focus_next(), { cooldown_ms = 80 })
koma.bind("Mod + WheelUp",    koma.act.workspace.focus_prev(), { cooldown_ms = 80 })

-- Hardware media & backlight keys active even during ext-session-lock-v1
koma.bind("XF86AudioRaiseVolume", koma.act.spawn({ "wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "5%+" }), {
    allow_when_locked = true,
    repeat_key = true,
})
koma.bind("XF86MonBrightnessUp", koma.act.spawn({ "brightnessctl", "set", "5%+" }), {
    allow_when_locked = true,
    repeat_key = true,
})

```

### 3.2 Complete `BindOptions` Schema

| Field | Type | Default | Semantics | 
| ----- | ----- | ----- | ----- | 
| `edge` | `"press" | "release" | "both"` | `"press"` | Trigger edge; `"both"` accepts `{ press = ..., release = ... }` as the target table. | 
| `repeat_key` | `boolean` | `false` | Re-fires on XKB key repeat when held down. | 
| `cooldown_ms` | `integer?` | `nil` | Minimum interval between activations (ideal for scroll wheel and screenshot binds). | 
| `allow_when_locked` | `boolean` | `false` | Permits execution while `ext-session-lock-v1` is active (restricted to `koma.act.*` audio/brightness/DPMS actions; arbitrary Lua callbacks are blocked while locked). | 
| `allow_inhibiting` | `boolean` | `true` | If `false`, bypasses client `keyboard-shortcuts-inhibit` requests (e.g., escape hatches out of VMs or remote desktops). | 
| `pass_through` | `boolean` | `false` | Forwards the raw key event to the focused Wayland client in addition to running the compositor action. | 
| `when_preempted` | `"shield" | "allow"` | `"shield"` | Under `Peek Read-Only` viewing of an `AgentExclusive` workspace, `"shield"` blocks mutating window binds until the human presses `Mod + G`. | 
| `desc` | `string?` | `nil` | Human-readable label shown in the hotkey overlay UI and `komactl binds --json`. | 

### 3.3 Modal Key-Tables (`koma.mode`) & Multi-Touch Gestures (`koma.gesture`)

```
-- Modal key-table (submap) with automatic status-bar event broadcast
koma.mode("resize", {
    on_enter = function() koma.notify("Entered Resize Mode (Esc to exit)") end,
    binds = {
        { "H", koma.act.window.resize({ width = -40, height = 0 }), { repeat_key = true } },
        { "L", koma.act.window.resize({ width =  40, height = 0 }), { repeat_key = true } },
        { "K", koma.act.window.resize({ width = 0, height = -40 }), { repeat_key = true } },
        { "J", koma.act.window.resize({ width = 0, height =  40 }), { repeat_key = true } },
        { "Escape", koma.act.mode.exit() },
        { "Return", koma.act.mode.exit() },
    },
})
koma.bind("Mod + R", koma.act.mode.enter("resize"), { desc = "Enter modal resize submap" })

-- Multi-finger trackpad gestures with continuous 1:1 progress tracking
koma.gesture({
    fingers = 3,
    direction = "horizontal", -- "horizontal" | "vertical" | "left" | "right" | "up" | "down" | "pinch_in" | "pinch_out"
    action = koma.act.scroll_strip.swipe(),
})
koma.gesture({
    fingers = 4,
    direction = "up",
    action = koma.act.overview.open(),
})

```

## 4. Declarative Window & Layer Rules Engine

### 4.1 Two-Phase Window Rules (`koma.rule.window`)

Following `Niri`'s `unmapped.rs -> mapped.rs` lifecycle, `koma.rule.window(spec)` evaluates rules in declaration order and merges matching fields (`last-writer-wins` per property).

* **`matches`**: List of `WindowMatchSpec` tables combined via **logical OR** (a window matches the rule if at least one `MatchSpec` matches; all specified fields inside a single `MatchSpec` must match via **logical AND**).

* **`excludes`**: List of `WindowMatchSpec` tables combined via **logical NOR** (if any `exclude` table matches, the rule is skipped).

#### `WindowMatchSpec` Predicates

| Field | Type | Phase Availability | Description | 
| ----- | ----- | ----- | ----- | 
| `app_id` | `string` (Rust regex) | Initial + Dynamic | Matches Wayland `xdg_toplevel.app_id` or `xwayland-satellite` WM_CLASS. | 
| `title` | `string` (Rust regex) | Initial + Dynamic | Matches current window title. | 
| `tag` | `string` (Rust regex) | Initial + Dynamic | Matches user/agent runtime tags (`komactl win tag`) or `xdg-toplevel-tag-v1`. | 
| `workspace` | `string` | Initial + Dynamic | Workspace name (`"agent:office"`) or smart count selector (`"w[1]"` single tiled window). | 
| `is_floating` | `boolean` | Dynamic | Matches current floating vs. tiled/deck state. | 
| `is_focused` | `boolean` | Dynamic | True when holding active seat focus on its workspace. | 
| `is_urgent` | `boolean` | Dynamic | True when marked urgent via [`xdg-activation-v1`](https://wayland.app/protocols/xdg-activation-v1). | 
| `is_modal_dialog` | `boolean` | Initial + Dynamic | True when attached via `xdg-dialog-v1` modal hint or transient parent size hint. | 
| `is_xwayland` | `boolean` | Initial + Dynamic | True for X11 windows bridged via [`xwayland-satellite`](https://github.com/Supreeeme/xwayland-satellite). | 
| `is_screencast_target` | `boolean` | Dynamic | True while actively captured via [`ext-image-copy-capture-v1`](https://wayland.app/protocols/ext-image-copy-capture-v1) or PipeWire. | 
| `is_agent_workspace` | `boolean` | Initial + Dynamic | True when the window resides on a workspace with `AgentExclusive` lease or headless mode. | 
| `at_startup` | `boolean` | Initial only | True during the first `5.0 s` after compositor boot. | 

#### Initial Configure vs. Dynamic Reactive Properties

```
-- 1. Privacy & Security Blackout Rule (Protected Surface Invariant)
koma.rule.window({
    name = "redact-credential-vaults",
    matches = {
        { app_id = "^(org\\.keepassxc\\.KeePassXC|bitwarden)$" },
        { app_id = "^polkit-gnome-authentication-agent-1$" },
        { title  = "(?i)(1password|secret|ssh passphrase|\\.env)" },
    },
    -- Replaces surface pixels with solid #000000 in Agent captures & screencasts,
    -- while keeping the window normally visible to the human on physical KMS scanout!
    block_out_from = "all", -- "agent_capture" | "screencast" | "screencopy" | "all"
})

-- 2. Agent Background Helper Rule (Silent Stash Placement)
koma.rule.window({
    name = "agent-office-dialogs",
    matches = {
        { app_id = "^(wps|et|wpp|libreoffice.*)$", is_agent_workspace = true },
    },
    initial = {
        open_mode = "deck_top",      -- "tile" | "float" | "fullscreen" | "maximized" | "deck_top" | "stash_background"
        open_focused = true,
    },
    suppress_events = { "maximize" }, -- Prevents legacy office suites from breaking canonical viewport dimensions
    corner_radius = 0,                -- Crisp unrounded corners for exact 9-anchor OCR & pixel coordinates
    clip_to_geometry = true,
})

-- 3. Picture-in-Picture Floating Anchor Rule (Niri-style RelativeTo positioning)
local pip_rule = koma.rule.window({
    name = "browser-pip",
    matches = {
        { app_id = "^(firefox|chromium)$", title = "^Picture-in-Picture$" },
    },
    initial = {
        open_mode = "float",
        open_focused = false,
        default_width = { fixed = 480 },
        default_height = { fixed = 270 },
        default_floating_pos = { x = 24, y = 24, anchor = "bottom-right" },
    },
    pin_on_output = true,
    opacity = 0.96,
})

-- 4. Highlight Screencast Targets Dynamically
koma.rule.window({
    name = "screencast-recording-border",
    matches = { { is_screencast_target = true } },
    border = { active_color = "#ff5555", inactive_color = "#ff5555", width = 3 },
})

-- 5. XWayland Empty-Class Drag Guard (ported from Hyprland's fix-xwayland-drags)
koma.rule.window({
    name = "xwayland-drag-artifact-guard",
    matches = {
        { app_id = "^$", title = "^$", is_xwayland = true, is_floating = true },
    },
    focusable = false,
})

```

### 4.2 Layer-Shell Rules (`koma.rule.layer`)

Controls `wlr-layer-shell` surfaces such as `waybar`, `swww`, `mako`, `fuzzel`, and `koma-overview`:

```
koma.rule.layer({
    name = "Redact-Notifications-From-Capture",
    matches = { { namespace = "^(mako|dunst|swaync-notification-window)$" } },
    block_out_from = "all",
    shadow = { enabled = true },
    corner_radius = 12,
})

koma.rule.layer({
    name = "Static-Wallpaper-In-Overview-Backdrop",
    matches = { { namespace = "^swww-daemon$", layer = "background" } },
    place_within_backdrop = true,
})

```

## 5. Timed Macro & Coroutine Automation API (`koma.macro`)

`koma.macro` turns shortcut-rich desktop applications—spreadsheets (WPS/Excel/Calc), word processors, 3D/animation suites (Blender), DAWs, and keyboard-driven games—into zero-token, sub-millisecond reusable skills callable by human hotkeys, `komactl`, `koma-mcp`, or [`gemini-decision-1`](https://aistudio.google.com/docs/models/gemini-decision-1) `choice` policies on the [`Gemini Decisions API`](https://aistudio.google.com/docs/decisions-api).

### 5.1 9-Anchor Window-Relative Coordinate Geometry (`AnchorPoint`)

Hardcoded screen coordinates break whenever a window resizes or moves. Every pointer or drag target in `koma.macro` resolves against the **focused target window's logical content geometry** using one of three forms:

1. **9-Anchor Edge Offset**: `{ anchor = "top-left" | "top" | "top-right" | "left" | "center" | "right" | "bottom-left" | "bottom" | "bottom-right", x = dx, y = dy }` (where `dx, dy` are inward or signed logical pixels from that anchor—preserving toolbar, sidebar, and status-bar alignment across arbitrary window widths).

2. **Normalized Proportional Point**: `{ u = 0.5, v = 0.25 }` (`0.0..1.0` across window width and height).

3. **225-Cell Decision Grid Label**: `{ grid_225 = "G8" }` (maps directly to the `15x15` [`warpd`](https://github.com/rvaiya/warpd)-style overlay grid used by `gemini-decision-1`).

### 5.2 `MacroContext` (`ctx`) Coroutine Primitives

Every `ctx:*` method verifies the caller's `WorkspaceLease` `Epoch` before and after any `HostOpHandle` suspension. If the human presses `Mod + G` mid-macro, `koma` cancels the suspended `Phodopus` coroutine immediately and releases any held virtual keys or mouse buttons within `1 ms`.

| Method Signature | Host Yield (`PendingHostOp`) | Behavior & Protocol Plumbing | 
| ----- | ----- | ----- | 
| `ctx:assert_app(regex)` | Synchronous | Aborts with `ERR_PRECONDITION` if the focused window's `app_id` does not match `regex`. | 
| `ctx:key(chord, opts?)` | Optional (`hold_ms` / `after_ms`) | Taps a key or modifier chord (`"Ctrl+Shift+L"`, `"Tab"`, `"F2"`). `opts`: `{ hold_ms = 15, after_ms = 20 }`. | 
| `ctx:sequence(chords, gap_ms)` | `SleepTimer` between steps | Dispatches sequential ribbon/modal mnemonics (e.g., `{ "Alt+H", "A", "C" }` in Excel/WPS) with exact cadence. | 
| `ctx:key_down(key)` / `ctx:key_up(key)` | Synchronous | Holds or releases a modifier/key; tracked in `vSeat`'s shadow ledger for automatic cleanup on abort. | 
| `ctx:move_to(pos, kinematics?)` | `PointerTrajectory` | Moves `vSeat` pointer using `"instant"`, `"minimum_jerk"`, `"spring"`, or custom `fn(t) -> (x, y)` closure. | 
| `ctx:click(pos, opts?)` | `PointerTrajectory` + `SleepTimer` | Moves to `pos` and clicks (`button = "left" | "right" | "middle"`, `clicks = 1 | 2 | 3`, `hold_ms = 25`). | 
| `ctx:drag(spec)` | `PointerTrajectory` + `SleepTimer` | Executes press -> `hold_before_move_ms` -> smooth trajectory (`from` -> `to`) -> `hold_before_release_ms` -> release (essential for ruler sliders, timeline scrubbing, and gizmo drags). | 
| `ctx:scroll(spec)` | `SleepTimer` | Emits discrete wheel clicks or smooth `wl_pointer.axis_v120` scroll (`dx`, `dy`, `steps`, `step_ms`). | 
| `ctx:text(utf8_str, opts?)` | `SleepTimer` / Settle | **3-Tier Zero-IME Injection**: (1) [`text-input-unstable-v3`](https://wayland.app/protocols/text-input-unstable-v3) `commit_string` -> (2) isolated `vSeat` clipboard paste -> (3) [`wtype`](https://github.com/atx/wtype)-style ephemeral XKB keymap. Never triggers Fcitx5/IBus candidate popups. | 
| `ctx:paste_mime(mime, data)` | `WaitDamageSettle` | Writes structured `text/tab-separated-values` (multi-cell spreadsheet grids) or `text/html` into `vSeat`'s isolated `wl_data_device` and triggers paste without touching human `seat0` clipboard. | 
| `ctx:sleep_ms(duration_ms)` | `SleepTimer` | Suspends coroutine on a `calloop` monotonic timer without blocking compositor frames. | 
| `ctx:wait_settle(opts?)` | `WaitDamageSettle` | Suspends until target window `wl_surface.damage` stays quiet for `quiet_ms` (default `40 ms`, capped by `timeout_ms = 500 ms`). | 

### 5.3 Defining Parameterized Macros (`koma.macro.define`)

Declaring a `params` schema allows `koma-mcp` to automatically expose the macro as a typed MCP tool and allows `gemini-decision-1` to invoke pre-validated macro banks without generating raw coordinates or burning LLM output tokens:

```
-- Example 1: Zero-Token WPS / Excel Table Ingestion & Ribbon Formatting Macro
koma.macro.define({
    id = "wps.insert_styled_table",
    app_id = "^(et|wps|libreoffice-calc)$",
    description = "Pastes a TSV grid at the active cell, bolds the header row, and auto-fits column widths",
    params = {
        tsv_data   = { type = "string", required = true },
        col_count  = { type = "int", min = 1, max = 64, default = 4 },
        row_height = { type = "int", min = 12, max = 72, default = 24 },
    },
    limits = { fuel = 120000, memory_bytes = 4 * 1024 * 1024, timeout_ms = 2500 },

    run = function(ctx, args)
        ctx:assert_app("^(et|wps|libreoffice-calc)$")

        -- 1. Inject multi-row/column TSV directly via isolated vSeat MIME clipboard
        ctx:paste_mime("text/tab-separated-values", args.tsv_data)
        ctx:wait_settle({ quiet_ms = 45, timeout_ms = 400 })

        -- 2. Return to top-left of pasted block, select header row, and apply Bold + Center
        ctx:key("Ctrl+Home", { after_ms = 20 })
        ctx:key_down("Shift")
        for _ = 1, (args.col_count - 1) do
            ctx:key("Right", { after_ms = 10 })
        end
        ctx:key_up("Shift")
        ctx:key("Ctrl+B", { after_ms = 15 })
        ctx:sequence({ "Alt+H", "A", "C" }, 35) -- Ribbon mnemonic: Home -> Align Center
        ctx:wait_settle({ quiet_ms = 35, timeout_ms = 300 })

        -- 3. Auto-fit columns via ribbon shortcut sequence (Home -> Format -> AutoFit Column Width)
        ctx:key("Ctrl+A", { after_ms = 20 })
        ctx:sequence({ "Alt+H", "O", "I" }, 40)

        -- 4. Open Row Height dialog, inject exact numeric value bypassing IME, and confirm
        ctx:sequence({ "Alt+H", "O", "H" }, 40)
        ctx:wait_settle({ quiet_ms = 40, timeout_ms = 300 })
        ctx:text(tostring(args.row_height), { strategy = "auto" })
        ctx:key("Return")
        ctx:wait_settle({ quiet_ms = 50, timeout_ms = 400 })
    end,
})

-- Example 2: WPS Writer First-Line Indent Ruler Drag (Long-Press Smooth Drag)
koma.macro.define({
    id = "wps.drag_first_line_indent",
    app_id = "^(wps|libreoffice-writer)$",
    description = "Drags the horizontal ruler first-line indent marker by delta_px",
    params = {
        ruler_x  = { type = "int", default = 242 },
        ruler_y  = { type = "int", default = 148 },
        delta_px = { type = "int", min = -200, max = 400, default = 64 },
    },
    run = function(ctx, args)
        ctx:drag({
            button = "left",
            from = { anchor = "top-left", x = args.ruler_x, y = args.ruler_y },
            to   = { anchor = "top-left", x = args.ruler_x + args.delta_px, y = args.ruler_y },
            hold_before_move_ms = 70,  -- Ensures ruler thumb grab engages before motion starts
            kinematics = { profile = "minimum_jerk", duration_ms = 140, arc_curvature = 0.0 },
            hold_before_release_ms = 35,
        })
        ctx:wait_settle({ quiet_ms = 40, timeout_ms = 300 })
    end,
})

-- Example 3: Blender Modal Extrude & Bevel Macro (Pure Keyboard + Numeric Input)
koma.macro.define({
    id = "blender.extrude_z_and_bevel",
    app_id = "^blender$",
    description = "Extrudes selected faces along Z and applies a multi-segment bevel in Edit Mode",
    params = {
        distance = { type = "float", default = 1.25 },
        bevel_width = { type = "float", default = 0.08 },
        segments = { type = "int", min = 1, max = 16, default = 4 },
    },
    run = function(ctx, args)
        -- Ensure viewport pointer focus lies inside central 3D View before modal hotkeys
        ctx:move_to({ anchor = "center", x = 0, y = 0 }, { profile = "instant" })
        ctx:key("E", { after_ms = 20 })
        ctx:key("Z", { after_ms = 15 })
        ctx:text(string.format("%.4f", args.distance), { strategy = "xkb_keymap" })
        ctx:key("Return", { after_ms = 25 })

        ctx:key("Ctrl+B", { after_ms = 20 })
        ctx:text(string.format("%.4f", args.bevel_width), { strategy = "xkb_keymap" })
        ctx:scroll({ dy = args.segments - 1, steps = args.segments - 1, step_ms = 18 })
        ctx:key("Return")
        ctx:wait_settle({ quiet_ms = 35, timeout_ms = 250 })
    end,
})

```

### 5.4 Human Demonstration Recording (`komactl macro record`)

Users can record repetitive workflows interactively without writing coordinates by hand:

1. Run `komactl macro record --output ~/.config/koma/lua/macros/recorded_task.lua` (or press `Mod + Shift + M`).

2. `koma-seat` attaches a non-intrusive tap onto `seat0` scoped to the focused window:

   * Consecutive pointer motion samples during drags are denoised via Ramer-Douglas-Peucker simplification and fitted to `minimum_jerk` duration parameters;

   * Click and drag endpoints automatically snap to the nearest of the **9 window anchors** (e.g., clicks within the right `25%` and top `15%` emit `anchor = "top-right"`);

   * Pauses exceeding `120 ms` directly following surface damage automatically compile into `ctx:wait_settle({ quiet_ms = 45, timeout_ms = 400 })` rather than brittle wall-clock sleeps;

   * Typed character bursts coalesce into a single `ctx:text("...")` call.

3. Pressing `Mod + Shift + M` again writes clean, human-editable Lua 5.4 code ready to bind to a key (`koma.act.macro.run("...")`) or expose to an agent.

## 6. Lifecycle Hooks & Complete `~/.config/koma/init.lua` Reference

### 6.1 Compositor Event Hooks (`koma.on`)

`koma.on(event_name, callback)` registers lightweight event listeners executed inside `Phodopus`:

* `"compositor.start"`: Fired once when Wayland socket & D-Bus environment are ready (ideal for starting `waybar`, `swww-daemon`, `fcitx5 -d`, `koma-overview --daemon`).

* `"monitor.added"` / `"monitor.removed"`: Hotplug callbacks receiving `{ name, make, model, serial }`.

* `"lease.preempted"`: Fired when the human presses `Mod + G` (`{ ws_name, previous_holder, new_epoch }`).

* `"window.opened"` / `"window.closed"`: Receives immutable window metadata `{ win_id, app_id, title, ws_name }`.

### 6.2 Minimal Production `~/.config/koma/init.lua`

```
---@diagnostic disable: undefined-global
-- Generate IDE autocomplete stubs via: komactl gen-types

-- 1. Modular user imports jailed under ~/.config/koma/lua/
-- require("macros.wps")
-- require("macros.blender")

-- 2. Session Environment & Autostart Daemons
koma.env("XCURSOR_SIZE", "24")
koma.env("QT_QPA_PLATFORM", "wayland;xcb")

koma.on("compositor.start", function(ctx)
    ctx:spawn({ "swww-daemon" })
    ctx:spawn({ "waybar" })
    ctx:spawn({ "fcitx5", "-d" })
    ctx:spawn({ "koma-overview", "--daemon" })
end)

-- 3. Physical Monitor & Symmetrical Workspaces
koma.monitor({
    output = "eDP-1",
    mode = "2560x1600@240.000",
    scale = 1.6,
    vrr = "on_demand",
    focus_at_startup = true,
})

for i = 1, 5 do
    koma.workspace({
        name = tostring(i),
        presentation = "headed",
        preferred_output = "eDP-1",
        layout = "scrolling",
    })
end

koma.workspace({
    name = "agent:work",
    presentation = "headless",
    viewport = { width = 1920, height = 1080, scale = 1.0 },
    layout = "deck",
})

-- 4. Input & Appearance
koma.input({
    mod_key = "Super",
    touchpad = { tap_to_click = true, natural_scroll = true },
    tablet = { map_to_output = "eDP-1" },
})

koma.appearance({
    corner_radius = 10,
    border = { enabled = true, width = 2, active_color = "#58a6ff", inactive_color = "#30363d" },
})

-- 5. Core Keybindings
koma.bind("Mod + Return", koma.act.spawn({ "ghostty" }), { desc = "Open terminal" })
koma.bind("Mod + D",      koma.act.spawn({ "fuzzel" }),  { desc = "Application launcher" })
koma.bind("Mod + Q",      koma.act.window.close(),       { desc = "Close active window" })
koma.bind("Mod + Tab",    koma.act.overview.toggle(),    { desc = "Toggle workspace overview" })

for i = 1, 5 do
    local ws = tostring(i)
    koma.bind("Mod + " .. ws,         koma.act.workspace.focus(ws))
    koma.bind("Mod + Shift + " .. ws, koma.act.window.move_to_workspace(ws))
end

-- Toggle peek view onto the background Agent workspace (Mod + G takes over write control)
koma.bind("Mod + A", koma.act.workspace.peek("agent:work"), {
    desc = "Peek at agent:work in Read-Only Shield mode",
})

-- Bind a parameterized macro directly to a human shortcut
koma.bind("Ctrl + Alt + H", koma.act.macro.run("wps.drag_first_line_indent", { delta_px = 64 }), {
    desc = "Indent paragraph first line in WPS Writer",
})

-- 6. Baseline Window Rules
koma.rule.window({
    name = "protect-password-managers",
    matches = { { app_id = "^(org\\.keepassxc\\.KeePassXC|bitwarden)$" } },
    block_out_from = "all",
})

```


---

## 7. v0.2 Layout, Tabbed Column, Pointer-Grab & Gesture Extensions

### 7.1 `koma.dwindle({ ... })` (Default `Headed` Layout)

```lua
koma.dwindle({
    force_split = 0,               -- 0 = follow aspect ratio, 1 = left/top, 2 = right/bottom
    preserve_split = true,         -- Keep split axis stable across window removals
    smart_split = true,            -- 4-quadrant diagonal cursor split & drag drop-zones
    use_active_for_splits = false, -- Split hovered tile by default (Hyprland parity)
    default_split_ratio = 1.0,     -- 1.0 = 50/50 split (range 0.1..1.9)
    smart_resizing = true,         -- Resize outward toward nearest dragged corner
    pseudotile = true,             -- Enable Mod + P client-size centering inside tile
    inner_gap = 6,
    outer_gap = 10,
})
```

### 7.2 `koma.scrolling({ ... })` (Multi-Tile Stacks & `ColumnDisplay::Tabbed` + `tab_indicator`)

```lua
koma.scrolling({
    preset_column_widths = { 1 / 3, 0.5, 2 / 3 },
    preset_window_heights = { 1 / 3, 0.5, 2 / 3 },
    default_column_width = 0.5,
    default_column_display = "normal", -- "normal" (vertical split) | "tabbed"
    center_focused_column = "never",   -- "never" | "on_overflow" | "always"
    always_center_single_column = false,
    camera_damping_ratio = 1.0,
    camera_stiffness = 800.0,
    swipe_working_area_movement = 1200.0,
    inner_gap = 8,
    outer_gap = 10,
    tab_indicator = {
        enabled = true,
        hide_when_single_tab = true,
        place_within_column = false,
        position = "left",             -- "left" | "right" | "top" | "bottom"
        width = 4.0,
        gap = 4.0,
        gaps_between_tabs = 4.0,
        length_proportion = 0.5,
        corner_radius = 2.0,
    },
    edge_auto_scroll = {
        enabled = true,
        trigger_width = 30.0,
        delay_ms = 100,
        max_speed = 1500.0,
    },
})
```

Key `koma.act.scrolling.*` actions:
* `koma.act.scrolling.toggle_column_tabbed_display()` (`Mod + W` default) — Toggles focused column between `Normal` vertical split and `Tabbed` stack with clickable side `tab-indicator` pills.
* `koma.act.scrolling.consume_or_expel_window_left()` / `consume_or_expel_window_right()` (`Mod + [` / `Mod + ]`).
* `koma.act.scrolling.consume_window_into_column()` / `expel_window_from_column()` (`Mod + ,` / `Mod + .`).
* `koma.act.scrolling.switch_preset_column_width()` / `switch_preset_window_height()` / `reset_window_height()`.

### 7.3 Pointer Buttons, Discrete Wheel/Touchpad Ticks & Multi-Finger `koma.gesture`

```lua
-- Interactive tile/float move & split-ratio resize grabs (opposite mouse button mid-drag toggles float)
koma.bind("Mod + MouseLeft",  koma.act.window.drag_move())
koma.bind("Mod + MouseRight", koma.act.window.drag_resize())

-- Discrete WheelScroll* (v120 = 120) & TouchpadScroll* (10 px tick) bindings with cooldown
koma.bind("Mod + WheelScrollDown",  koma.act.workspace.focus_next(), { cooldown_ms = 150 })
koma.bind("Mod + WheelScrollUp",    koma.act.workspace.focus_prev(), { cooldown_ms = 150 })

-- Multi-finger touchpad gestures (unclaimed 2-finger pinch/hold pass through via zwp_pointer_gestures_v1)
koma.gesture({
    fingers = 3,
    direction = "horizontal",
    action = koma.act.scrolling.swipe(), -- 1:1 pixel tracking + 0.997 kinetic velocity snap
})
koma.gesture({
    fingers = 4,
    direction = "up",
    action = koma.act.overview.toggle(),
})
```
