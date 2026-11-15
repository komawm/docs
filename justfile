set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

check: metadata links manuals

metadata:
    python3 scripts/check.py

links:
    python3 scripts/check-links.py

manuals:
    python3 scripts/build-manuals.py --check

hooks-install:
    lefthook install pre-commit
    carryctx hooks install --compose
