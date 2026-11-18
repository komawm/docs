# komactl & Workspace Overview

`komactl` is Koma's administration CLI (`koma-admin.sock`) and offline Lua validator, while `koma-overview` provides a `wlr-layer-shell` spatial overview across all workspaces.

## `komactl` Command Reference

`komactl` discovers `$XDG_RUNTIME_DIR/koma/<signature>/koma-admin.sock` automatically (or via `KOMA_INSTANCE_SIGNATURE`).

| Command | Mode | Description |
| :--- | :--- | :--- |
| `komactl validate [path/to/init.lua]` | Offline | Evaluates `init.lua` in the isolated Lua sandbox, validates rule regexes & gestures, and prints resource counts |
| `komactl reload [path/to/init.lua]` | IPC (`admin.sock`) | Sends `config.reload` and atomically swaps live compositor configuration |
| `komactl config-status` | IPC (`admin.sock`) + offline | Prints active config path, reload generation, last error if any (`config.status`), plus `template.{installed_version,shipped_version,outdated,missing_files}` for the generated scaffold |
| `komactl init [dir] [--force]` | Offline | Scaffolds `init.lua`, `lua/{input,workspaces,appearance,window_rules,keybinds}.lua`, and `lua/macros/example.lua`; refuses to overwrite existing files unless `--force` is given |
| `komactl gen-types` | Offline | Emits deterministic `LuaCATS` stubs for `koma-types` (`types/koma.lua`) |
| `komactl inventory` | IPC (`admin.sock`) | Prints live monitors, workspaces, `Epoch` counters, Deck windows, and Stash slots (`scene.inventory`) |
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
