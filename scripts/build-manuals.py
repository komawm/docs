#!/usr/bin/env python3
"""Validate 1:1 locale parity, convert math to CSP-safe MathML, and build R2 bundles."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
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
MATHML_NS = "http://www.w3.org/1998/Math/MathML"

TEX_SYMBOLS = {
    "Delta": "\u0394",
    "Gamma": "\u0393",
    "Theta": "\u0398",
    "Lambda": "\u039b",
    "Pi": "\u03a0",
    "Sigma": "\u03a3",
    "Phi": "\u03a6",
    "Omega": "\u03a9",
    "alpha": "\u03b1",
    "beta": "\u03b2",
    "gamma": "\u03b3",
    "delta": "\u03b4",
    "epsilon": "\u03b5",
    "varepsilon": "\u03b5",
    "zeta": "\u03b6",
    "eta": "\u03b7",
    "theta": "\u03b8",
    "lambda": "\u03bb",
    "mu": "\u03bc",
    "pi": "\u03c0",
    "rho": "\u03c1",
    "sigma": "\u03c3",
    "tau": "\u03c4",
    "phi": "\u03c6",
    "omega": "\u03c9",
    "infty": "\u221e",
    "cdot": "\u00b7",
    "times": "\u00d7",
    "pm": "\u00b1",
    "le": "\u2264",
    "leq": "\u2264",
    "ge": "\u2265",
    "geq": "\u2265",
    "neq": "\u2260",
    "approx": "\u2248",
    "in": "\u2208",
    "notin": "\u2209",
    "to": "\u2192",
    "rightarrow": "\u2192",
    "leftarrow": "\u2190",
    "lceil": "\u2308",
    "rceil": "\u2309",
    "lfloor": "\u230a",
    "rfloor": "\u230b",
    ",": "\u2009",
    ";": "\u2005",
    "quad": "\u2001",
    "{": "{",
    "}": "}",
}
OPERATOR_CMDS = {
    "cdot",
    "times",
    "pm",
    "le",
    "leq",
    "ge",
    "geq",
    "neq",
    "approx",
    "in",
    "notin",
    "to",
    "rightarrow",
    "leftarrow",
    "lceil",
    "rceil",
    "lfloor",
    "rfloor",
    "{",
    "}",
}
ACCENT_CMDS = {
    "dot": "\u02d9",
    "ddot": "\u00a8",
    "bar": "\u00af",
    "hat": "^",
    "vec": "\u2192",
    "tilde": "~",
}


class _TexParser:
    def __init__(self, src: str) -> None:
        self.src = src
        self.pos = 0
        self.n = len(src)

    def skip_ws(self) -> None:
        while self.pos < self.n and self.src[self.pos].isspace():
            self.pos += 1

    def parse_group_text(self) -> str:
        self.skip_ws()
        if self.pos < self.n and self.src[self.pos] == "{":
            self.pos += 1
            depth = 1
            start = self.pos
            while self.pos < self.n and depth > 0:
                ch = self.src[self.pos]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        text = self.src[start:self.pos]
                        self.pos += 1
                        return text
                self.pos += 1
            return self.src[start:]
        if self.pos < self.n:
            ch = self.src[self.pos]
            self.pos += 1
            return ch
        return ""

    def parse_expr(self, stop_on_brace: bool = False) -> str:
        nodes: list[str] = []
        while self.pos < self.n:
            self.skip_ws()
            if self.pos >= self.n:
                break
            ch = self.src[self.pos]
            if stop_on_brace and ch == "}":
                self.pos += 1
                break
            node = self.parse_scripted_atom()
            if node:
                nodes.append(node)
        if not nodes:
            return "<mrow></mrow>"
        if len(nodes) == 1:
            return nodes[0]
        return f"<mrow>{''.join(nodes)}</mrow>"

    def parse_scripted_atom(self) -> str:
        base = self.parse_atom()
        if not base:
            return ""
        sub: str | None = None
        sup: str | None = None
        while self.pos < self.n:
            self.skip_ws()
            if self.pos >= self.n:
                break
            marker = self.src[self.pos]
            if marker == "_" and sub is None:
                self.pos += 1
                sub = self.parse_atom()
            elif marker == "^" and sup is None:
                self.pos += 1
                sup = self.parse_atom()
            else:
                break
        if sub is not None and sup is not None:
            return f"<msubsup>{base}{sub}{sup}</msubsup>"
        if sub is not None:
            return f"<msub>{base}{sub}</msub>"
        if sup is not None:
            return f"<msup>{base}{sup}</msup>"
        return base

    def parse_atom(self) -> str:
        self.skip_ws()
        if self.pos >= self.n:
            return ""
        ch = self.src[self.pos]
        if ch == "{":
            self.pos += 1
            return self.parse_expr(stop_on_brace=True)
        if ch == "\\":
            self.pos += 1
            if self.pos >= self.n:
                return ""
            if not self.src[self.pos].isalpha():
                cmd = self.src[self.pos]
                self.pos += 1
            else:
                start = self.pos
                while self.pos < self.n and self.src[self.pos].isalpha():
                    self.pos += 1
                cmd = self.src[start:self.pos]
            if cmd == "frac":
                num = self.parse_atom()
                den = self.parse_atom()
                return f"<mfrac>{num}{den}</mfrac>"
            if cmd == "sqrt":
                body = self.parse_atom()
                return f"<msqrt>{body}</msqrt>"
            if cmd == "text":
                txt = html.escape(self.parse_group_text())
                return f"<mtext>{txt}</mtext>"
            if cmd in ACCENT_CMDS:
                base = self.parse_atom()
                mark = html.escape(ACCENT_CMDS[cmd])
                return f"<mover>{base}<mo>{mark}</mo></mover>"
            if cmd in TEX_SYMBOLS:
                sym = html.escape(TEX_SYMBOLS[cmd])
                tag = "mo" if cmd in OPERATOR_CMDS else ("mtext" if cmd in {",", ";", "quad"} else "mi")
                return f"<{tag}>{sym}</{tag}>"
            return f"<mi>{html.escape(cmd)}</mi>"
        if ch.isdigit():
            start = self.pos
            while self.pos < self.n and (self.src[self.pos].isdigit() or self.src[self.pos] == "."):
                self.pos += 1
            return f"<mn>{html.escape(self.src[start:self.pos])}</mn>"
        if ch.isalpha():
            self.pos += 1
            return f"<mi>{html.escape(ch)}</mi>"
        self.pos += 1
        return f"<mo>{html.escape(ch)}</mo>"


def tex_to_mathml(expr: str, block: bool) -> str:
    body = _TexParser(expr.strip()).parse_expr(stop_on_brace=False)
    if block:
        return (
            f'<div class="math-block"><math display="block" xmlns="{MATHML_NS}">'
            f"{body}</math></div>"
        )
    return f'<span class="math-inline"><math xmlns="{MATHML_NS}">{body}</math></span>'


_INLINE_MATH_RE = re.compile(r"(?<!\\)(?<!\$)\$(?!\s)([^\n$]+?)(?<!\s)(?<!\\)\$(?!\$|\d)")
_DISPLAY_MATH_RE = re.compile(r"(?<!\\)\$\$\s*([\s\S]+?)\s*(?<!\\)\$\$")
_CODE_SPAN_RE = re.compile(r"(`+)([\s\S]*?)\1")


def _replace_math_in_prose(segment: str) -> str:
    placeholders: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        idx = len(placeholders)
        placeholders.append(match.group(0))
        return f"\x00CODE{idx}\x00"

    masked = _CODE_SPAN_RE.sub(stash_code, segment)
    masked = _DISPLAY_MATH_RE.sub(lambda m: tex_to_mathml(m.group(1), block=True), masked)
    masked = _INLINE_MATH_RE.sub(lambda m: tex_to_mathml(m.group(1), block=False), masked)

    if "$$" in masked:
        raise SystemExit("unterminated display math block ($$) outside fenced code block")
    if re.search(r"\sstyle\s*=", masked, flags=re.IGNORECASE):
        raise SystemExit("prohibited inline style= attribute generated in manual math output")
    if re.search(r"<script\b", masked, flags=re.IGNORECASE):
        raise SystemExit("prohibited <script> tag generated in manual math output")

    for idx, original in enumerate(placeholders):
        masked = masked.replace(f"\x00CODE{idx}\x00", original)
    return masked


def render_markdown_csp_safe(markdown_text: str) -> str:
    """Convert non-code $$...$$ / $...$ LaTeX formulas into CSP-safe HTML5 MathML."""
    out_parts: list[str] = []
    prose_buf: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0

    for line in markdown_text.splitlines(keepends=True):
        stripped = line.lstrip()
        if not in_fence:
            m = re.match(r"^(`{3,}|~{3,})", stripped)
            if m:
                if prose_buf:
                    out_parts.append(_replace_math_in_prose("".join(prose_buf)))
                    prose_buf.clear()
                in_fence = True
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                out_parts.append(line)
                continue
            prose_buf.append(line)
        else:
            out_parts.append(line)
            if re.match(rf"^{re.escape(fence_char)}{{{fence_len},}}\s*$", stripped):
                in_fence = False

    if prose_buf:
        out_parts.append(_replace_math_in_prose("".join(prose_buf)))
    return "".join(out_parts)


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
                raw_text = md_file.read_text(encoding="utf-8")
                if not raw_text.strip().startswith("# "):
                    raise SystemExit(f"{surface}: {md_file.relative_to(ROOT)} must start with an H1 heading")
                render_markdown_csp_safe(raw_text)
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


def build_deterministic_targz(
    surface: str, locale: str, expected_paths: list[str]
) -> tuple[bytes, dict[str, bytes]]:
    loc_root = MANUAL_ROOT / surface / locale
    rendered_map: dict[str, bytes] = {}
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
            raw_text = (loc_root / rel).read_text(encoding="utf-8")
            rendered_text = render_markdown_csp_safe(raw_text)
            rendered_map[rel] = rendered_text.encode("utf-8")
            data = raw_text.encode("utf-8")
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
    return gz_buf.getvalue(), rendered_map


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

        flat_items = [
            (sec["id"], sec["title"], item)
            for sec in manifest_obj["sections"]
            for item in sec["items"]
        ]
        paths = [item["path"] for _, _, item in flat_items]
        manifest_bytes = (json.dumps(manifest_obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        manifest_file = bundle_dir / "manifest.json"
        manifest_file.write_bytes(manifest_bytes)
        manifest_sha = sha256_bytes(manifest_bytes)
        checksum_lines.append(f"{manifest_sha}  {manifest_file.relative_to(out).as_posix()}")

        bundles_meta: dict[str, dict[str, str]] = {}
        for loc in LOCALES:
            tgz, rendered_map = build_deterministic_targz(surface, loc, paths)
            tgz_file = bundle_dir / f"{loc}.tar.gz"
            tgz_file.write_bytes(tgz)
            digest = sha256_bytes(tgz)
            bundles_meta[loc] = {
                "path": f"{version_dir}/{loc}.tar.gz",
                "sha256": digest,
            }
            checksum_lines.append(f"{digest}  {tgz_file.relative_to(out).as_posix()}")

            for sec_id, sec_titles, item in flat_items:
                rel_md = item["path"]
                md_bytes = rendered_map[rel_md]
                page_obj = {
                    "schema": 1,
                    "surface": surface,
                    "locale": loc,
                    "version": manifest_obj["version"],
                    "revision": args.revision,
                    "section_id": sec_id,
                    "section_title": sec_titles[loc],
                    "slug": item["slug"],
                    "path": rel_md,
                    "title": item["title"][loc],
                    "markdown": md_bytes.decode("utf-8"),
                    "sha256": sha256_bytes(md_bytes),
                }
                page_bytes = (
                    json.dumps(page_obj, indent=2, ensure_ascii=False) + "\n"
                ).encode("utf-8")
                page_file = out / surface / loc / Path(rel_md).with_suffix(".json")
                page_file.parent.mkdir(parents=True, exist_ok=True)
                page_file.write_bytes(page_bytes)
                checksum_lines.append(
                    f"{sha256_bytes(page_bytes)}  {page_file.relative_to(out).as_posix()}"
                )

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
