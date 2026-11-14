# Initial source inventory

This inventory describes the imported source on 2026-11-14. Refresh it when build and runtime acceptance changes. Detailed local initialization logs are retained in the workspace's ignored `recording/` directory rather than published as source.

## What exists

The Cargo manifest lists nine packages: five libraries (`koma-proto`, `koma-model`, `koma-lua`, `koma-render`, `koma-seat`) and four binaries (`koma`, `komactl`, `koma-mcp`, `koma-overview`). They contain implementation source and inline unit tests. The compositor has explicit Winit, TTY and headless-check launch modes; Lua/renderer/layer-shell integrations have Cargo feature boundaries. Default compositor features include both Winit and TTY integration.

The model includes Dwindle and scrolling/tabbed structures, deck/stash and floating state, animation, rules, leases and clocks. Protocol source covers framing, capabilities, epoch identifiers, RPC schemas and Unix FD transport. The Lua layer includes registry/type generation, a Phodopus bridge and host-operation scheduler. The render and compositor trees include shaders, scene composition, input/Wayland handlers, IPC, configuration reload and Xwayland integration. These are source inventory statements, not test results.

The initial import included five architecture/API specifications, Koma/Jiku examples, LuaLS definitions and session templates. Canonical specifications and shared development docs now live in koma-docs; Jiku examples/service templates live in jiku; the unchanged LuaLS snapshot lives in koma-types. Koma keeps its nine crates, configuration example and session integration resources.

## Boundaries that matter

- The separate Jiku repository contains four library-only, non-runnable scaffolding crates (`jikud`, `jiku`, `jiku-memory`, `jiku-tts`), configuration/service templates and an internal skills directory. No daemon/CLI is implemented. Provider, memory, voice and sandbox descriptions remain design targets; avatar integration is deferred.
- `--headless-check` currently reports a launch-path message; it does not initialize a display backend or prove a complete compositor state-machine, rendering, input, IPC or security test.
- Package descriptions and specs include latency, zero-copy, portability and sandbox guarantees. They need dedicated build/runtime measurements and adversarial acceptance. Do not infer them from names, comments or missing `todo!` markers.
- Koma pins Smithay to a Git revision and consumes Phodopus Git packages. A lockfile and dependency/API compatibility checks are required for a reproducible build baseline. Do not silently redirect production dependencies to a sibling checkout.
- The target is Rust 1.100.0 / Rust 2024. Rust 1.100.0 is installed in the grouped workspace's user-owned `.targets` caches, selected via the workspace environment helper. Earlier installed-1.98.1 structural probes remain historical fallback observations. Jiku's scaffold checks pass under the actual target compiler; they execute no agent behavior.
- The architecture mentions Linux/BSD targets. The initial development host is Arch Linux; this is not evidence of FreeBSD/OpenBSD support.
- Koma (including `koma-proto`) and Jiku use GPL-3.0-or-later; koma-types uses Apache-2.0; documentation and packaging infrastructure use MIT. Each repository has one `LICENSE`; preserve third-party provenance.

## Incubation and dependencies

The requested initial package version is `0.0.1`. Development stays on `0.0.x` until a first formal `0.1.0` release line is accepted. No version change alone is publication or release evidence.

Use the latest dependency versions that have been verified compatible with Koma. The inherited fixed Smithay Git revision is an explicit architecture/API compatibility exception; updating it requires a tested integration migration. Direct dependencies have been updated to the verified compatible resolution baseline; this does not establish that every inherited source API compiles. Rustix now uses 1.1.6, correcting the initial 0.38 assumption; protocol compilation succeeds with that manifest-only correction. The unused wgpu declaration was removed rather than retained as an unconsumed dependency. Phodopus's upstream identity and licensing stay independent; a sibling checkout is not an implicit source override.

## Initialization checks

Koma infrastructure validation passes metadata, workflow and helper-script checks. Jiku's four library-only scaffolds pass their full local checks with Rust 1.100.0 and a Cargo.lock; their zero-test suites do not establish a runnable daemon. Koma now has a generated Cargo.lock resolving 263 packages under Rust 1.100.0. It records the reviewed solver baseline with current compatible dependency selections and the explicit Smithay compatibility exception; this is dependency resolution evidence, not proof of source/API compatibility. The Rust 1.100.0 core test command compiles `koma-proto`, then fails in inherited `koma-model` source: layout/animation code uses `width`/`height` where `LogicalRect` defines `w`/`h`, and some code constructs `WindowId` as a tuple despite its struct representation. The observed run reports 125 library errors and 163 library-test errors; the suite does not reach passing tests.

The actual-target formatter gate also fails on inherited differences and a Lua recorder Rust string syntax error. These failures are source remediation work, not an unresolved compiler installation or missing lockfile. Full Rust quality and runtime acceptance remain open. Latest local logs are `koma-test-core-1.100.log` and `koma-fmt-1.100.log` under ignored initialization evidence.

Historical first probes found inherited formatter differences, a missing Koma Cargo.lock and an incomplete offline Phodopus Git cache. Keep those logs as baseline history, not current target-build results. The initial missing-lockfile/offline-cache condition is resolved. CarryCtx task `KOM-0003` retains the remaining Koma quality/remediation work.

## Acceptance work

Complete target-compiler tests and full workspace compilation before calling the imported source runnable. Run core/model tests, enabled Phodopus tests, renderer/compositor compilation and Clippy independently from document/configuration validation. Keep every failure with its exact command and revision.

Then follow the [testing plan](https://github.com/komawm/docs/blob/main/docs/development/testing.md): explicit nested Winit, disposable VM sessions and separately authorized physical-seat tests. No initialization result should be reported as a successful replacement for the current Hyprland session.

The LuaLS file in koma-types remains the imported snapshot. Its hash and syntax are checked, but regeneration from Koma's type generator is still pending. No public JSON Schema crate or schema generation is claimed by this initialization.
