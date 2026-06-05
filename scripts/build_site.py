#!/usr/bin/env python3
"""Build the M3TRIC static site.

This generator intentionally uses only the Python standard library so the site can
be built locally and in GitHub Actions without installing dependencies.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
ASSETS_DIR = ROOT / "assets"
TEMPLATE_PATH = ROOT / "templates" / "base.html"
NAV_PATH = ROOT / "navigation.json"
SITE_CONFIG_PATH = ROOT / "site.json"
OUTPUT_DIR = ROOT / "site"


@dataclass(frozen=True)
class Page:
    source: str
    output: str
    title: str
    description: str
    wide: bool
    content_html: str


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text

    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text

    raw_meta = parts[1]
    body = parts[2]
    meta: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, body


def source_to_output(source: str) -> str:
    path = Path(source)
    return str(path.with_suffix(".html")).replace("\\", "/")


def page_root(output: str) -> str:
    depth = len(Path(output).parts) - 1
    return "../" * depth


def apply_page_vars(text: str, root_url: str) -> str:
    assets_url = f"{root_url}assets" if root_url else "assets"
    return text.replace("{{root}}", root_url).replace("{{assets}}", assets_url)


def convert_link_target(target: str) -> str:
    if target.startswith(("http://", "https://", "mailto:", "tel:", "#")):
        return target
    if target.endswith(".md"):
        return target[:-3] + ".html"
    return target


def inline_markdown(text: str) -> str:
    """Convert a small, safe subset of inline Markdown to HTML."""
    placeholders: list[str] = []

    def stash(value: str) -> str:
        placeholders.append(value)
        return f"@@PLACEHOLDER_{len(placeholders)-1}@@"

    # Preserve inline code before escaping.
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = html.escape(text, quote=False)

    # Images and links.
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: stash(
            f'<img src="{html.escape(convert_link_target(m.group(2)), quote=True)}" '
            f'alt="{html.escape(m.group(1), quote=True)}">'
        ),
        text,
    )
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: stash(
            f'<a href="{html.escape(convert_link_target(m.group(2)), quote=True)}">{m.group(1)}</a>'
        ),
        text,
    )

    # Bold and emphasis after escaping.
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)

    for i, value in enumerate(placeholders):
        text = text.replace(f"@@PLACEHOLDER_{i}@@", value)
    return text


def is_table_start(lines: list[str], i: int) -> bool:
    if i + 1 >= len(lines):
        return False
    first = lines[i].strip()
    second = lines[i + 1].strip()
    return first.startswith("|") and first.endswith("|") and bool(re.match(r"^\|[\s:\-\|]+\|$", second))


def render_table(lines: list[str], i: int) -> tuple[str, int]:
    table_lines: list[str] = []
    while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
        table_lines.append(lines[i].strip())
        i += 1

    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in table_lines]
    header = rows[0]
    body = rows[2:]
    out = ["<table>", "<thead>", "<tr>"]
    out.extend(f"<th>{inline_markdown(cell)}</th>" for cell in header)
    out.extend(["</tr>", "</thead>", "<tbody>"])
    for row in body:
        out.append("<tr>")
        out.extend(f"<td>{inline_markdown(cell)}</td>" for cell in row)
        out.append("</tr>")
    out.extend(["</tbody>", "</table>"])
    return "\n".join(out), i


def render_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Raw HTML lines are passed through. Keep every line that looks like HTML
        # as author-controlled markup so landing-page sections remain editable.
        if stripped.startswith("<") and stripped.endswith(">"):
            out.append(line)
            i += 1
            continue

        if stripped in {"---", "***", "___"}:
            out.append("<hr>")
            i += 1
            continue

        if is_table_start(lines, i):
            table_html, i = render_table(lines, i)
            out.append(table_html)
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = inline_markdown(heading.group(2))
            slug = re.sub(r"[^a-z0-9]+", "-", heading.group(2).lower()).strip("-")
            out.append(f'<h{level} id="{html.escape(slug, quote=True)}">{text}</h{level}>')
            i += 1
            continue

        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f"<blockquote><p>{inline_markdown(' '.join(quote_lines))}</p></blockquote>")
            continue

        if re.match(r"^[-*]\s+", stripped):
            items: list[str] = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                item = re.sub(r"^[-*]\s+", "", lines[i].strip())
                items.append(f"<li>{inline_markdown(item)}</li>")
                i += 1
            out.append("<ul>\n" + "\n".join(items) + "\n</ul>")
            continue

        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                item = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                items.append(f"<li>{inline_markdown(item)}</li>")
                i += 1
            out.append("<ol>\n" + "\n".join(items) + "\n</ol>")
            continue

        # Paragraph.
        paragraph: list[str] = []
        while i < len(lines):
            candidate = lines[i]
            s = candidate.strip()
            if not s:
                break
            if (
                s.startswith("<")
                or re.match(r"^(#{1,6})\s+", s)
                or re.match(r"^[-*]\s+", s)
                or re.match(r"^\d+\.\s+", s)
                or s.startswith(">")
                or s in {"---", "***", "___"}
                or is_table_start(lines, i)
            ):
                break
            paragraph.append(s)
            i += 1
        if paragraph:
            out.append(f"<p>{inline_markdown(' '.join(paragraph))}</p>")
        else:
            i += 1

    return "\n".join(out)


def flatten_nav(nav_items: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    pages: list[dict[str, str]] = []
    for item in nav_items:
        if "source" in item:
            pages.append(item)
        for child in item.get("children", []):
            if "source" in child:
                pages.append(child)
    return pages


def render_nav(nav_items: list[dict[str, Any]], current_source: str, root_url: str) -> str:
    chunks: list[str] = []
    for item in nav_items:
        if "children" in item:
            active_parent = any(child.get("source") == current_source for child in item["children"])
            parent_class = "nav-parent active" if active_parent else "nav-parent"
            chunks.append('<div class="nav-item">')
            chunks.append(f'<button class="{parent_class}" type="button">{html.escape(item["title"])}</button>')
            chunks.append('<div class="dropdown">')
            for child in item["children"]:
                href = root_url + source_to_output(child["source"])
                active = " class=\"active\"" if child["source"] == current_source else ""
                chunks.append(f'<a{active} href="{html.escape(href, quote=True)}">{html.escape(child["title"])}</a>')
            chunks.append("</div>")
            chunks.append("</div>")
        else:
            href = root_url + source_to_output(item["source"])
            active = " active" if item["source"] == current_source else ""
            chunks.append('<div class="nav-item">')
            chunks.append(f'<a class="nav-link{active}" href="{html.escape(href, quote=True)}">{html.escape(item["title"])}</a>')
            chunks.append("</div>")
    return "\n".join(chunks)



def render_product_pillar_bar(current_source: str, root_url: str) -> str:
    """Render the fixed product ecosystem navigator for product pages."""
    products = [
        {
            "title": "Monitoreo multiescala",
            "tag": "",#"M1 · M2 · M3",
            "href": "productos/monitoreo-multiescala.html",
            "class": "monitoring",
            "description": "Monitoreo in-situ, remoto y satelital",
            "subitems": [
                ("M1", "", "productos/monitoreo-multiescala.html#m1-microescala"),
                ("M2", "", "productos/monitoreo-multiescala.html#m2-mesoescala"),
                ("M3", "", "productos/monitoreo-multiescala.html#m3-macroescala"),
            ],
        },
        {
            "title": "Capacidades IoT",
            "tag": "",#"Conectividad",
            "href": "productos/capacidades-iot.html",
            "class": "iot",
            "description": "LoRa, brokers y APIs",
            "subitems": [],
        },
        {
            "title": "Visualización, alertas y reportes",
            "tag": "",#"Dashboards · Reportes",
            "href": "productos/visualizacion-alertas.html",
            "class": "visualization",
            "description": "Tableros, alertas y reportes automáticos",
            "subitems": [],
        },
        {
            "title": "Modelación e información espacial",
            "tag": "",#"Análisis geoespacial",
            "href": "productos/modelacion-geoespacial.html",
            "class": "modeling",
            "description": "Geoestadística y gemelos digitales",
            "subitems": [],
        },
    ]

    chunks = [
        '<nav class="product-ecosystem-nav" aria-label="M3TRIC decision system">',
        '<div class="product-ecosystem-inner">',
        '<div class="product-ecosystem-label">M3TRIC Decision System</div>',
        '<div class="product-ecosystem-grid">',
    ]
    for product in products:
        href = root_url + product["href"]
        active = " active" if product["href"].replace(".html", ".md") == current_source else ""
        chunks.append(f'<section class="product-ecosystem-card {product["class"]}{active}">')
        chunks.append(f'<a class="product-ecosystem-main" href="{html.escape(href, quote=True)}">')
        chunks.append(f'<span class="product-ecosystem-tag">{html.escape(product["tag"])}</span>')
        chunks.append(f'<strong>{html.escape(product["title"])}</strong>')
        chunks.append(f'<small>{html.escape(product["description"])}</small>')
        chunks.append('</a>')
        if product["subitems"]:
            chunks.append('<div class="product-ecosystem-scales" aria-label="Escalas de monitoreo multiescala">')
            for code, label, subhref in product["subitems"]:
                chunks.append(
                    f'<a href="{html.escape(root_url + subhref, quote=True)}">'
                    f'<b>{html.escape(code)}</b><span>{html.escape(label)}</span></a>'
                )
            chunks.append('</div>')
        chunks.append('</section>')
    chunks.append('</div></div></nav>')
    return "\n".join(chunks)

def build_page(source: str, nav_items: list[dict[str, Any]], site_config: dict[str, str], template: str) -> Page:
    source_path = CONTENT_DIR / source
    if not source_path.exists():
        raise FileNotFoundError(f"Navigation references missing content file: {source}")

    output = source_to_output(source)
    root_url = page_root(output)
    raw_text = source_path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw_text)
    body = apply_page_vars(body, root_url)
    body_html = render_markdown(body)

    title = meta.get("title") or source_path.stem.replace("-", " ").title()
    description = meta.get("description") or site_config.get("description", "")
    wide = meta.get("wide", "false").lower() in {"true", "yes", "1"}
    article_class = "content wide" if wide else "content"
    article_html = f'<article class="{article_class}">\n{body_html}\n</article>'
    if source.startswith("productos/"):
        content = render_product_pillar_bar(source, root_url) + "\n" + article_html
    else:
        content = article_html

    replacements = {
        "{{ language }}": site_config.get("language", "es"),
        "{{ page_title }}": html.escape(title),
        "{{ page_description }}": html.escape(description),
        "{{ author }}": html.escape(site_config.get("author", "M3TRIC")),
        "{{ site_name }}": html.escape(site_config.get("site_name", "M3TRIC")),
        "{{ tagline }}": html.escape(site_config.get("tagline", "")),
        "{{ root }}": root_url,
        "{{ nav_html }}": render_nav(nav_items, source, root_url),
        "{{ content }}": content,
    }

    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)

    return Page(
        source=source,
        output=output,
        title=title,
        description=description,
        wide=wide,
        content_html=rendered,
    )


def copy_assets() -> None:
    target = OUTPUT_DIR / "assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ASSETS_DIR, target)


def write_page(page: Page) -> None:
    output_path = OUTPUT_DIR / page.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page.content_html, encoding="utf-8")



def remove_tree(path: Path) -> None:
    """Remove a directory, with retries for Windows/OneDrive file locks."""
    def onerror(func, target, exc_info):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except PermissionError:
            time.sleep(0.5)
            os.chmod(target, stat.S_IWRITE)
            func(target)

    if path.exists():
        shutil.rmtree(path, onerror=onerror)


def all_content_pages(nav_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build pages from navigation plus every Markdown file under content/.

    This keeps the visible menu simple while still generating pages that may be
    linked from Markdown content, such as ecosistema, escalas, or decision-system.
    """
    pages = flatten_nav(nav_items)
    seen = {item["source"] for item in pages}
    for path in sorted(CONTENT_DIR.rglob("*.md")):
        source = path.relative_to(CONTENT_DIR).as_posix()
        if source not in seen:
            pages.append({"title": path.stem.replace("-", " ").title(), "source": source})
            seen.add(source)
    return pages

def main() -> None:
    nav_items = load_json(NAV_PATH)
    site_config = load_json(SITE_CONFIG_PATH)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    remove_tree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    copy_assets()

    pages = all_content_pages(nav_items)
    seen_sources = set()
    for item in pages:
        source = item["source"]
        if source in seen_sources:
            raise ValueError(f"Duplicated page source in navigation: {source}")
        seen_sources.add(source)
        page = build_page(source, nav_items, site_config, template)
        write_page(page)

    (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Built {len(pages)} pages into {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
