# Documentation delivery

1. Work inside this repository with a named CarryCtx agent/session and scoped task. Record cross-repository dependencies before changing shared contracts.
2. Preserve unrelated work. Delegate through isolated worktrees after the first commit; before that, use explicitly disjoint file scopes.
3. Run `just check` locally, inspect changed Markdown and links, and record the actual results. Product compilation and runtime checks belong to the owning product repository.
4. Checkpoint evidence and remaining work, end sessions cleanly, and independently inspect task state and files before completion.
5. Documentation uses direct updates without PRs, CI/CD, CodeQL or bot-review requirements. Commits and remote publication remain within the user's task authorization.
