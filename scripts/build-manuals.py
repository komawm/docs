#!/usr/bin/env python3
"""Validate 1:1 locale parity and build deterministic R2 manual bundles for Koma & Jiku."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
MANUAL_ROOT = ROOT / "manual"
LOCALES = ("en", "zh-CN", "ja")
SURFACES = ("koma", "jiku")
SAFE_REL = re.compile(r"^[a-z0-9][a-z0-9/_-]*\.md$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_and_validate_surface(surface: str) -> dict:
    sdir = MANUAL_ROOT / surface
    manifest_path = sdir / "manifest.toml"
    if not manifest_path.is_file():
        raise SystemExit(f"missing manual manifest: {manifest_path}")
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("surface") != surface:
        raise SystemExit(f"{manifest_path}: surface must be {surface!r}")
    if tuple(manifest.get("locales", ())) != LOCALES:
        raise SystemExit(f"{manifest_path}: locales must be {list(LOCALES)}")

    sections = manifest.get("sections", [])
    if not sections:
        raise SystemExit(f"{manifest_path}: sections cannot be empty")

    expected_paths: set[str] = set()
    seen_slugs: set[str] = set()
    normalized_sections = []

    for section in sections:
        sec_id = section["id"]
        titles = section["title"]
        for loc in LOCALES:
            if not titles.get(loc):
                raise SystemExit(f"{surface}: section {sec_id!r} missing {loc} title")
        norm_items = []
        for item in section.get("items", []):
            rel_path = item["path"]
            slug = f"{sec_id}/{item['slug']}"
            if not SAFE_REL.fullmatch(rel_path):
                raise SystemExit(f"{surface}: unsafe manual path {rel_path!r}")
            if slug in seen_slugs:
                raise SystemExit(f"{surface}: duplicate route slug {slug!r}")
            seen_slugs.add(slug)
            expected_paths.add(rel_path)
            for loc in LOCALES:
                if not item.get("title", {}).get(loc):
                    raise SystemExit(f"{surface}: item {slug!r} missing {loc} title")
                md_file = sdir / loc / rel_path
                if not md_file.is_file():
                    raise SystemExit(f"{surface}: missing localized file {md_file.relative_to(ROOT)}")
                body = md_file.read_text(encoding="utf-8").strip()
                if not body.startswith("# "):
                    raise SystemExit(f"{surface}: {md_file.relative_to(ROOT)} must start with an H1 heading")
            norm_items.append(
                {
                    "slug": item["slug"],
                    "path": rel_path,
                    "title": item["title"],
                }
            )
        normalized_sections.append(
            {
                "id": sec_id,
                "title": titles,
                "items": norm_items,
            }
        )

    # Ensure no locale directory (en, zh-CN, ja) carries orphan .md files outside manifest.toml
    for loc in LOCALES:
        loc_root = sdir / loc
        actual = {p.relative_to(loc_root).as_posix() for p in loc_root.rglob("*.md")}
        if actual != expected_paths:
            missing = sorted(expected_paths - actual)
            extra = sorted(actual - expected_paths)
            raise SystemExit(
                f"{surface}/{loc} parity mismatch: missing={missing}, unlisted={extra}"
            )

    return {
        "schema": 1,
        "surface": surface,
        "version": manifest["version"],
        "locales": list(LOCALES),
        "sections": normalized_sections,
    }


def build_deterministic_targz(surface: str, locale: str, expected_paths: list[str]) -> bytes:
    loc_root = MANUAL_ROOT / surface / locale
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w", format=tarfile.PAX_FORMAT) as tf:
        root_info = tarfile.TarInfo(name=f"{locale}/")
        root_info.type = tarfile.DIRTYPE
        root_info.mode = 0o755
        root_info.uid = 0
        root_info.gid = 0
        root_info.uname = ""
        root_info.gname = ""
        root_info.mtime = 0
        tf.addfile(root_info)

        for rel in sorted(expected_paths):
            data = (loc_root / rel).read_bytes()
            info = tarfile.TarInfo(name=f"{locale}/{rel}")
            info.size = len(data)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            tf.addfile(info, io.BytesIO(data))

    gz_buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz_buf, compresslevel=9, mtime=0) as gz:
        gz.write(raw_tar.getvalue())
    return gz_buf.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate parity only without writing bundles")
    parser.add_argument("--surface", choices=("all", "koma", "jiku"), default="all")
    parser.add_argument("--revision", default="0000000000000000000000000000000000000000")
    parser.add_argument("--out", type=Path, help="Output directory for R2 bundles")
    args = parser.parse_args()

    selected = SURFACES if args.surface == "all" else (args.surface,)
    validated = {s: load_and_validate_surface(s) for s in selected}

    if args.check:
        for s, meta in validated.items():
            count = sum(len(sec["items"]) for sec in meta["sections"])
            print(f"manual/{s}: verified {count} page(s) across {LOCALES}")
        return

    if args.out is None:
        parser.error("--out is required unless --check is set")

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    short_rev = args.revision[:12]
    checksum_lines: list[str] = []
    dispatch_surfaces: dict[str, dict] = {}

    for surface, manifest_obj in validated.items():
        version_dir = f"v{manifest_obj['version']}-{short_rev}"
        bundle_dir = out / surface / version_dir
        bundle_dir.mkdir(parents=True, exist_ok=True)

        paths = [item["path"] for sec in manifest_obj["sections"] for item in sec["items"]]
        manifest_bytes = (json.dumps(manifest_obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        manifest_file = bundle_dir / "manifest.json"
        manifest_file.write_bytes(manifest_bytes)
        manifest_sha = sha256_bytes(manifest_bytes)
        checksum_lines.append(f"{manifest_sha}  {manifest_file.relative_to(out).as_posix()}")

        bundles_meta: dict[str, dict[str, str]] = {}
        for loc in LOCALES:
            tgz = build_deterministic_targz(surface, loc, paths)
            tgz_file = bundle_dir / f"{loc}.tar.gz"
            tgz_file.write_bytes(tgz)
            digest = sha256_bytes(tgz)
            bundles_meta[loc] = {
                "path": f"{version_dir}/{loc}.tar.gz",
                "sha256": digest,
            }
            checksum_lines.append(f"{digest}  {tgz_file.relative_to(out).as_posix()}")

        latest_obj = {
            "schema": 1,
            "surface": surface,
            "version": manifest_obj["version"],
            "revision": args.revision,
            "version_dir": version_dir,
            "manifest": {
                "path": f"{version_dir}/manifest.json",
                "sha256": manifest_sha,
            },
            "bundles": bundles_meta,
        }
        latest_bytes = (json.dumps(latest_obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        latest_file = out / surface / "latest.json"
        latest_file.write_bytes(latest_bytes)
        checksum_lines.append(f"{sha256_bytes(latest_bytes)}  {latest_file.relative_to(out).as_posix()}")
        dispatch_surfaces[surface] = latest_obj

    dispatch_payload = {
        "schema": 1,
        "revision": args.revision,
        "surfaces": dispatch_surfaces,
    }
    dispatch_bytes = (json.dumps(dispatch_payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (out / "dispatch-payload.json").write_bytes(dispatch_bytes)
    (out / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"Built R2 manual bundles in {out} for {list(validated)}")


if __name__ == "__main__":
    main()
