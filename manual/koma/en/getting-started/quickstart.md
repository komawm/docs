# Getting Started & Keybindings

> [!TIP]
> Koma ships a complete Hyprland-compatible default keybinding table (`inherit_default_binds = true` by default). You can launch Koma with **no `~/.config/koma/init.lua`** and immediately open terminals, tile or float windows, switch workspaces, and reload config.

![Koma default dwindle tiling workspace](https://cdn.komawm.org/media/koma-dwindle.webp)

## Launch Modes (`koma [OPTIONS]`)

Koma parses CLI options before opening any display, seat, or DRM device:

| Flag | Backend / Behavior | Typical Use Case |
| :--- | :--- | :--- |
| `koma --winit` | Nested Wayland/X11 window | Testing config changes safely inside Hyprland, Sway, or GNOME |
| `koma --tty` | Direct bare-metal Linux VT via `libseat` (`seatd`/`logind`), `udev`, `DRM/KMS`, `libinput` | Standalone TTY launch or isolated QEMU/KVM `virtio-vga` smoke tests |
| `koma --session` | Login session mode (`koma-session`, `greetd`, `systemd --user`) | Imports `WAYLAND_DISPLAY`, `DISPLAY`, `XDG_CURRENT_DESKTOP=koma`, `XDG_SESSION_TYPE=wayland`, `KOMA_INSTANCE_SIGNATURE` into `systemd --user` & D-Bus, then signals `$NOTIFY_SOCKET`/`$NOTIFY_FD` `READY=1` |
| `koma --headless-check` | CLI & state-machine self-check | CI, packaging, and post-install sanity verification |
| `--spawn <CMD>` | Spawns `<CMD>` once the compositor socket is ready | e.g. `koma --winit --spawn foot` or `koma --tty --spawn bitty` |
| `-c, --config <PATH>` | Overrides `$XDG_CONFIG_HOME/koma/init.lua` | Testing alternate Lua configs |
| `koma init <bash\|zsh\|fish\|nushell>` | Prints shell-native exports for the live instance: `WAYLAND_DISPLAY`, `KOMA_INSTANCE_SIGNATURE`, `XDG_RUNTIME_DIR`, `DISPLAY` (only while XWayland is up), `XDG_SESSION_TYPE`, and `XDG_CURRENT_DESKTOP` | Running `komactl` from an external terminal (`koma init fish \| source`) |
| `koma completions <bash\|zsh\|fish>` | Prints the completion script rendered from the binary's own command table | Manual shell completion setup |
| `koma mcp [--print-tools]` | Runs the stdio MCP server against `koma-agent.sock`; there is no separate `koma-mcp` binary | Registering Koma in an MCP desktop host |

`koma init` never prints capability tokens. It fails with a clear message when no live instance exists or when several are live, in which case set `KOMA_INSTANCE_SIGNATURE` to the instance you want; `--unset` prints the inverse assignments.

> [!NOTE]
> When invoked with no backend flag, Koma selects `--winit` if `WAYLAND_DISPLAY` or `DISPLAY` is set (except under `--session`, which targets the physical seat), otherwise `--tty`. Signals `SIGTERM`, `SIGINT`, and `SIGHUP` perform a clean teardown (exit `0`) and unlink runtime sockets.

## Built-In Default Keymap (`Mod` = `Super` on TTY / `Alt` when nested under `--winit`)

| Chord | Action | Description |
| :--- | :--- | :--- |
| `Mod + Return` | `spawn({ "bitty" })` | Launch the default terminal (Bitty), falling back to `foot` |
| `Mod + Q` | `window.close()` | Close focused window |
| `Mod + V` | `window.float_toggle()` | Toggle floating state |
| `Mod + F` | `window.fullscreen_toggle()` | Toggle fullscreen (whole monitor, gaps included) |
| `Mod + M` | `window.maximize_toggle()` | Toggle maximize (work area minus gaps; the bar stays visible) |
| `Mod + P` | `window.pseudotile_toggle()` | Toggle dwindle pseudotile |
| `Mod + E` | `dwindle.toggle_split()` | Toggle horizontal/vertical dwindle split |
| `Mod + H / J / K / L` | `focus.left/down/up/right()` | Move focus directionally |
| `Mod + Shift + H / J / K / L` | `window.move_direction(...)` | Move/swap window directionally |
| `Mod + 1..9` | `workspace.focus("1".."9")` | Switch to workspace `1`–`9` |
| `Mod + Shift + 1..9` | `window.move_to_workspace("1".."9")` | Move focused window to workspace `1`–`9` and follow it |
| `Mod + R` / `Mod + Ctrl + R` | `scrolling.switch_preset_column_width()` | Cycle scrolling column width forward / backward |
| `Mod + Ctrl + Shift + R` | `scrolling.switch_preset_window_height()` | Cycle scrolling window height preset |
| `Mod + C` | `scrolling.center_column()` | Center active scrolling column |
| `Mod + Shift + M` | `scrolling.maximize_column()` | Maximize active scrolling column |
| `Mod + W` | `scrolling.toggle_column_tabbed_display()` | Toggle tabbed display inside scrolling column |
| `Mod + Comma` / `Mod + Period` | `scrolling.consume_window_into_column()` / `expel_window_from_column()` | Consume into or expel from column |
| `Mod + BracketLeft` / `BracketRight` | `scrolling.consume_or_expel_window_left/right()` | Consume/expel left or right |
| `Mod + S` / `Mod + Shift + S` | `scratchpad.toggle()` / `move_window()` | Toggle or move window to scratchpad |
| `Mod + Tab` | `overview.toggle()` | Toggle `koma-overview` spatial workspace switcher |
| `Mod + Shift + Slash` | `overlay.keybinds_toggle()` | Compositor-rendered keybind overview; `Escape`, the same chord, or a click dismisses it |
| `Mod + MouseLeft` / `MouseRight` | `window.drag_move()` / `drag_resize()` | Drag-move or drag-resize window |
| `Mod + WheelScrollDown / Up` | `workspace.focus_next()` / `focus_prev()` | Cycle workspaces (`150 ms` cooldown) |
| `Mod + WheelScrollLeft / Right` | `deck.cycle_prev()` / `cycle_next()` | Cycle Deck/Stash stack (`150 ms` cooldown) |
| `Mod + Shift + R` | `koma.act.reload_config()` | Hot-reload `init.lua` |
| `Mod + Shift + E` | `koma.act.quit()` | Exit Koma cleanly |
| `Mod + G` (Preemption Barrier) | Instant Human Preemption | Immediately revokes active agent leases (`< 1 ms`, `4091 ERR_HUMAN_PREEMPTED`) |

## Fullscreen vs. Maximize (`Mod + F` / `Mod + M`)

- **Fullscreen (`Mod + F`, `koma.act.window.fullscreen_toggle()`)** covers the whole monitor, gaps included. While it is active, `Top` and `Overlay` layer surfaces (status bars, launchers) are not composited; they stay mapped and appear again immediately when fullscreen ends. Other windows on the workspace are hidden. The fullscreen window itself paints no border, focus ring or shadow; maximize keeps them, because neighbours and the bar remain.
- **Maximize (`Mod + M`, `koma.act.window.maximize_toggle()`)** fills the work area minus gaps and exclusive zones, so the bar stays visible.
- The two states are mutually exclusive: entering one leaves the other. `Mod + Shift + M` is the separate Scrolling action `koma.act.scrolling.maximize_column()` and does not toggle window maximize.

## Interactive Resize (frame edges)

Dragging a window border or corner resizes it with no modifier. The pointer switches to the matching `W`/`E`/`N`/`S`/`NW`/`NE`/`SW`/`SE` shape over that edge. `Mod + right-drag` (`window.drag_resize()`) still works.

Deck refuses an edge drag on a tiled window because the active window always fills the viewport; the log message tells you to float the window first, and a floating Deck window does resize.

## Moving Windows Between Workspaces

`Mod + Shift + 1..9` and `koma.act.window.move_to_workspace(ws)` move the focused window and follow it to the destination workspace. Use `koma.act.window.move_to_workspace(ws, { follow = false })` for the `movetoworkspacesilent` equivalent that leaves focus where it is.

## Workspace Overview & Kill-Switch (`Mod + Tab` / `Mod + G`)

- **Spatial Overview (`koma-overview`)**: Bound to `Mod + Tab` by default (you can also bind `koma.bind("Mod + O", koma.act.overview.toggle())` in `init.lua`). Renders an interactive `wlr-layer-shell` spatial grid of active workspaces and windows via `koma-admin.sock` (`scene.inventory`).
- **Human Preemption (`Mod + G`)**: Pressing `Mod + G` or generating physical keyboard/pointer activity raises the preemption barrier on agent-leased workspaces so automation cannot fight your cursor.

## Legacy X11 Apps via `xwayland-satellite`

Koma does not embed `Xwayland` directly inside the compositor. Instead, configure rootless [`xwayland-satellite`](https://github.com/Supreeeme/xwayland-satellite) in `~/.config/koma/init.lua`:

```lua
koma.xwayland({
    enabled = true,
    -- path = "/usr/bin/xwayland-satellite", -- optional explicit path
    isolate_agent_workspaces = true,        -- keep X11 isolated from agent workspaces
})
```
