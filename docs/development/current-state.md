# Current-state source and verification inventory

This inventory records the state of the `komawm` workspace and its six published GitHub repositories (`v0.0.1` incubation baseline) on 2026-11-14. Refresh it when build, contract or runtime acceptance changes. Detailed local verification logs and read-only upstream reference checkouts (`recording/references/Hyprland`, `recording/references/niri`) are retained in the workspace's ignored `recording/` directory rather than published as product source.

## Organization & repository status (`v0.0.1` incubation baseline)

All six `komawm` repositories (`koma`, `jiku`, `koma-types`, `docs` / checkout `koma-docs`, `packaging`, and `.github`) are initialized, verified against their local repository gates, and published to GitHub under the `komawm` organization at the `v0.0.1` incubation baseline. Development remains on `0.0.x` until independent runtime and security acceptance criteria for `v0.1.0` are met.

## What exists and passes under Rust `1.100.0` (Edition 2024)

### 1. `koma` (`d4ea6f3c7a0bf801ae173c1e3f89439e9201e0fb`)

The `koma` workspace manifest contains nine crates: five libraries (`koma-proto`, `koma-model`, `koma-lua`, `koma-render`, `koma-seat`) and four binaries (`koma`, `komactl`, `koma-mcp`, `koma-overview`). It follows a zero-hardcoding, configurable-defaults + user-overrides architecture across `koma-model`, `koma-lua`, `koma-render`, and `koma-seat`:
- **Configurable global & per-workspace layouts**: Headed workspaces default to `"dwindle"` (`LayoutMode::Dwindle`), configurable globally via `koma.layout("dwindle" | "scrolling" | "deck" | "bsp")` or per-workspace via `koma.workspace({ layout = ..., gaps = ... })`, with fine-grained parameters in `koma.dwindle({...})` and `koma.scrolling({...})`.
- **Inheritable default keybinding table with in-place overrides**: `koma.input({ inherit_default_binds = true })` (default) loads the built-in Hyprland-compatible default keybinding table (`Mod + Return`, `Mod + Q`, `Mod + M`, `Mod + V`, `Mod + F`, `Mod + P`, `Mod + E`, `Mod + S`, `Mod + H/J/K/L`, `Mod + Shift + H/J/K/L`, `Mod + 1..9`, `Mod + Shift + 1..9`, `Mod + MouseLeft/Right`, `Mod + WheelScrollDown/Up`), merges user `koma.bind(...)` calls by overriding matching chords in-place without wiping other defaults, and supports `koma.unbind(chord)` to remove specific default chords.
- **Complete typed appearance defaults**: `koma.appearance({...})` exposes typed defaults and user overrides for `border` (`enabled`, `width`, `active_color`, `inactive_color`, `agent_leased_color`, `human_preempt_color`), `focus_ring`, `shadow`, `dim` (plus top-level `brightness`, `dim_inactive`, `dim_strength` convenience fields), `blur`, `animations`, and `corner_radius`.

Under the pinned target toolchain **Rust `1.100.0` (Edition 2024)**, all nine crates cleanly pass the repository quality gates:

- `just fmt-check` (`cargo fmt --all -- --check`)
- `just check-core` (`cargo check --workspace --locked --exclude koma --exclude koma-render`)
- `just typecheck` (`cargo check --workspace --all-targets --locked`)
- `just clippy` (`cargo clippy --workspace --all-targets --locked -- -D warnings`)
- `just test-core` (`cargo test --locked -p koma-proto -p koma-model -p koma-lua -p koma-seat`)
- `just test` (`cargo test --workspace --locked`, passing unit tests across `koma-model`, `koma-lua`, `koma-render`, `koma-seat`, and `koma`)
- `komactl gen-types` (deterministic LuaLS definition emission from `koma-lua`)
- `koma --headless-check` (headless structural configuration and launch-path check)

### 2. `koma-types` (`generator_reproduced = true`)

`koma-types` reproduces `types/koma.lua` byte-for-byte from `komactl gen-types` (including `LuaCATS` annotations for `koma.layout`, `koma.unbind`, `koma.input` with `inherit_default_binds`, and the full `koma.appearance` schema across `border`, `focus_ring`, `shadow`, `dim`, `blur`, `animations`, and `corner_radius`), recorded in `manifest.toml` with `generator_reproduced = true` and verified by `just check`.

### 3. `jiku` (Three-Driver pure-data contracts, configurable defaults & scaffold tests)

The `jiku` workspace (`jikud`, `jiku`, `jiku-memory`, `jiku-tts`) defines pure-data contracts, configuration schemas, wire envelopes, and unit tests for the **Three-Driver architecture** (`DecisionsDriver` / `DecisionBackend` for `gemini-decision-1` zero-decode single-prefill decisions with automatic `EmulatedStructuredTextModel` fallback on `[roles.planner]`, `TurnModelDriver` for HTTP/2 SSE planner/text/Lua synthesis turns, and optional `LiveSessionDriver` for stateful full-duplex WebSocket `BidiGenerateContent` companion sessions). All compiler and runtime parameters use configurable defaults without hardcoded constants—including `[roles.decision_router.compiler]` (`DecisionCompilerConfig`: `fast_path_confidence = 0.85`, `min_cell_prob = 0.05`, `time_slot_min_confidence = 0.75`, `bernoulli_activation_threshold = 0.80`, `probe_min_prob = 0.15`, `stop_sentinel = "stop_done"`, `fallback_token = "NONE_OR_OTHER"`), `[roles.decision_router.compiler.grid]` (`GridSpec`: `cols = 15`, `rows = 15`), and range-validated `[roles.live_companion]` rates (`audio_in_sample_rate_hz` `8000..=48000` default `16000`, `audio_out_sample_rate_hz` `8000..=48000` default `24000`, `max_screen_fps` `1..=60` default `2`)—and passes all local formatting, typecheck, Clippy, and unit test gates under Rust `1.100.0`. Prior to `v0.1.0`, `jiku` remains a library-only, non-runnable scaffold with no network I/O daemon or executable CLI binary.

## `v0.0.1` development prerelease

`v0.0.1` is published as GitHub prereleases of `komawm/koma` (Linux x86_64 binary archive plus `SHA256SUMS`), `komawm/jiku` (library-scaffold source archive) and `komawm/koma-types` (LuaLS definitions). Each tag-triggered `release.yml` re-runs the repository gates on the tagged revision, verifies the tag against the manifest version, and publishes through a protected `release` environment that only accepts `v*.*.*` tags. `komawm/packaging` provides the manual `cd-archlinux.yml` workflow that builds an Arch Linux review-candidate package and uploads it to the Koma prerelease once the `PRODUCT_RELEASE_TOKEN` environment secret is configured. These prereleases are development snapshots: no DRM/KMS, hardware, installation, or security acceptance is implied; see the [release plan](https://github.com/komawm/.github/blob/main/docs/releases.md).

## Boundaries that still matter

- **Compilation & unit tests vs. live display/runtime acceptance**: Passing `just test`, `just clippy`, and `koma --headless-check` under Rust `1.100.0` proves source/API coherence and unit-tested model/Lua/render invariants at `28f5d9513e8d2952c1522b8d8ae729f7d5574c50`. It does **not** initialize a live display backend or prove end-to-end nested Wayland rendering, DRM/KMS scanout, physical `libinput`/`libseat` device handling, `SCM_RIGHTS` `memfd` zero-copy frame transport under load, or adversarial sandbox enforcement.
- **Jiku execution boundary**: While `jiku` now codifies and unit-tests the pure-data contracts for `DecisionsDriver`, `TurnModelDriver`, and `LiveSessionDriver` alongside configuration templates and bundled skills, live HTTP/2 SSE, `/v1beta/decisions`, WebSocket `BidiGenerateContent`, PipeWire audio, and Landlock daemon execution remain `v0.1.0` implementation targets; Live2D/VRM avatar rendering remains a separate subscriber boundary.
- **Dependency provenance**: `Koma` pins Smithay to a reviewed Git revision and consumes `Phodopus` as an independent upstream Git dependency (`https://github.com/Xuepoo/phodopus`) locked in `Cargo.lock`. Do not silently redirect dependencies to sibling workstation checkouts.
- **Platform & licensing boundaries**: The development host is Arch Linux; FreeBSD/OpenBSD portability remains unverified. `Koma` (including `koma-proto`) and `Jiku` use `GPL-3.0-or-later`; `koma-types` uses `Apache-2.0`; `koma-docs`, `packaging`, and `.github` use `MIT`.

## Next acceptance stages toward `v0.1.0`

Follow the [testing plan](https://github.com/komawm/docs/blob/main/docs/development/testing.md) in strict order:

1. **Nested compositor validation**: Exercise `koma --winit` in an isolated nested window with test Wayland clients, IPC commands (`komactl`), and `Phodopus` Lua configuration reload.
2. **Disposable QEMU/KVM session validation**: Validate `koma --tty`, `seatd`/`logind`, virtual DRM/KMS, and `koma-agent.sock` `Epoch` fencing inside an isolated VM image using read-only ISOs from `ISO_PATH` and recording command lines/evidence under ignored `recording/`.
3. **Separately authorized physical-seat & runnable `jikud` acceptance**: Only with explicit user authorization, validate physical GPU/input hardware and connect a runnable `jikud` implementation against `koma-agent.sock`. Never replace the active Hyprland host session during routine development.
