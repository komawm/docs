# Testing and evidence

Koma is a window manager. Validate layers separately and record what each run actually exercised. Use the pinned justfile recipes for repeatable build/test gates. Retain revision, toolchain, command, feature flags, relevant environment, exit status and logs with each result. For visual tests, retain screenshots or video and describe observed behavior.

## 1. Core and integration baseline

Start with `just fmt-check`, `just check-core` and `just test-core`. These cover selected non-display components; inspect the recipe's package/feature arguments. Follow with full workspace checks and enabled Phodopus/Smithay integration. Cargo workspace resolution may require Git dependencies even when selected packages disable default features.

An unresolved dependency, unavailable native development library, compile error or failing test is a failed/blocked gate. Keep the baseline visible. Metadata validation and the `--headless-check` message do not substitute for unit tests or enabled-feature compilation.

## 2. Nested display session

After the compositor builds, run it with explicit `--winit` inside an existing graphical session using isolated configuration, runtime resources and test clients. Do not use `--session`: the session wrapper changes login/session environment and service lifecycle. Record backend, renderer/GPU, startup, first frame, client mapping, input/focus, layouts, config reload, shutdown and client cleanup. Keep epoch/preemption and protected-capture tests distinct from a visual smoke test.

The local host runs Arch Linux with Hyprland and a dedicated GPU. Check device, socket and session access inside the actual execution environment before starting. The initialization agent environment had neither `/dev/dri` nor `/dev/kvm`; host capabilities are not automatically available to the agent.

## 3. Disposable VM sessions

Use QEMU with a writable disk overlay and isolated test data. Discover installer images via `ISO_PATH`; never bake a host mount or a particular ISO filename into repository configuration. The packaging harnesses cover both `vm/arch-vm.sh` + `vm/koma-smoke.sh` (Arch Linux package install and live `koma --tty` Wayland protocol smoke) and `vm/freebsd-vm.sh` (FreeBSD `15.1-RELEASE` unattended ZFS/UFS installation and `cargo check`/`cargo test` portability verification). Locally observed images also include Debian, Fedora KDE, and openSUSE; other OS images do not establish a supported target.

Check KVM access, QEMU graphics/display options, guest kernel/userspace, seat/session manager and virtual GPU explicitly. Software emulation may serve limited smoke tests, but cannot stand in for hardware timing or GPU acceptance. Preserve the ISO identity/hash, QEMU invocation, guest installation notes, overlay location and screenshots/logs in ignored retained evidence. Do not modify source ISO images.

## 4. Physical seat and GPU

Plan physical-seat tests after nested and VM acceptance. They may require a spare VT/seat, DRM/input permissions and a GPU path. Keep a recovery route and confirm the intended session transition before stopping Hyprland, activating Koma's session resources, changing greetd or assigning hardware. User-owned builds and staging directories are preferred; system installation is a distinct deployment step.

Record hardware/driver/kernel, outputs, scale/refresh, render and scanout devices, input devices, hotplug, suspend/resume and exit behavior. Multi-GPU and latency claims require measurements on those paths. Core CI and VM rendering do not establish these results.

## Storage

Use `/tmp/koma/` for disposable intermediate files. Keep reproducible logs, captures, notes and VM overlays under the workspace's ignored `recording/` directory. It is local retained evidence, not a Git repository or CarryCtx database. Link accepted results into CarryCtx checkpoints; do not commit runtime sockets, tokens, credentials, raw state snapshots or VM images.
