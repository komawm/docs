set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

check: metadata links

metadata:
    python3 scripts/check.py

links:
    python3 scripts/check-links.py

hooks-install:
    lefthook install pre-commit
    carryctx hooks install --compose
