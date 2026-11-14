# Development guide

Clone [Koma](https://github.com/komawm/koma) as a normal independent Git repository. For a grouped checkout, use the [organization workspace setup](https://github.com/komawm/.github); Koma also works as a standalone clone. Phodopus remains an upstream Git dependency, with an optional separate checkout for explicitly scoped co-development. No submodule initialization is needed.

The incubation baseline across all six published `komawm` repositories is `v0.0.1`; stay on `0.0.x` until the first formal `0.1.0` release line is accepted. Install the Rust `1.100.0` channel and components named by `rust-toolchain.toml`, plus `just`, `git`, CarryCtx and Lefthook. Rust source uses the 2024 edition. Rust `1.100.0` is installed in the grouped workspace's user-owned `.targets` caches; source the [workspace environment helper](https://github.com/komawm/.github/blob/main/scripts/env.sh) before running product commands there. Standalone clones can install the pinned toolchain with their own Rustup setup. Build dependencies vary with features: the Smithay DRM/udev/libinput/libseat/EGL path requires Linux system development libraries; core model/protocol checks need no display server. The CI workflow and justfile document the build dependency baseline.

From a `koma` checkout:

```bash
just --list
just fmt-check
just check-core
just typecheck
just clippy
just test-core
just test
just hooks-install
```

The [justfile](https://github.com/komawm/koma/blob/main/justfile) is the command source of truth. At Koma commit `28f5d9513e8d2952c1522b8d8ae729f7d5574c50`, all nine `koma` crates pass `just fmt-check`, `just check-core`, `just typecheck`, `just clippy`, `just test-core`, `just test` (25 unit tests), `komactl gen-types`, and `koma --headless-check` under Rust `1.100.0`. In [koma-types](https://github.com/komawm/koma-types), `types/koma.lua` is reproduced directly from `komactl gen-types` at Koma revision `28f5d9513e8d2952c1522b8d8ae729f7d5574c50` (`generator_reproduced = true`). In [Jiku](https://github.com/komawm/jiku), the four library crates define pure-data contracts and unit tests for the Three-Driver architecture (`DecisionsDriver`, `TurnModelDriver`, `LiveSessionDriver`) and pass all workspace checks while remaining a library-only non-runnable scaffold prior to `v0.1.0`.

Use a repository-local CarryCtx identity/session and task before multi-step edits; see [AGENTS.md](https://github.com/komawm/koma/blob/main/AGENTS.md). Work in an isolated task branch/worktree, and capture progress, decisions, validation results and remaining work before ending the session. CI runs and independent acceptance attach to the exact revision being reviewed.

Read the [current-state inventory](https://github.com/komawm/docs/blob/main/docs/development/current-state.md) for verified compiler/test boundaries and the [testing plan](https://github.com/komawm/docs/blob/main/docs/development/testing.md) for display/hardware work. Compiler/unit-test verification, nested Winit rendering, disposable VM execution and physical-seat acceptance remain distinct claims.

Keep temporary artifacts in `/tmp/koma/`; retain durable verification logs and read-only reference clones (`recording/references/Hyprland`, `recording/references/niri`) under the workspace's ignored `recording/` directory. Use user-owned build/cache paths. Avoid changing installed sessions, drivers or system services during ordinary development setup.

The [Koma licensing policy](https://github.com/komawm/koma#license) uses GPL-3.0-or-later for all product crates, including the protocol crate. Jiku also uses GPL-3.0-or-later, koma-types uses Apache-2.0, and documentation and packaging infrastructure use MIT. Consult the [CarryCtx catalog](https://github.com/komawm/koma/blob/main/.carryctx/README.md) before dispatching or handing off work.
