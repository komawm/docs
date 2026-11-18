# komactl & Workspace Overview

`komactl` is Koma's administration CLI (`koma-admin.sock`) and offline Lua validator, while `koma-overview` provides a `wlr-layer-shell` spatial overview across all workspaces.

## `komactl` Command Reference

`komactl` discovers `$XDG_RUNTIME_DIR/koma/<signature>/koma-admin.sock` automatically (or via `KOMA_INSTANCE_SIGNATURE`).

| Command | Mode | Description |
| :--- | :--- | :--- |
| `komactl validate [path/to/init.lua]` | Offline | Evaluates `init.lua` in the isolated Lua sandbox, validates rule regexes & gestures, and prints resource counts |
| `komactl doctor [path/to/init.lua] [--json] [--strict]` | Offline | Runs every non-destructive configuration check grouped by area and reports `ok` / `warn` / `error` / `skip`; `error` never changes the exit code |
| `komactl keys [path/to/init.lua] [--json] [--grep <pattern>]` | Offline (live read-only when reachable) | Lists the effective keymap: built-in catalogue merged with `init.lua`, plus pointer binds and gestures; repeating rows carry `[repeat]` |
| `komactl reload [path/to/init.lua]` | IPC (`admin.sock`) | Sends `config.reload` and atomically swaps live compositor configuration |
| `komactl config-status` | IPC (`admin.sock`) + offline | Prints active config path, reload generation, last error if any (`config.status`), the effective `input.keyboard`, `input.pointer` and `input.touchpad` knobs, plus `template.{init_lua,present,installed_version,shipped_version,outdated,missing_files}` for the generated scaffold |
| `komactl init [dir] [--force]` | Offline | Scaffolds `init.lua`, `lua/{input,workspaces,appearance,window_rules,keybinds}.lua`, and `lua/macros/example.lua`; refuses to overwrite existing files unless `--force` is given |
| `komactl gen-types` | Offline | Emits deterministic `LuaCATS` stubs for `koma-types` (`types/koma.lua`) |
| `komactl inventory` | IPC (`admin.sock`) | Prints live monitors, workspaces, `Epoch` counters, Deck windows, and Stash slots (`scene.inventory`); exactly one workspace carries `"focused": true` |
| `komactl win move-to-workspace <ws_id\|name> [--follow]` | IPC (`admin.sock`) | Moves the active window of the focused workspace to an existing workspace (`win.move_to_workspace`); `--follow` switches to the destination, without it the source keeps focus |
| `komactl token mint [label]` | IPC (`admin.sock`) | Mints a scoped `CapabilityToken` (`ttl_secs = 28800`, `can_create_headless = true`, `max_owned_workspaces = 4`) |
| `komactl capture [ws_id] [out.rgba]` | IPC (`admin.sock`) | Captures a zero-copy `SCM_RIGHTS` sealed `memfd` frame with `grid_225` overlay (`ws_id` default `ws_01`) |
| `komactl sandbox <subcmd>` | Container + IPC | Runs `bwrap` or rootless `podman` GUI containers inside an isolated `Headless` workspace |
| `komactl -V` / `--version` | Offline | Prints `komactl <version>` |

## Generated Configuration (`komactl init`)

`komactl init` renders the shipped starter tree, either into the default config directory or into an explicit `[dir]`:

```text
init.lua
lua/input.lua
lua/workspaces.lua
lua/appearance.lua
lua/window_rules.lua
lua/keybinds.lua
lua/macros/example.lua
```

`init.lua` is a thin router and `lua/keybinds.lua` contains the full default keymap expanded as `koma.bind(...)` calls, so the generated file and the built-in fallback keymap cannot drift. Every generated file starts with the machine-readable marker `-- koma-config-template: <version>`.

Existing files are never overwritten: `komactl init` refuses and lists the conflicting paths unless you pass `--force`. After editing, run `komactl validate` and `komactl reload`. `komactl config-status` compares the on-disk marker with the shipped template and reports `template.installed_version`, `template.shipped_version`, `template.outdated`, and `template.missing_files`.

Two further `template` fields disambiguate the cases the version comparison cannot see: `template.init_lua` is the exact path that was inspected (resolved from `KOMA_CONFIG`, then `$XDG_CONFIG_HOME/koma/init.lua`, then `$HOME/.config/koma/init.lua`), and `template.present` says whether that file exists at all. A hand-written `init.lua` without the marker reports `installed_version: null` and `outdated: false` rather than looking stale, while a half-deleted scaffold shows up in `missing_files`.

## Effective Input in `komactl config-status`

The same report embeds the compositor's `config.status`, whose `input.pointer` and `input.touchpad` blocks list the values Koma actually applies: `accel_speed`, `accel_profile`, `natural_scroll`, `scroll_factor`, `follow_mouse`, plus `tap_to_click` and `disable_while_typing` for touchpads. A `null` means the key was never written in `init.lua`, so libinput's built-in default applies; `accel_profile` is either `"adaptive"` (the default curve) or `"flat"` (no acceleration). When the pointer travels a different distance than in another compositor at the same physical movement, compare `accel_speed` and `accel_profile` first — an unset profile explains most of the difference.

### XKB Keyboard Map in `config.status`

The same `input` object now carries `input.keyboard`: `layout`, `variant`, `model`, `options`, `repeat_delay_ms`, and `repeat_rate_hz`. A `null` again means "not configured", so the XKB/libinput default applies; `options` is the raw XKB option string, which makes a remap verifiable without reading `init.lua`. These are the same values that drive text repeat and hold-to-repeat keybinds.

`options` uses XKB names, exactly the ones Hyprland accepts in `kb_options`, and anything `setxkbmap -option` accepts works:

| Option | Effect |
| :--- | :--- |
| `caps:escape` | Caps Lock acts as Escape |
| `caps:ctrl_modifier` | Caps Lock becomes an extra Ctrl |
| `ctrl:nocaps` | Caps Lock is mapped to Ctrl |
| `altwin:swap_lalt_lwin` | Swap Left Alt and Left Super |
| `compose:caps` | Caps Lock becomes the Compose key |
| `grp:alt_shift_toggle` | Alt + Shift switches the keyboard layout group |

### Frame-Time Histogram in `config.status` (`frame_perf`)

`config.status` also exposes `frame_perf` with zero-allocation render telemetry (`rendered_frames`, `skipped_frames`, `avg_us`, `max_us`, `last_us`, `p50_bucket`, `p95_bucket`, and fixed buckets `lt_1ms` through `ge_16ms`), alongside periodic `tracing::debug!` summaries every 1,000 rendered frames.

## Configuration Diagnostics (`komactl doctor` & `komactl keys`)

Both commands reuse the same jailed shadow-VM evaluation as `komactl validate`, so they work offline and never need a seat. `komactl doctor` groups its checks into `config`, `template`, `binds`, `monitors`, `workspaces`, `rules`, and `environment`, and every row carries a severity: `ok` (the check ran and found nothing), `warn` (loads fine, probably not what was intended), `error` (would be rejected on the next reload), or `skip` (cannot run here, such as no DRM or no live compositor).

`error` never changes the exit code, because the compositor keeps running on its last valid configuration and a broken config must not brick the session. `--strict` exits `1` on any warn or error; `2` is reserved for a configuration that cannot be read at all, a usage error, or an internal failure. `--json` emits one document with the counts and every per-check row.

`komactl keys` prints the effective map: the built-in catalogue merged with `input.inherit_default_binds`, `koma.unbind`, and chord overrides, plus pointer binds and gestures in their own sections. Every row shows the chord, action, Lua expression, source (`builtin` or `config:<file>`), and description; an override keeps the built-in description in parentheses so the original stays visible. `--grep <pattern>` filters rows case-insensitively, and `--json` emits `{catalogue, keyboard, pointer, gestures, total, overridden_builtins}`. Nothing is hidden: a bind the compositor cannot translate back into a catalogue entry is printed with its raw action descriptor. The listing is offline by default; when a live `koma-admin.sock` is reachable, the header and the JSON `live` object merge the running generation, active configuration path, and lock state, read-only.

## `komactl sandbox` Container Isolation

`komactl sandbox` creates a restricted `jail-<ws_id>.sock` (never mounting the host `$XDG_RUNTIME_DIR`, `koma-admin.sock`, D-Bus, PipeWire, or SSH agent) inside a private `0700` `tmpfs` runtime directory:

```bash
# Run a browser inside an ephemeral bwrap sandbox on a 1920x1080 Headless workspace (network isolated by default)
komactl sandbox run --name browser-jail -- firefox

# Run an OCI container via rootless podman with network enabled and dry-run inspection first
komactl sandbox run --runtime podman --image fedora:latest --share-net --dry-run -- glxgears

# Explicitly grant scoped agent access (mounts koma-agent.sock + single-workspace KOMA_CAPABILITY_TOKEN)
komactl sandbox run --with-agent-sock --ro-bind ~/repo:/workspace -- code-oss
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--runtime <bwrap\|podman>` | `bwrap` | Container engine (auto-switches to `podman` if `--image` is provided) |
| `--ws <ws_id\|auto>` | `auto` | Reuse an existing `ws_id` or allocate a new `Headless` workspace |
| `--name <name>` | `sandbox` | Name for newly created `Headless` workspace |
| `--geometry <WxH[@scale]>` | `1920x1080` | Viewport dimensions and scale (e.g. `2560x1600@1.6`) |
| `--bind <host:guest>` / `--ro-bind` | none | Explicit host bind mounts |
| `--share-net` | off | Enable host network (`bwrap`) or `pasta` (`podman`); isolated by default |
| `--no-gpu` | off | Omit `/dev/dri` passthrough to force software Mesa/Lavapipe |
| `--nvidia` | off | Add `--device=nvidia.com/gpu=all` CDI flag on Podman |
| `--with-agent-sock` | off | Mount `koma-agent.sock` + inject single-workspace `KOMA_CAPABILITY_TOKEN` (never `koma-admin.sock`) |
| `--keep-jail` | off | Keep `jail-<ws_id>.sock` alive after exit (`create-jail` / `revoke-jail` manage it manually) |
| `--dry-run` | off | Print the exact container command without spawning |

## `koma` Subcommands (`init`, `completions`, `mcp`)

The compositor binary also owns three non-compositor subcommands:

| Command | Description |
| :--- | :--- |
| `koma init <bash\|zsh\|fish\|nushell> [--unset]` | Prints shell-native assignments for the live instance |
| `koma completions <bash\|zsh\|fish>` | Prints the completion script rendered from the binary's command table |
| `koma mcp [--print-tools] [--auto-mint-admin]` | Runs the stdio MCP server against `koma-agent.sock` |

`koma init` exports `WAYLAND_DISPLAY`, `KOMA_INSTANCE_SIGNATURE`, `XDG_RUNTIME_DIR`, `DISPLAY` (only while `xwayland-satellite` is up), `XDG_SESSION_TYPE`, and `XDG_CURRENT_DESKTOP`, so `komactl` and other tools work from an external terminal:

```bash
koma init fish | source
eval "$(koma init bash)"
koma init zsh --unset   # inverse assignments
```

It never prints capability tokens. With no live instance, or with several live instances, it fails with a clear message instead of guessing; set `KOMA_INSTANCE_SIGNATURE` to choose one.

`koma mcp` is the stdio server formerly shipped as the separate `koma-mcp` binary. `--print-tools` dumps the 17 tool schemas offline without touching the agent socket, and `--auto-mint-admin` mints a local development token from `koma-admin.sock`.

## Spatial Overview (`koma-overview`)

![koma-overview spatial workspace switcher](https://cdn.komawm.org/media/koma-overview.webp)

Toggle `koma-overview` via `Mod + Tab` (or bind `koma.act.overview.toggle()`):

- Attaches via `zwlr_layer_shell_v1` on the active output and queries `koma-admin.sock` `scene.inventory`.
- Displays all Headed and Headless workspaces (including `agent:work` decks and background Stash counts) in a unified spatial grid with zero idle GPU wakeups.
