# Current-state source and verification inventory

This inventory records the state of the `komawm` workspace and its published GitHub repositories (`v0.0.1` incubation baseline) on 2026-11-15. It separates **existing implementation**, **compiler/unit-test checks**, **disposable VM runtime evidence**, and **planned `v0.1.0` proposals** as distinct claims. Detailed local verification logs and read-only upstream reference checkouts (`recording/references/Hyprland`, `recording/references/niri`) remain in the ignored `recording/` directory rather than tracked product source.

## Organization & repository status (`v0.0.1` incubation baseline)

All `komawm` repositories (`koma`, `jiku`, `koma-types`, `docs` / checkout `koma-docs`, `packaging`, `.github`, plus the `website` static storefront) are initialized, verified against their repository quality gates, and published under `https://github.com/komawm`. Product repositories stay on `0.0.x` until independent runtime and security acceptance criteria for `v0.1.0` are satisfied.

## Verified `main` source inventory & Rust `1.100.0` (Edition 2024) checks

### 1. `koma` (`aef9652814d216803dd05c1fb57b4fa340acc225`)

The `koma` workspace comprises nine crates — five libraries (`koma-proto`, `koma-model`, `koma-lua`, `koma-render`, `koma-seat`) and four binaries (`koma`, `komactl`, `koma-mcp`, `koma-overview`):

- **Zero-avoidable-`unsafe` Rust lint posture**: Enforces `[workspace.lints.rust] unsafe_code = "deny"` workspace-wide and `#![forbid(unsafe_code)]` across six crates (`koma-model`, `koma-lua`, `komactl`, `koma-mcp`, `koma-overview`, `koma-seat`), eliminating avoidable `unsafe` in `koma-proto` (`rustix::shm`), `config_watcher` (`rustix::fs::inotify`), `signals` (`rustix::pipe`), and child environment setup (`child_env` without `env::set_var` / `remove_var`).
- **Unified Hooke Spring + Cubic Bezier animation & ricing engine**: Implements Damped Hooke's Law Semi-Implicit Euler springs (`HookeSpringTrack` with up to 24 sub-steps and velocity-preserving `retarget`), overshoot-capable `CubicBezier` tracks (Newton-Raphson + bisection), named presets, `koma.bezier(...)` / `koma.spring(...)`, per-channel styles (`popin`, `slide`, `gnomed`, `fade`, `WorkspaceTransitionTable`), GLES2-compatible rotating dual-stop gradient borders (`active_color_end`, `inactive_color_end`, `gradient_angle`, `gradient_rotate_rpm`), Dual Kawase blur, and extended per-window rice rules (`inactive_opacity`, `animation`, `no_blur`, `no_shadow`, `border_color`).
- **Wayland protocol & multi-monitor matrix**: Implements cursor shape (`wp-cursor-shape-v1`), `wlr-layer-shell`, `ext-session-lock-v1`, IME (`text-input-unstable-v3` + `input-method-unstable-v2`), screencopy (`wlr-screencopy-unstable-v1` + `ext-image-copy-capture-v1`), `xdg-activation-v1`, `wlr-foreign-toplevel-management-v1`, `ext-idle-notify-v1` / idle inhibitor / DPMS / `wlr-gamma-control-v1`, and 2D multi-monitor layout + `wlr-output-management-unstable-v1`.
- **Layouts, defaults & Phodopus Lua closures**: Supports `"dwindle"` (default), `"scrolling"`, `"deck"`, and `"bsp"` layouts; `inherit_default_binds = true` with in-place `koma.bind` overrides and `koma.unbind`; `MacroContext` read-only desktop snapshots (`ctx:focused_window()`, `ctx:windows()`, `ctx:outputs()`, `ctx:workspaces()`) with `[protected]` title redaction and offscreen isolation; `ctx:dispatch(action)` (plus `koma.act.window.focus` and `koma.act.workspace.set_layout`); and fuel-metered Ring 0 `koma.on` lifecycle hooks (`compositor.start`, `config.reloaded`, `window.mapped`, `window.closed`, `window.focused`, `workspace.focused`, `output.changed`; recursion depth capped at `4`).
- **Verified Linux checks on `aef9652814d216803dd05c1fb57b4fa340acc225` (Rust `1.100.0`, Edition 2024)**: `just fmt-check`, `just check-core`, `just typecheck`, `just clippy` (`-D warnings`), `just test-core`, `just test` (including 61 `koma`, 28 `koma-model`, 10 `koma-lua` + 5 `--no-default-features`, and 6 `koma-proto` tests), `komactl gen-types`, and `luac -p` syntax checks on `examples/init.lua` and `examples/dotfiles_showcase.lua` all pass (`komawm/koma` GitHub Actions `CI` run `43693360615` completed `success`).

### 2. `koma-types` (`ebebc7f9ddd19edec81bade5151a5609e8090224`)

`koma-types` reproduces `types/koma.lua` (SHA-256 `dcfac4fcf8d80afe269b7efb796ad56451c220052570ef1cac27297ff274b241`) directly from `komactl gen-types` at `komawm/koma` revision `aef9652814d216803dd05c1fb57b4fa340acc225` (`generator_reproduced = true`) and passes `just check` (`scripts/check.py`, `scripts/check-links.py`, `actionlint`, `luac -p`, `shellcheck`; GitHub Actions `CI` run `43693511465` completed `success`).

### 3. `jiku` (`39ab03ef6ae6b22dd98e2c55bd4475886d39717d`)

The `jiku` workspace (`jikud`, `jiku`, `jiku-memory`, `jiku-tts`) provides the runnable `v0.0.1` daemon, CLI, MCP server, and Three-Driver runtime:

- **Workspace-wide `#![forbid(unsafe_code)]`**: `[workspace.lints.rust] unsafe_code = "forbid"` plus `#![forbid(unsafe_code)]` across all four crates (`jikud`, `jiku`, `jiku-memory`, `jiku-tts`), replacing `rustix::mm` with safe `File`/`Seek`/`Read` operations.
- **Daemon, CLI, MCP & Three-Driver runtime**: `jikud` Unix-socket RPC daemon (`$XDG_RUNTIME_DIR/jiku.sock`) with `--daemon`, `--headless-check`, `--validate-config`; `jiku` subcommands (`status`, `validate-config`, `decide`, `plan`, `run`, `box classify`, `memory search`, `skills <list|diff|stage|approve>`, `mcp --stateless | --print-tools`); `DecisionsDriver` (`gemini-decision-1` + `EmulatedStructuredTextModel`), `TurnModelDriver` (OpenCode Go, OpenAI-compatible, Google AI Studio, Anthropic), `LiveSessionDriver`, `jiku-memory` SQLite WAL + FTS5 BM25 episodic memory, `Phodopus` Lua hooks, and `KomaIpcClient`. GitHub Actions `CI` and `CodeQL` pass on `39ab03ef6ae6b22dd98e2c55bd4475886d39717d`.

### 4. `packaging` & `docs` / `website` infrastructure

- **`komawm/packaging`**: Provides Arch Linux (`PKGBUILD.in`, `PKGBUILD.jiku.in`, `cd-archlinux.yml`), Debian/Ubuntu (`debian/*`, `apt/komawm.sources`, `apt/setup.sh`), Alpine (`alpine/APKBUILD.in`), FreeBSD Ports (`freebsd/Makefile.in`), Homebrew (`homebrew/koma.rb.in`), `nfpm`, and QEMU/KVM harnesses (`vm/arch-vm.sh`, `vm/freebsd-vm.sh`, `vm/koma-smoke.sh`).
- **`komawm/docs` & `komawm/website`**: `koma-docs` maintains canonical engineering specs plus the 19-topic tri-lingual (`en`, `zh-CN`, `ja`, 57 Markdown pages) Koma & Jiku manual corpus, published to `https://cdn.komawm.org/manual/` and statically rendered by `komawm/website` under strict `style-src 'self'; script-src 'self'` CSP.

## VM verification evidence (`recording/2026-11-15/`)

- **Arch Linux QEMU/KVM end-to-end runtime smoke (`recording/2026-11-15/vm-arch-koma-final/EVIDENCE.md`)**: Verified `10/10` PASS at `koma` `cfabbb81e9406f5cba69f8dcd21785989bca3743` (`koma --tty --spawn foot` over `llvmpipe` / `virtio-vga` with `seatd`, `WAYLAND_DISPLAY` + dual sockets, `komactl` window/workspace verification, live `foot` launch and `Mod+Q` exit, and clean `SIGTERM` shutdown).
- **FreeBSD `15.1-RELEASE` (`GENERIC amd64`, `rustc 1.100.0`) QEMU/KVM compilation & unit tests (`recording/2026-11-15/vm-freebsd-koma/EVIDENCE.md`)**: `vm/freebsd-vm.sh koma-check` (`cargo check --workspace --all-targets --locked` + `cargo test --workspace --locked`) **PASSED** (`exit 0`, **114 passed, 0 failed, 0 ignored** across all 9 crates and doc-tests) on final `komawm/koma` `main` `aef9652814d216803dd05c1fb57b4fa340acc225` (as well as `104 passed, 0 failed` on earlier `cfabbb81e9406f5cba69f8dcd21785989bca3743`).

## Claim boundaries & planned `v0.1.0` work (not yet shipped)

- **FreeBSD runtime boundary**: The FreeBSD `15.1-RELEASE` evidence proves clean BSD compilation and workspace unit tests; interactive Wayland rendering and physical DRM/KMS on FreeBSD remain unverified (`runtime_verified = false`). OpenBSD runtime remains unverified.
- **Physical hardware & multi-client display boundary**: Bare-metal DRM/KMS scanout on physical iGPU/dGPU hardware, physical `libinput` devices, nested `--winit` multi-client stress, and `virgl` GPU passthrough remain unverified outside disposable software-KMS VMs.
- **Planned `jiku` `v0.1.0` milestones (deferred during `v0.0.x`)**: Multi-format layer-shell avatar frontends (`VRM 0.x/1.0`, `MMD`, `Live2D Cubism`, `Inochi2D`), live `PipeWire` audio capture/streaming, and Linux `Landlock` + `seccomp` confinement for `jikud`.
- **Dependency provenance & licensing**: `Koma` pins Smithay and consumes `Phodopus` (`https://github.com/Xuepoo/phodopus`) via `Cargo.lock`. `Koma` and `Jiku` use `GPL-3.0-or-later`; `koma-types` uses `Apache-2.0`; `koma-docs`, `packaging`, and `.github` use `MIT`. See the [release plan](https://github.com/komawm/.github/blob/main/docs/releases.md).

## Next acceptance stages toward `v0.1.0`

Follow the [testing plan](https://github.com/komawm/docs/blob/main/docs/development/testing.md) in strict order:

1. **Nested compositor & multi-client stress validation**: Exercise `koma --winit` with multiple Wayland/XWayland clients, `Phodopus` hot reload, and `Mod+G` human preemption barriers under interactive load.
2. **Physical GPU & `virgl` / dGPU KMS validation**: Verify `koma --tty` on real DRM/KMS hardware (and optional `virtio-vga-gl` / `egl-headless` VM sessions) without falling back to `llvmpipe`.
3. **Hardened `jikud` & live voice acceptance**: Validate `Landlock` sandboxing, live `PipeWire` audio streaming over `LiveSessionDriver`, and separately authorized physical-seat desktop workflows without replacing the active Hyprland host session during routine development.
