# Koma documentation guidance

This repository owns canonical Koma and Jiku specifications and shared development documentation at [komawm/docs](https://github.com/komawm/docs). The workspace checkout is named `koma-docs`. Product source belongs to [Koma](https://github.com/komawm/koma) and [Jiku](https://github.com/komawm/jiku), and LuaLS definitions to [koma-types](https://github.com/komawm/koma-types). Read the [workspace map](https://github.com/komawm/.github/blob/main/workspace/workspace.toml) and affected contracts before editing.

Keep changes focused on documentation. Preserve design status labels and distinguish requirements, proposals, implementation, compiler results, runtime observations and acceptance evidence. Coordinate contract changes with the owning implementation repository. This repository uses [MIT](https://github.com/komawm/docs/blob/main/LICENSE); Koma and Jiku use GPL-3.0-or-later, koma-types uses Apache-2.0, and packaging infrastructure uses MIT. Preserve attribution and external dependency provenance.

Run `just check` locally for Markdown links and repository metadata. Documentation uses direct updates without PRs, CI/CD, CodeQL or bot-review requirements. Product checks and release delivery belong to their owning repositories. Publishing still follows the user's authorized scope.

Use this checkout's CarryCtx database, a named agent/session and scoped tasks before multi-step edits. Record dependencies and checkpoints, end sessions cleanly, and read task state and files back before acceptance. Delegated work uses isolated worktrees after the first commit; before that, keep shared-checkout scopes disjoint. See the [local CarryCtx guide](https://github.com/komawm/docs/blob/main/.carryctx/README.md).

Use canonical HTTPS links in README and AGENTS files. Keep disposable files under `/tmp/koma/` and retained evidence under the workspace's ignored `recording/`; never publish raw CarryCtx snapshots. Documentation work grants no authority to alter desktop sessions, host devices, system services or external Phodopus state.
