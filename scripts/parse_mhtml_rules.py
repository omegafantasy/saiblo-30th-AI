#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
PARSED_DIR = DOCS_DIR / "mhtml_parsed"
ASSET_ROOT = DOCS_DIR / "mhtml_assets"

TARGETS = [
    ("ANTWar - Saiblo.mhtml", "antwar_game22"),
    ("Generals - Saiblo.mhtml", "generals_game35"),
    ("蚁洋陷役2 - Saiblo.mhtml", "antwar2_game48"),
]

EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


@dataclass
class ParsedMhtml:
    html: str
    cid_map: Dict[str, Tuple[str, bytes]]


def _detect_html_charset(payload: bytes, declared_charset: str | None) -> str | None:
    head = payload[:8192]

    # <meta charset="utf-8">
    m = re.search(br"<meta[^>]+charset\s*=\s*['\"]?\s*([A-Za-z0-9._-]+)\s*['\"]?", head, re.I)
    if m:
        try:
            return m.group(1).decode("ascii")
        except Exception:
            pass

    # <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    m = re.search(br"charset\s*=\s*([A-Za-z0-9._-]+)", head, re.I)
    if m:
        try:
            return m.group(1).decode("ascii")
        except Exception:
            pass

    if declared_charset:
        return declared_charset
    return None


def _decode_html_payload(payload: bytes, declared_charset: str | None) -> str:
    charset = _detect_html_charset(payload, declared_charset)

    candidates: List[str] = []
    if payload.startswith(b"\xef\xbb\xbf"):
        candidates.append("utf-8-sig")
    if charset:
        candidates.append(charset)
    if declared_charset and declared_charset not in candidates:
        candidates.append(declared_charset)

    # Common fallbacks: prefer utf-8 for Saiblo pages.
    for enc in ("utf-8", "gb18030", "gbk", "big5", "latin1"):
        if enc not in candidates:
            candidates.append(enc)

    for enc in candidates:
        try:
            return payload.decode(enc)
        except Exception:
            continue
    return payload.decode("utf-8", errors="replace")


class RulesHtmlToMd(HTMLParser):
    def __init__(self, src_map: Dict[str, str]):
        super().__init__(convert_charrefs=True)
        self.src_map = src_map
        self.out: List[str] = []

        self.heading_level: int | None = None
        self.heading_buf: List[str] = []

        self.link_href: str | None = None
        self.link_buf: List[str] = []

        self.inline_code_depth = 0

        self.list_depth = 0

        self.in_pre = False
        self.pre_buf: List[str] = []
        self.pre_lang = ""

        self.in_table = False
        self.table_rows: List[List[str]] = []
        self.current_row: List[str] | None = None
        self.current_cell: List[str] | None = None

    def _attrs(self, attrs: List[Tuple[str, str | None]]) -> Dict[str, str]:
        return {k: (v or "") for k, v in attrs}

    def _emit(self, s: str) -> None:
        if s:
            self.out.append(s)

    def _emit_block_sep(self) -> None:
        text = "".join(self.out)
        if not text.endswith("\n\n"):
            if text.endswith("\n"):
                self.out.append("\n")
            else:
                self.out.append("\n\n")

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str | None]]) -> None:
        a = self._attrs(attrs)

        if self.in_table:
            if tag == "tr":
                self.current_row = []
            elif tag in ("td", "th"):
                self.current_cell = []
            elif tag == "br" and self.current_cell is not None:
                self.current_cell.append("\n")
            return

        if self.in_pre:
            if tag == "br":
                self.pre_buf.append("\n")
            elif tag == "code":
                cls = a.get("class", "")
                m = re.search(r"language-([a-zA-Z0-9_+-]+)", cls)
                if m:
                    self.pre_lang = m.group(1)
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.heading_level = int(tag[1])
            self.heading_buf = []
            return

        if tag == "p":
            self._emit_block_sep()
            return

        if tag in ("ul", "ol"):
            self.list_depth += 1
            self._emit_block_sep()
            return

        if tag == "li":
            indent = "  " * max(0, self.list_depth - 1)
            self._emit(f"{indent}- ")
            return

        if tag == "br":
            self._emit("\n")
            return

        if tag == "pre":
            self.in_pre = True
            self.pre_buf = []
            self.pre_lang = ""
            self._emit_block_sep()
            return

        if tag == "code":
            self.inline_code_depth += 1
            self._emit("`")
            return

        if tag == "a":
            self.link_href = a.get("href", "")
            self.link_buf = []
            return

        if tag == "img":
            src = a.get("src", "")
            src = self.src_map.get(src, src)
            alt = a.get("alt", "")
            self._emit(f"![{alt}]({src})")
            return

        if tag == "table":
            self.in_table = True
            self.table_rows = []
            self.current_row = None
            self.current_cell = None
            self._emit_block_sep()
            return

    def handle_endtag(self, tag: str) -> None:
        if self.in_table:
            if tag in ("td", "th"):
                if self.current_row is not None and self.current_cell is not None:
                    cell = "".join(self.current_cell).strip().replace("\n", " ")
                    self.current_row.append(re.sub(r"\s+", " ", cell))
                    self.current_cell = None
            elif tag == "tr":
                if self.current_row:
                    self.table_rows.append(self.current_row)
                self.current_row = None
            elif tag == "table":
                self._emit(self._format_table(self.table_rows))
                self._emit_block_sep()
                self.in_table = False
                self.table_rows = []
            return

        if self.in_pre:
            if tag == "pre":
                code = "".join(self.pre_buf).strip("\n")
                lang = self.pre_lang
                self._emit(f"```{lang}\n{code}\n```")
                self._emit_block_sep()
                self.in_pre = False
                self.pre_buf = []
                self.pre_lang = ""
            return

        if self.heading_level is not None and tag == f"h{self.heading_level}":
            text = re.sub(r"\s+", " ", "".join(self.heading_buf).strip())
            if text:
                self._emit_block_sep()
                self._emit(f"{'#' * self.heading_level} {text}")
                self._emit_block_sep()
            self.heading_level = None
            self.heading_buf = []
            return

        if tag == "p":
            self._emit_block_sep()
            return

        if tag in ("ul", "ol"):
            self.list_depth = max(0, self.list_depth - 1)
            self._emit_block_sep()
            return

        if tag == "li":
            self._emit("\n")
            return

        if tag == "code" and self.inline_code_depth > 0:
            self.inline_code_depth -= 1
            self._emit("`")
            return

        if tag == "a" and self.link_href is not None:
            text = "".join(self.link_buf).strip()
            href = self.link_href
            if text:
                self._emit(f"[{text}]({href})")
            else:
                self._emit(href)
            self.link_href = None
            self.link_buf = []
            return

    def handle_data(self, data: str) -> None:
        if not data:
            return

        if self.in_table:
            if self.current_cell is not None:
                self.current_cell.append(data)
            return

        if self.in_pre:
            self.pre_buf.append(data)
            return

        if self.heading_level is not None:
            self.heading_buf.append(data)
            return

        if self.link_href is not None:
            self.link_buf.append(data)
            return

        if self.inline_code_depth > 0:
            self._emit(data)
            return

        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self._emit(text)

    def _format_table(self, rows: List[List[str]]) -> str:
        if not rows:
            return ""
        cols = max(len(r) for r in rows)
        norm = [r + [""] * (cols - len(r)) for r in rows]
        lines = []
        lines.append("| " + " | ".join(norm[0]) + " |")
        lines.append("| " + " | ".join(["---"] * cols) + " |")
        for r in norm[1:]:
            lines.append("| " + " | ".join(r) + " |")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        text = "".join(self.out)
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def parse_mhtml(path: Path) -> ParsedMhtml:
    msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    html = ""
    cid_map: Dict[str, Tuple[str, bytes]] = {}

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue

        ctype = part.get_content_type()
        content_id = (part.get("Content-ID") or "").strip()
        if content_id.startswith("<") and content_id.endswith(">"):
            content_id = content_id[1:-1]

        payload = part.get_payload(decode=True) or b""

        if ctype == "text/html" and not html:
            html = _decode_html_payload(payload, part.get_content_charset())

        if content_id and payload:
            cid_map[content_id] = (ctype, payload)

    return ParsedMhtml(html=html, cid_map=cid_map)


def extract_rules_fragment(html: str) -> str:
    start = html.find("<h1 id=")
    if start < 0:
        start = html.find("<h1 ")
    if start < 0:
        return html

    end_patterns = [
        'class="ui bottom attached segment" style="display: none;"',
        "class='ui bottom attached segment' style='display: none;'",
    ]
    ends = [html.find(p, start) for p in end_patterns]
    ends = [e for e in ends if e > start]
    end = min(ends) if ends else len(html)
    return html[start:end]


def _safe_name(s: str, fallback: str) -> str:
    s = s.strip()
    s = urllib.parse.unquote(s)
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    s = s.strip("._")
    return s or fallback


def export_image(src: str, cid_map: Dict[str, Tuple[str, bytes]], asset_dir: Path) -> str:
    asset_dir.mkdir(parents=True, exist_ok=True)

    if src.startswith("cid:"):
        cid = src[4:]
        if cid in cid_map:
            ctype, data = cid_map[cid]
        else:
            # fuzzy fallback by suffix
            hit = None
            for k, v in cid_map.items():
                if k.endswith(cid):
                    hit = v
                    break
            if not hit:
                return src
            ctype, data = hit
        ext = EXT_BY_MIME.get(ctype, mimetypes.guess_extension(ctype) or ".bin")
        name = _safe_name(cid, "cid")
        out = asset_dir / f"{name}{ext}"
        out.write_bytes(data)
        return out.name

    if src.startswith("data:image/"):
        m = re.match(r"data:(image/[a-zA-Z0-9.+-]+);base64,(.*)", src, re.S)
        if not m:
            return src
        ctype = m.group(1)
        b64 = m.group(2)
        data = base64.b64decode(b64)
        ext = EXT_BY_MIME.get(ctype, mimetypes.guess_extension(ctype) or ".bin")
        h = hashlib.sha1(data).hexdigest()[:16]
        out = asset_dir / f"inline_{h}{ext}"
        out.write_bytes(data)
        return out.name

    if src.startswith("http://") or src.startswith("https://"):
        try:
            req = urllib.request.Request(src, headers={"User-Agent": "mhtml-parser/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        except Exception:
            return src

        path = urllib.parse.urlparse(src).path
        base = Path(path).name
        base = _safe_name(base, "img")
        stem = Path(base).stem or "img"
        ext = Path(base).suffix
        if not ext:
            ext = EXT_BY_MIME.get(ctype, mimetypes.guess_extension(ctype) or ".bin")
        out = asset_dir / f"{stem}{ext}"
        if out.exists() and out.read_bytes() == data:
            return out.name
        if out.exists() and out.read_bytes() != data:
            h = hashlib.sha1(data).hexdigest()[:8]
            out = asset_dir / f"{stem}_{h}{ext}"
        out.write_bytes(data)
        return out.name

    return src


def convert_one(src_file: Path, slug: str) -> Path:
    parsed = parse_mhtml(src_file)
    fragment = extract_rules_fragment(parsed.html)

    image_sources = sorted(set(re.findall(r"<img[^>]+src=['\"]([^'\"]+)['\"]", fragment, flags=re.I)))
    asset_dir = ASSET_ROOT / slug
    rel_map: Dict[str, str] = {}
    for src in image_sources:
        local_name = export_image(src, parsed.cid_map, asset_dir)
        rel_map[src] = f"../mhtml_assets/{slug}/{local_name}" if not local_name.startswith("http") else local_name

    parser = RulesHtmlToMd(rel_map)
    parser.feed(fragment)
    body = parser.to_markdown()

    out_file = PARSED_DIR / f"{slug}.md"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = [
        f"# {slug}",
        "",
        f"- Source mhtml: `{src_file.name}`",
        f"- Parsed at: {ts}",
        "",
    ]
    out_file.write_text("\n".join(header) + body, encoding="utf-8")
    return out_file


def main() -> int:
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)

    outputs: List[Tuple[Path, str, List[Path]]] = []
    for name, slug in TARGETS:
        root_src = ROOT / name
        docs_src = DOCS_DIR / name
        src = root_src if root_src.is_file() else docs_src
        if not src.is_file():
            raise FileNotFoundError(f"missing file in both locations: {root_src} OR {docs_src}")
        out_file = convert_one(src, slug)
        asset_dir = ASSET_ROOT / slug
        images = sorted([p for p in asset_dir.glob("*") if p.is_file()]) if asset_dir.exists() else []
        outputs.append((out_file, slug, images))

    index = PARSED_DIR / "README.md"
    lines = ["# mhtml_parsed", "", "Generated markdown files:", ""]
    for p, slug, images in outputs:
        lines.append(f"- [{p.name}](./{p.name})")
        lines.append(f"  - images: {len(images)}")
        if images:
            for img in images:
                rel = f"../mhtml_assets/{slug}/{img.name}"
                lines.append(f"  - {rel}")
    lines.append("")
    index.write_text("\n".join(lines), encoding="utf-8")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("Generated:")
    print(f"- timestamp: {ts}")
    for p, _, _ in outputs:
        print(f"- {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
