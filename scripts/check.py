#!/usr/bin/env python3
"""Check the documentation checkout's local metadata and license."""
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
for path in ROOT.rglob("*.toml"):
    if ".git" not in path.parts:
        with path.open("rb") as stream:
            tomllib.load(stream)
with (ROOT / "repo.toml").open("rb") as stream:
    metadata = tomllib.load(stream)
repo = metadata["repo"]
assert repo["repository"] == "https://github.com/komawm/docs", "repository URL mismatch"
assert repo["docs"] == repo["repository"] + "/tree/main/docs", "documentation URL mismatch"
assert metadata["licensing"] == {"content": "MIT"}, "documentation license must be MIT"
for name in ("README.md", "AGENTS.md", "justfile", ".carryctx/config.toml"):
    assert (ROOT / name).is_file(), f"missing {name}"
for name in ("ARCHITECTURE.md", "IPC_SPEC.md", "LUA_API_SPEC.md", "JIKU_ARCHITECTURE.md", "JIKU_CONFIG_SPEC.md"):
    assert (ROOT / "docs" / name).is_file(), f"missing canonical specification {name}"
assert sorted(path.name for path in ROOT.glob("LICENSE*")) == ["LICENSE"], "use one LICENSE"
license_text = (ROOT / "LICENSE").read_text()
assert "MIT License" in license_text and "Permission is hereby granted" in license_text, "missing MIT license text"
print(f"{repo['name']}: local metadata and MIT license valid")
