# Current-state source and verification inventory

This inventory records the state of the `komawm` workspace and its six published GitHub repositories (`v0.0.1` incubation baseline) on 2026-11-14. Refresh it when build, contract or runtime acceptance changes. Detailed local verification logs and read-only upstream reference checkouts (`recording/references/Hyprland`, `recording/references/niri`) are retained in the workspace's ignored `recording/` directory rather than published as product source.

## Organization & repository status (`v0.0.1` incubation baseline)

All six `komawm` repositories (`koma`, `jiku`, `koma-types`, `docs` / checkout `koma-docs`, `packaging`, and `.github`) are initialized, verified against their local repository gates, and published to GitHub under the `komawm` organization at the `v0.0.1` incubation baseline. Development remains on `0.0.x` until independent runtime and security acceptance criteria for `v0.1.0` are met.

## What exists and passes under Rust `1.100.0` (Edition 2024)

### 1. `koma` (`28f5d9513e8d2952c1522b8d8ae729f7d5574c50`)

The `koma` workspace manifest contains nine crates: five libraries (`koma-proto`, `koma-model`, `koma-lua`, `koma-render`, `koma-seat`) and four binaries (`koma`, `komactl`, `koma-mcp`, `koma-overview`). Under the pinned target toolchain **Rust `1.100.0` (Edition 2024)** at commit `28f5d9513e8d2952c1522b8d8ae729f7d5574c50`, all nine crates cleanly pass the repository quality gates:

- `just fmt-check` (`cargo fmt --all -- --check`)
- `just check-core` (`cargo check --workspace --locked --exclude koma --exclude koma-render`)
- `just typecheck` (`cargo check --workspace --all-targets --locked`)
- `just clippy` (`cargo clippy --workspace --all-targets --locked -- -D warnings`)
- `just test-core` (`cargo test --locked -p koma-proto -p koma-model -p koma-lua -p koma-seat`)
- `just test` (`cargo test --workspace --locked`, passing **25 unit tests** across `koma-model` (`21`), `koma-lua` (`2`), `koma-render` (`1`), and `koma` (`1`))
- `komactl gen-types` (deterministic LuaLS definition emission from `koma-lua`)
- `koma --headless-check` (headless structural configuration and launch-path check)

### 2. `koma-types` (`generator_reproduced = true`)

`koma-types` reproduces `types/koma.lua` byte-for-byte from `komactl gen-types` at Koma revision `28f5d9513e8d2952c1522b8d8ae729f7d5574c50`, recorded in `manifest.toml` with `generator_reproduced = true` and verified by `just check`.

### 3. `jiku` (Three-Driver pure-data contracts & scaffold tests)

The `jiku` workspace (`jikud`, `jiku`, `jiku-memory`, `jiku-tts`) defines pure-data contracts, configuration schemas, wire envelopes, and unit tests for the **Three-Driver architecture** (`DecisionsDriver` for `gemini-decision-1` zero-decode single-prefill decisions, `TurnModelDriver` for HTTP/2 SSE planner/text/Lua synthesis turns, and `LiveSessionDriver` for stateful full-duplex WebSocket `BidiGenerateContent` companion sessions) and passes all local formatting, typecheck, Clippy, and unit test gates under Rust `1.100.0`. Prior to `v0.1.0`, `jiku` remains a library-only, non-runnable scaffold with no network I/O daemon or executable CLI binary.

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
