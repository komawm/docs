# Panels, Portals, IME & Apps

Koma implements core Wayland protocols for panels, lockscreens, portals, remote desktop, and input methods, while marking `wp_security_context_manager_v1` and `komactl sandbox` sockets as restricted so jailed clients cannot access privileged globals.

## Shell, Surface & Output Protocols

| Protocol / Global | Purpose & Client Ecosystem | Security / Sandbox Rule |
| :--- | :--- | :--- |
| `xdg_shell` (`xdg_wm_base`) | Desktop toplevels, popups, fullscreen, SSD negotiation (`zxdg_decoration_manager_v1`) | Jailed clients stay confined to their `Headless` workspace |
| `zwlr_layer_shell_v1` | Bars (`waybar`, `ironbar`, `quickshell`), notifications (`swaync`), launchers (`fuzzel`/`rofi`), `koma-overview` | Exclusive zones, `get_popup` -> `xdg_popup` unconstraining & grabs; filtered out for sandboxed clients |
| `ext_session_lock_v1` | Fail-closed lockscreens (`swaylock`, `hyprlock`) | Masks rendered frames, blocks `grim` screencopy (`failed`), defers `xdg-activation` |
| `zwlr_output_manager_v1` | Dynamic multi-monitor inspection, `test`, and `apply` (`kanshi`, `wdisplays`) | Restricted from sandboxed/jailed clients |
| `zwlr_output_power_manager_v1` & `zwlr_gamma_control_manager_v1` | DPMS sleep/wake (`wlopm`) and night-light / color ramps (`wlsunset`, `gammastep`) | Filtered out for restricted clients |
| `wp_fractional_scale_manager_v1` & `wp_viewporter` | Sharp fractional HiDPI scaling (`1.25`, `1.5`, `1.6`, `"auto"`) | Per-output scale delivery |
| `wp_single_pixel_buffer_v1`, `wp_presentation` & `wl_shm` formats | Solid widget surfaces (`ironbar`/`quickshell`), scanout frame timing, `Abgr8888`/`Xbgr8888` buffers (`Waydroid`) | Exposed to graphical clients |
| `xdg_activation_v1` & `xdg_toplevel_icon_v1` | Cross-client focus tokens (`10 s` TTL) and validated window icons | Jail-scoped token validation & lock-screen deferral |
| `zwlr_foreign_toplevel_manager_v1` & `ext_foreign_toplevel_list_v1` | Taskbar / panel window list & activate/minimize/close controls | Filtered from restricted clients & guarded during session lock |
| `zwlr_virtual_pointer_manager_v1` & `zwp_keyboard_shortcuts_inhibit_manager_v1` | Remote desktop pointer injection and shortcut pass-through (`RustDesk`) | Restricted from jailed clients; `Mod + G` preemption and VT switches remain un-inhibitable |

## Workspace Model (`ext-workspace-v1`) & Waybar

Koma advertises [`ext-workspace-v1`](https://wayland.app/protocols/ext-workspace-v1) (staging) as `ext_workspace_manager_v1` to unrestricted clients, so a status bar can list, follow and switch workspaces natively instead of polling a runtime file. Jailed and `wp_security_context_manager_v1` clients cannot bind it, exactly like `zwlr_layer_shell_v1`.

| What the bar receives | Koma value |
| :--- | :--- |
| Groups | Exactly one `ext_workspace_group_handle_v1`; it owns every output through `output_enter` / `output_leave` |
| Workspaces | One `ext_workspace_handle_v1` per workspace, including `special:` overlays |
| `id` | The Koma workspace id (`ws_01`) — a stable door id, not a strip number |
| `name` | The configured workspace name (`1`, `chat`, `special:magic`) |
| `coordinates` | Unique 1D index in strip order: numeric names first by value, then the named ones |
| `capabilities` | `activate` only |
| `state` | `active` while the workspace is displayed (assigned to an output, the open `special:` overlay, or `active_ws_id`); no state bits for an ordinary inactive workspace; `hidden` only for workspaces that have no on-screen representation at all (headless/`agent:` workspaces) |

Property events are delta-only and every batch ends with `done`, so cache what you received instead of re-deriving state from a single event. `workspace.activate` runs through the same switch path as `Mod + 1..0`, and it is ignored while the session is locked.

### Waybar `ext/workspaces`

```jsonc
// ~/.config/waybar/config.jsonc
"modules-center": ["ext/workspaces"],

"ext/workspaces": {
  "format": "{name} {icon}",
  "on-click": "activate",
  "ignore-hidden": true,
  "sort-by-name": true,
  "format-icons": {
    "active": "●",
    "default": "○"
  }
}
```

```css
/* ~/.config/waybar/style.css */
#workspaces button {
  padding: 0 6px;
  border-radius: 4px;
}
#workspaces button.active {
  background: #7aa2f7;
  color: #16161e;
}
#workspaces button.hidden {
  /* Only matches workspaces Koma deliberately leaves off-screen. */
  opacity: 0.55;
}
```

`ignore-hidden: true` is safe and preferred: the protocol defines `hidden` as "the workspace is not visible in its workspace group, and clients attempting to visualize the compositor workspace state should not display such workspaces", and Koma only sets it for workspaces with no on-screen representation. Ordinary inactive workspaces carry **no** state bits, so they stay clickable. `icon` / `format-icons` work (`active` and `default` are the keys this module matches, and workspace-name keys match too), but `urgent` never fires, because Koma has no window-urgency notion and therefore no urgent workspace. Keep `"sort-by-name": true`: `"sort-by-id": true` would order by the door id (`ws_01`, `ws_02`, …), which only looks right while ids happen to follow creation order. A bar wired with `"on-click-right": "close"` or `"deactivate"` simply does nothing — Koma advertises `activate` alone.

## Screencopy & `xdg-desktop-portal`

- **`zwlr_screencopy_manager_v1` (v3)**: Supports SHM and DMA-BUF capture (`grim`, `wayshot`, `slurp`). Emits a single `buffer` / `linux_dmabuf` event per frame and honors `block_out_from = "screencopy"` / `"all"` blackout masks plus `ext-session-lock-v1` fail-closed denial.
- **`xdg-desktop-portal` (`koma.portal`)**: Routes `ScreenCast`, `Screenshot`, and `GlobalShortcuts` / `Inhibit` interfaces via `xdg-desktop-portal-wlr` / `xdg-desktop-portal-gtk` compatible portal configuration installed with Koma packages.

## Input Method (IME) & Virtual Input

Koma natively implements the modern Wayland CJK/IME stack without X11 dependencies:

- **`zwp_text_input_manager_v3`** (`text-input-v3`) for GTK4, Qt6, Chromium/Electron (`--enable-wayland-ime`), and native Wayland terminals.
- **`zwp_input_method_manager_v2`** (`input-method-v2`) and **`zwp_virtual_keyboard_manager_v1`** for **`Fcitx5`** and **`IBus`** candidate popups and preedit composition.
- **`zwp_pointer_constraints_v1` & `zwp_relative_pointer_manager_v1`**: Pointer lock/confine and raw relative motion for games and 3D viewports (broken cleanly on `ext-session-lock` or focus change).
- **`wl_touch` & `wp_cursor_shape_manager_v1`**: Multi-touch gesture/surface routing and compositor-rendered cursor themes.

> [!TIP]
> **IME vs. Automated Text Injection**: Interactive typing uses `Fcitx5` / `IBus` over `text-input-v3` and `input-method-v2`, whereas automation over `koma-agent.sock` injects text directly via keymap, `text-input-v3`, or clipboard paste (`Ctrl+Shift+V`) so automated input never triggers interactive IME candidate popups.

## `wp_security_context_manager_v1` & Jailed Clients

Both Wayland-native `wp_security_context_manager_v1` (used by Flatpak / `bubblewrap`) and `komactl sandbox` mark client connections as restricted. Restricted connections cannot bind privileged globals (`zwlr_layer_shell_v1`, `zwlr_screencopy_manager_v1`, `zwlr_data_control_manager_v1`, `zwp_virtual_keyboard_manager_v1`, `ext_session_lock_manager_v1`, `zwlr_output_manager_v1`, or `wp_security_context_manager_v1` itself).
