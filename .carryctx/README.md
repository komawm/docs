# Documentation task context

The [configuration](https://github.com/komawm/docs/blob/main/.carryctx/config.toml) keeps this checkout's identity and local `just check` verification entry point. Its database lives in the Git common directory and must remain private. The [vendored skill](https://github.com/komawm/.github/blob/main/workspace/.agents/skills/use-carryctx/SKILL.md) explains CarryCtx commands.

Read the [delivery rules](https://github.com/komawm/docs/blob/main/.carryctx/rules/delivery.md), [documentation rules](https://github.com/komawm/docs/blob/main/.carryctx/rules/documentation.md), and [local workflow](https://github.com/komawm/docs/blob/main/.carryctx/workflows/local-development.md). Use named identities, scoped tasks, dependencies and checkpoints; inspect evidence before completion.

Documentation updates use local Markdown checks and direct repository updates. No PR, CI/CD or bot review is required. Remote publication follows explicit user authorization.
