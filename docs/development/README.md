# Development guide

Clone [Koma](https://github.com/komawm/koma) as a normal independent Git repository. For a grouped checkout, use the [organization workspace setup](https://github.com/komawm/.github); Koma also works as a standalone clone. Phodopus remains an upstream Git dependency, with an optional separate checkout for explicitly scoped co-development. No submodule initialization is needed.

The incubation version is `0.0.1`; use `0.0.x` until the first formal `0.1.0` release line. Install the Rust `1.100.0` channel and components named by `rust-toolchain.toml`, plus `just`, `git`, CarryCtx and Lefthook. Rust source uses the 2024 edition. Rust `1.100.0` is now installed in the grouped workspace's user-owned `.targets` caches. Opt into the [workspace environment helper](https://github.com/komawm/.github/blob/main/scripts/env.sh) before running product commands there. Standalone clones can install the pinned toolchain with their own Rustup setup. Earlier structural probes under `1.98.1` remain fallback evidence, and are separate from the later target-compiler results. Build dependencies vary with features: the Smithay DRM/udev/libinput/libseat/EGL path requires Linux system development libraries; core model/protocol checks need no display server. The CI workflow and justfile document the build dependency baseline. Do not copy Bitty's terminal, plugin or cross-platform matrix wholesale into compositor acceptance.

From this checkout:

```bash
just --list
just fmt-check
just check-core
just test-core
just hooks-install
```

The [justfile](https://github.com/komawm/koma/blob/main/justfile) is the command source of truth. Full checks must cover enabled Phodopus and Smithay paths in addition to the headless/core baseline. Dependency resolution still examines workspace Git dependencies even for selected packages, so an unavailable revision or package must be fixed as a separate documented dependency change.

Use a repository-local CarryCtx identity/session and task before multi-step edits; see [AGENTS.md](https://github.com/komawm/koma/blob/main/AGENTS.md). After a baseline commit, work in a task branch/worktree. Capture progress, decisions, validation results and unresolved work before ending the session. CI runs and independent acceptance attach to the exact revision being reviewed.

Read the [current-state inventory](https://github.com/komawm/docs/blob/main/docs/development/current-state.md) for initial boundaries and the [testing plan](https://github.com/komawm/docs/blob/main/docs/development/testing.md) for display/hardware work. Build success, nested rendering, VM execution and physical-seat acceptance are separate results.

Keep temporary artifacts in `/tmp/koma/`; retain useful evidence under the workspace's ignored `recording/` directory. Use user-owned build/cache paths. Avoid changing installed sessions, drivers or system services during ordinary development setup.

The [Koma licensing policy](https://github.com/komawm/koma#license) uses GPL-3.0-or-later for all product crates, including the protocol crate. Jiku also uses GPL-3.0-or-later, koma-types uses Apache-2.0, and documentation and packaging infrastructure use MIT. Consult the [CarryCtx catalog](https://github.com/komawm/koma/blob/main/.carryctx/README.md) before dispatching or handing off work. Keep local initialization and an explicitly authorized remote Issue/PR/release lifecycle separate.

Koma now includes a Cargo.lock generated with Rust 1.100.0; use locked repository gates and review dependency changes deliberately. Solver resolution does not establish full source/API compatibility. The actual Rust 1.100.0 formatter/core-test gates fail on inherited source issues; consult the current-state inventory for exact boundaries and retained evidence. The LuaLS snapshot in koma-types has not yet been reproduced from the generator.
