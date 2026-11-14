# Koma documentation

This repository owns the canonical architecture, protocol, Lua API, Jiku design and shared development documentation for [Koma](https://github.com/komawm/koma) and its companion repositories. It is an independent Git checkout within the [Koma organization workspace](https://github.com/komawm/.github); no submodules are required.

| Document | Scope |
| --- | --- |
| [Koma architecture](https://github.com/komawm/docs/blob/main/docs/ARCHITECTURE.md) | Compositor mechanism/policy separation, layouts, rendering, input and session targets. |
| [IPC specification](https://github.com/komawm/docs/blob/main/docs/IPC_SPEC.md) | Admin/agent sockets, framing, FD transport, capabilities and epoch contracts. |
| [Lua API](https://github.com/komawm/docs/blob/main/docs/LUA_API_SPEC.md) | Configuration, host functions, rules, bindings and macros. |
| [Jiku architecture](https://github.com/komawm/docs/blob/main/docs/JIKU_ARCHITECTURE.md) | Proposed desktop orchestration runtime, sandbox and integrations. |
| [Jiku configuration](https://github.com/komawm/docs/blob/main/docs/JIKU_CONFIG_SPEC.md) | Proposed provider, memory, voice, skill and CLI configuration. |
| [Development guide](https://github.com/komawm/docs/blob/main/docs/development/README.md) | Repository setup, toolchain and local work. |
| [Current state](https://github.com/komawm/docs/blob/main/docs/development/current-state.md) | Imported implementation and unresolved acceptance boundaries. |
| [Testing plan](https://github.com/komawm/docs/blob/main/docs/development/testing.md) | Core, nested display, VM and physical-seat evidence. |

The existing specifications retain their design baseline labels. Design status, source implementation, compilation, runtime observations and security/performance acceptance remain distinct claims. [Jiku](https://github.com/komawm/jiku) currently contains templates and a component boundary, with no implemented daemon. [koma-types](https://github.com/komawm/koma-types) owns the checked-in LuaLS snapshot; its generator remains in Koma.

Run `just check` locally before updating Markdown; see [AGENTS.md](https://github.com/komawm/docs/blob/main/AGENTS.md) for task and evidence policy. This documentation repository uses direct updates without pull requests or CI/CD. Product build and release checks belong to the product and packaging repositories.

This repository uses the [MIT license](https://github.com/komawm/docs/blob/main/LICENSE).
