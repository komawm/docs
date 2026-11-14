# Current-state source and verification inventory

This inventory records the state of the `komawm` workspace and its six published GitHub repositories (`v0.0.1` incubation baseline) on 2026-11-15. Refresh it when build, contract or runtime acceptance changes. Detailed local verification logs and read-only upstream reference checkouts (`recording/references/Hyprland`, `recording/references/niri`) are retained in the workspace's ignored `recording/` directory rather than published as product source.

## Organization & repository status (`v0.0.1` incubation baseline)

All six `komawm` repositories (`koma`, `jiku`, `koma-types`, `docs` / checkout `koma-docs`, `packaging`, and `.github`) are initialized, verified against their local repository gates, and published to GitHub under the `komawm` organization at the `v0.0.1` incubation baseline. Development remains on `0.0.x` until independent runtime and security acceptance criteria for `v0.1.0` are met.

## What exists and passes under Rust `1.100.0` (Edition 2024)

### 1. `koma` (`edd053bbdc5e3c5fefa83489b12b3db3578f00ba`)

The `koma` workspace manifest contains nine crates: five libraries (`koma-proto`, `koma-model`, `koma-lua`, `koma-render`, `koma-seat`) and four binaries (`koma`, `komactl`, `koma-mcp`, `koma-overview`). It follows a zero-hardcoding, configurable-defaults + user-overrides architecture across `koma-model`, `koma-lua`, `koma-render`, and `koma-seat`:
- **Configurable global & per-workspace layouts**: Headed workspaces default to `"dwindle"` (`LayoutMode::Dwindle`), configurable globally via `koma.layout("dwindle" | "scrolling" | "deck" | "bsp")` or per-workspace via `koma.workspace({ layout = ..., gaps = ... })`, with fine-grained parameters in `koma.dwindle({...})` and `koma.scrolling({...})`.
- **Inheritable default keybinding table with in-place overrides**: `koma.input({ inherit_default_binds = true })` (default) loads the built-in Hyprland-compatible default keybinding table (`Mod + Return`, `Mod + Q`, `Mod + M`, `Mod + V`, `Mod + F`, `Mod + P`, `Mod + E`, `Mod + S`, `Mod + H/J/K/L`, `Mod + Shift + H/J/K/L`, `Mod + 1..9`, `Mod + Shift + 1..9`, `Mod + MouseLeft/Right`, `Mod + WheelScrollDown/Up`), merges user `koma.bind(...)` calls by overriding matching chords in-place without wiping other defaults, and supports `koma.unbind(chord)` to remove specific default chords.
- **Complete typed appearance defaults**: `koma.appearance({...})` exposes typed defaults and user overrides for `border` (`enabled`, `width`, `active_color`, `inactive_color`, `agent_leased_color`, `human_preempt_color`), `focus_ring`, `shadow`, `dim` (plus top-level `brightness`, `dim_inactive`, `dim_strength` convenience fields), `blur`, `animations`, and `corner_radius`.
- **Bare-metal TTY software KMS fallback, Wayland client promotion & `vseat.inject_text` strategy dispatch**: Supports `--tty`, `--winit`, `--headless-check`, `--session`, `--spawn`, `--config`, and clean `SIGTERM`/`SIGINT`/`SIGHUP` teardown; promotes mapped Wayland clients into workspace layouts; and honors `TextInjectStrategy` with synchronous US QWERTY ASCII XKB keystroke injection and terminal-aware `Ctrl+Shift+V` clipboard paste chords.

Under the pinned target toolchain **Rust `1.100.0` (Edition 2024)**, all nine crates cleanly pass the repository quality gates:

- `just fmt-check` (`cargo fmt --all -- --check`)
- `just check-core` (`cargo check --workspace --locked --exclude koma --exclude koma-render`)
- `just typecheck` (`cargo check --workspace --all-targets --locked`)
- `just clippy` (`cargo clippy --workspace --all-targets --locked -- -D warnings`)
- `just test-core` (`cargo test --locked -p koma-proto -p koma-model -p koma-lua -p koma-seat`)
- `just test` (`cargo test --workspace --locked`, passing unit tests across `koma-model`, `koma-lua`, `koma-render`, `koma-seat`, `koma-proto`, `koma-mcp`, `koma-overview`, `komactl`, and `koma`)
- `komactl gen-types` (deterministic LuaLS definition emission from `koma-lua`)
- `koma --headless-check` (headless structural configuration and launch-path check)

### 2. `koma-types` (`generator_reproduced = true`)

`koma-types` reproduces `types/koma.lua` byte-for-byte from `komactl gen-types` (including `LuaCATS` annotations for `koma.layout`, `koma.unbind`, `koma.input` with `inherit_default_binds`, and the full `koma.appearance` schema across `border`, `focus_ring`, `shadow`, `dim`, `blur`, `animations`, and `corner_radius`), recorded in `manifest.toml` with `generator_reproduced = true` and verified by `just check`.

### 3. `jiku` (`1f22c4d6ba2b7d51673a8e4fe3ec8973464eec35`)

The `jiku` workspace (`jikud`, `jiku`, `jiku-memory`, `jiku-tts`) provides the runnable v0.0.1 daemon, CLI, MCP server, and Three-Driver runtime:
- **Daemon (`jikud`) & CLI/MCP (`jiku`)**: Unix-socket RPC daemon (`$XDG_RUNTIME_DIR/jiku.sock`) with `--daemon`, `--headless-check`, `--validate-config`, and clean `SIGTERM`/`SIGINT`/`SIGHUP` removal, plus `jiku` subcommands (`status`, `validate-config`, `decide`, `plan`, `run`, `box classify`, `memory search`, `skills <list|diff|stage|approve>`, `mcp --stateless | --print-tools`).
- **Three-Driver clients & configurable compiler**:
  - `DecisionsDriver`: calls `gemini-decision-1` (`POST https://generativelanguage.googleapis.com/v1beta/decisions`) using the verified `input`/`questions` -> `answers`/`usage` (`total_output_tokens == 0`) contract, with automatic `EmulatedStructuredTextModel` fallback and configurable `[roles.decision_router.compiler]` / `[roles.decision_router.compiler.grid]` parameters (`DecisionCompilerConfig`, `GridSpec`).
  - `TurnModelDriver`: supports **OpenCode Go** (`kind = "opencode_go"`, `https://opencode.ai/inference/go/openai/v1/chat/completions`, deterministic `x-opencode-session` UUIDv4 header, defaulting to `deepseek-v4.1-flash` with `"thinking": {"type": "disabled"}`) as well as OpenAI-compatible, Google AI Studio, and Anthropic providers.
  - `LiveSessionDriver`: full-duplex WebSocket client for Gemini `BidiGenerateContent` with range-validated `[roles.live_companion]` parameters.
- **Memory, Policy, TTS & Koma IPC**: `jiku-memory` provides SQLite WAL + FTS5 BM25 episodic memory (`l1_app_quirks`, `l2_episodes`), visual `dHash`, and human-gated `staged_skills` staging/diff/promotion; `jikud` integrates `Phodopus` Lua lifecycle/prefetch hooks, `~/JikuBox/` batch classification (`jiku box classify`), `jiku-tts` PCM envelopes (`VOICEVOX` / `OpenAI` / `noop`), and `KomaIpcClient` (`SCM_RIGHTS` `memfd` frame capture + `vseat.*` actions). Offline `just check` passes 35 workspace unit tests (`jiku`, `jiku-memory`, `jiku-tts`, `jikud`).

## `v0.0.1` development prerelease

`v0.0.1` is published as GitHub prereleases of `komawm/koma` (Linux x86_64 binary archive plus `SHA256SUMS`), `komawm/jiku` (runtime/CLI source archive) and `komawm/koma-types` (LuaLS definitions). Each tag-triggered `release.yml` re-runs the repository gates on the tagged revision, verifies the tag against the manifest version, and publishes through a protected `release` environment that only accepts `v*.*.*` tags. `komawm/packaging` provides the manual `cd-archlinux.yml` workflow plus the local `vm/arch-vm.sh` QEMU/KVM Arch Linux VM harness to test installation, `koma --tty`, and `jikud`/`jiku` end-to-end, uploading Arch Linux packages to the Koma prerelease once `PRODUCT_RELEASE_TOKEN` is configured. These prereleases are development snapshots: no physical GPU/hardware or security acceptance is implied; see the [release plan](https://github.com/komawm/.github/blob/main/docs/releases.md).

## Boundaries that still matter

- **Isolated VM software KMS vs. physical hardware acceptance**: Both `koma --tty --spawn foot` (`llvmpipe` software EGL over `virtio-vga` with `seatd`) and full `jikud` -> `gemini-decision-1` + OpenCode Go `deepseek-v4.1-flash` -> `KomaIpcClient` (`vseat.inject_text` / `vseat.key` -> `foot` writing `/tmp/jiku-proof.txt`) have now passed inside a disposable QEMU/KVM Arch Linux VM, alongside live API checks (`decide`, `plan`, `box classify`) on the host. However, bare-metal DRM/KMS scanout on physical iGPU/dGPU hardware, physical `libinput` devices, nested `--winit` multi-client stress, and hardware Virgl GPU passthrough remain unverified outside the VM.
- **Remaining `jiku` `v0.1.0` hardening & media boundaries**: Live PipeWire `16 kHz` / `24 kHz` audio device streaming, Landlock filesystem/network sandboxing around `jikud`, and Live2D/VRM avatar frontend rendering remain `v0.1.0` targets.
- **Dependency provenance**: `Koma` pins Smithay to a reviewed Git revision and consumes `Phodopus` as an independent upstream Git dependency (`https://github.com/Xuepoo/phodopus`) locked in `Cargo.lock`. Do not silently redirect dependencies to sibling workstation checkouts.
- **Platform & licensing boundaries**: The development host is Arch Linux; FreeBSD/OpenBSD portability remains unverified. `Koma` (including `koma-proto`) and `Jiku` use `GPL-3.0-or-later`; `koma-types` uses `Apache-2.0`; `koma-docs`, `packaging`, and `.github` use `MIT`.

## Next acceptance stages toward `v0.1.0`

Follow the [testing plan](https://github.com/komawm/docs/blob/main/docs/development/testing.md) in strict order:

1. **Nested compositor & multi-client stress validation**: Exercise `koma --winit` with multiple Wayland/XWayland clients, `Phodopus` hot reload, and `Mod+G` human preemption barriers under interactive load.
2. **Physical GPU & `virgl` / dGPU KMS validation**: Verify `koma --tty` on real DRM/KMS hardware (and optional `virtio-vga-gl` / `egl-headless` VM sessions) without falling back to `llvmpipe`.
3. **Hardened `jikud` & live voice acceptance**: Validate Landlock sandboxing, live `PipeWire` audio streaming over `LiveSessionDriver`, and separately authorized physical-seat desktop workflows without replacing the active Hyprland host session during routine development.
