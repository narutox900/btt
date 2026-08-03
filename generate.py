#!/usr/bin/env python3
"""
Tiny static generator for a personal "random thoughts" journal.

Model (inspired by pclouds.gitlab.io / "Cùi Bắp"):
  - One Markdown file per thought in thoughts/
  - Output is plain static HTML, organized by month and by tag
  - No backend, no database, easy to grep and back up

Usage:
  python generate.py                 # build site into public/
  python generate.py build           # same as above
  python generate.py serve [PORT]    # build, then serve public/ for preview
  python generate.py new "Title" --tags home,misc [--date 2026-07-27]

A thought file looks like:

    ---
    title: Door curtain
    date: 2026-07-27 15:33
    tags: [home, misc]
    ---

    When I first moved in, I just wanted something *up and running*...
"""

import argparse
import html
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

try:
    import markdown as md_lib
except ImportError:
    md_lib = None

ROOT = Path(__file__).resolve().parent
ENTRIES_DIR = ROOT / "entries"    # source posts, bucketed into entries/YYYYMM/
ASSETS_DIR = ROOT / "assets"
FILES_DIR = ROOT / "files"        # images & attachments, referenced as files/...
OUTPUT_DIR = ROOT / "public"

SITE_TITLE = "linh tinh vớ vẩn"
SITE_TAGLINE = "viết nhảm tìm sự chú ý"
AUTHOR = "btt"
HOME_RECENT = 25  # posts shown on the homepage

# External profile links, shown in the sidebar "Elsewhere" block.
# (label, url) — fill in the URLs when you have them.
LINKS = [
    ("nhạc nhẽo", "https://open.spotify.com/user/ksgob34txxt74pah0011xiegm?si=94770db61ec14e22"),      # spotify
    ("phim phọt", "https://letterboxd.com/narutox900/"),      # letterboxd
    ("sách sủng", "http://goodreads.com/user/show/85308781-btt"),      # goodreads
]

VN_MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
DATE_PREFIX_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[-_](.+)$")


def slugify(text):
    """ASCII, URL-safe slug. Transliterates diacritics (incl. Vietnamese)."""
    text = text.strip().lower().replace("đ", "d")
    # decompose accents and drop the combining marks: à -> a, ổ -> o, ...
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s-]", "", text)   # keep ASCII word chars only
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or "untitled"


def parse_frontmatter(raw):
    """Return (meta_dict, body_str). Supports a small YAML subset."""
    m = FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    head, body = m.group(1), m.group(2)
    meta = {}
    for line in head.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "tags":
            val = val.strip("[]")
            meta["tags"] = [t.strip().strip("'\"") for t in val.split(",") if t.strip()]
        else:
            meta[key] = val.strip("'\"")
    return meta, body


def parse_date(value, fallback):
    if not value:
        return fallback
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return fallback


class Thought:
    def __init__(self, path):
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)

        stem = path.stem
        m = DATE_PREFIX_RE.match(stem)
        fname_date = None
        fname_slug = stem
        if m:
            y, mo, d, rest = m.groups()
            fname_date = f"{y}-{mo}-{d}"
            fname_slug = rest

        # file mtime as a last-resort fallback so posts always sort somehow
        fallback = parse_date(fname_date, datetime.fromtimestamp(path.stat().st_mtime))
        self.dt = parse_date(meta.get("date"), fallback)
        self.title = meta.get("title") or fname_slug.replace("-", " ").strip().capitalize()
        self.tags = meta.get("tags", [])
        self.slug = slugify(meta.get("slug") or fname_slug)
        self.body_md = body.strip()
        self.path = path

    @property
    def anchor(self):
        return self.dt.strftime("%Y-%m-%dT%H_%M_%S")

    @property
    def year(self):
        return self.dt.year

    @property
    def month(self):
        return self.dt.month

    @property
    def month_path(self):
        return f"archives/{self.year:04d}/{self.month:02d}/index.html"

    @property
    def permalink(self):
        return f"{self.month_path}#{self.anchor}"

    def render_body(self):
        if md_lib is None:
            # graceful fallback: escape + paragraph-ise
            paras = [html.escape(p) for p in re.split(r"\n\s*\n", self.body_md)]
            return "\n".join(f"<p>{p}</p>" for p in paras if p)
        return md_lib.markdown(
            self.body_md,
            extensions=["fenced_code", "codehilite", "tables", "sane_lists", "nl2br"],
            extension_configs={"codehilite": {"guess_lang": False}},
        )


# --------------------------------------------------------------------------- #
# HTML helpers
# --------------------------------------------------------------------------- #

def rel(depth, path):
    """Relative URL from a page `depth` levels deep to a root-relative path."""
    return ("../" * depth) + path


# Rewrite src/href to files/... (or /files/...) so images & attachments resolve
# from whatever depth the post is rendered at.
LOCAL_LINK_RE = re.compile(r'(src|href)="/?(files/[^"]*)"')


def fixup_local_links(html_str, depth):
    prefix = "../" * depth
    return LOCAL_LINK_RE.sub(lambda m: f'{m.group(1)}="{prefix}{m.group(2)}"', html_str)


def esc(s):
    return html.escape(str(s))


def fmt_date(dt):
    return dt.strftime(f"%a, %d {VN_MONTHS[dt.month]} %Y &middot; %H:%M")


def tag_slug(tag):
    return slugify(tag)


def page_shell(depth, title, body_html, sidebar_html):
    css = rel(depth, "styles/style.css")
    home = rel(depth, "index.html")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="generator" content="thoughts.py">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{css}">
</head>
<body>
<header class="site-header">
  <a class="brand" href="{home}">{esc(SITE_TITLE)}</a>
  <span class="tagline">{esc(SITE_TAGLINE)}</span>
  <button id="menu-toggle" aria-label="Toggle navigation">☰</button>
</header>
<div class="layout">
  <main class="content">
{body_html}
  </main>
  <aside class="sidebar" id="sidebar">
{sidebar_html}
  </aside>
</div>
<footer class="site-footer">
  <p>Bốc phét từ mồm {esc(AUTHOR)}. Code ăn cướp được.</p>
</footer>
<script>
document.getElementById('menu-toggle').addEventListener('click',function(){{
  document.getElementById('sidebar').classList.toggle('open');
}});
</script>
</body>
</html>
"""


def render_post(depth, t, heading_level=2):
    tags_html = ""
    if t.tags:
        links = " ".join(
            f'<a class="tag" href="{rel(depth, "archives/tags/" + tag_slug(tag) + ".html")}">{esc(tag)}</a>'
            for tag in t.tags
        )
        tags_html = f'<div class="post-tags">{links}</div>'
    permalink = rel(depth, t.permalink)
    return f"""    <article class="post" id="{esc(t.anchor)}">
      <h{heading_level} class="post-title"><a href="{permalink}">{esc(t.title)}</a></h{heading_level}>
      <div class="post-meta"><time>{fmt_date(t.dt)}</time></div>
      <div class="post-body">
{fixup_local_links(t.render_body(), depth)}
      </div>
      {tags_html}
    </article>"""


def build_sidebar(depth, by_year, by_tag):
    year_items = "\n".join(
        f'    <li><a href="{rel(depth, f"archives/{y:04d}/index.html")}">{y}</a> '
        f'<span class="count">{len(posts)}</span></li>'
        for y, posts in sorted(by_year.items(), reverse=True)
    )
    tag_items = "\n".join(
        f'    <li><a href="{rel(depth, "archives/tags/" + tag_slug(tag) + ".html")}">{esc(tag)}</a> '
        f'<span class="count">{len(posts)}</span></li>'
        for tag, posts in sorted(by_tag.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    )
    archives_index = rel(depth, "archives/index.html")
    tags_index = rel(depth, "archives/tags/index.html")
    links_items = "\n".join(
        f'    <li><a href="{esc(url)}"{"" if url.startswith("#") else " rel=\"me noopener\" target=\"_blank\""}>{esc(label)}</a></li>'
        for label, url in LINKS
    )
    links_block = f"""
    <section class="side-block">
      <h3>Elsewhere</h3>
      <ul class="side-list links">
{links_items}
      </ul>
    </section>""" if LINKS else ""
    return f"""    <section class="side-block">
      <h3><a href="{archives_index}">Archives</a></h3>
      <ul class="side-list">
{year_items}
      </ul>
    </section>
    <section class="side-block">
      <h3><a href="{tags_index}">Tags</a></h3>
      <ul class="side-list tags">
{tag_items}
      </ul>
    </section>{links_block}"""


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build():
    if not ENTRIES_DIR.exists():
        print(f"No entries/ directory found at {ENTRIES_DIR}", file=sys.stderr)
        sys.exit(1)

    thoughts = [Thought(p) for p in sorted(ENTRIES_DIR.rglob("*.md"))]
    thoughts.sort(key=lambda t: t.dt, reverse=True)

    if not thoughts:
        print("No entries found. Create one with: python new.py post")

    by_year = {}
    by_month = {}
    by_tag = {}
    for t in thoughts:
        by_year.setdefault(t.year, []).append(t)
        by_month.setdefault((t.year, t.month), []).append(t)
        for tag in t.tags:
            by_tag.setdefault(tag, []).append(t)

    # clean output
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # assets
    if ASSETS_DIR.exists():
        shutil.copytree(ASSETS_DIR, OUTPUT_DIR / "styles")

    # images & attachments (referenced in Markdown as files/...)
    if FILES_DIR.exists():
        shutil.copytree(FILES_DIR, OUTPUT_DIR / "files")

    # --- homepage (depth 0) ---
    sidebar0 = build_sidebar(0, by_year, by_tag)
    recent = thoughts[:HOME_RECENT]
    if recent:
        body = '    <h1 class="page-title">từ trên xuống dưới</h1>\n'
        body += "\n".join(render_post(0, t) for t in recent)
        if len(thoughts) > HOME_RECENT:
            body += f'\n    <p class="more"><a href="archives/index.html">Older thoughts in the archives &rarr;</a></p>'
    else:
        body = '    <h1 class="page-title">Nothing here yet</h1>\n    <p>Write your first thought.</p>'
    write(OUTPUT_DIR / "index.html", page_shell(0, SITE_TITLE, body, sidebar0))

    # --- archives index (depth 1): years ---
    sidebar1 = build_sidebar(1, by_year, by_tag)
    year_blocks = []
    for y in sorted(by_year, reverse=True):
        months = sorted({m for (yy, m) in by_month if yy == y}, reverse=True)
        month_links = " ".join(
            f'<a href="{y:04d}/{m:02d}/index.html">{VN_MONTHS[m]} '
            f'<span class="count">{len(by_month[(y, m)])}</span></a>'
            for m in months
        )
        year_blocks.append(
            f'    <div class="archive-year"><h2><a href="{y:04d}/index.html">{y}</a> '
            f'<span class="count">{len(by_year[y])}</span></h2>'
            f'<div class="month-links">{month_links}</div></div>'
        )
    body = '    <h1 class="page-title">Archives</h1>\n' + "\n".join(year_blocks)
    write(OUTPUT_DIR / "archives" / "index.html",
          page_shell(1, f"Archives · {SITE_TITLE}", body, sidebar1))

    # --- per-year (depth 2) ---
    sidebar2 = build_sidebar(2, by_year, by_tag)
    for y in by_year:
        months = sorted({m for (yy, m) in by_month if yy == y}, reverse=True)
        blocks = []
        for m in months:
            posts = by_month[(y, m)]
            items = "\n".join(
                f'      <li><a href="{m:02d}/index.html#{esc(p.anchor)}">{esc(p.title)}</a> '
                f'<span class="when">{p.dt.strftime("%d %b")}</span></li>'
                for p in posts
            )
            blocks.append(
                f'    <section class="archive-month"><h2><a href="{m:02d}/index.html">{VN_MONTHS[m]} {y}</a> '
                f'<span class="count">{len(posts)}</span></h2>\n      <ul class="post-list">\n{items}\n      </ul></section>'
            )
        body = f'    <h1 class="page-title">{y}</h1>\n' + "\n".join(blocks)
        write(OUTPUT_DIR / "archives" / f"{y:04d}" / "index.html",
              page_shell(2, f"{y} · {SITE_TITLE}", body, sidebar2))

    # --- per-month (depth 3): full posts ---
    sidebar3 = build_sidebar(3, by_year, by_tag)
    for (y, m), posts in by_month.items():
        posts_sorted = sorted(posts, key=lambda t: t.dt, reverse=True)
        body = f'    <h1 class="page-title">{VN_MONTHS[m]} {y}</h1>\n'
        body += "\n".join(render_post(3, t) for t in posts_sorted)
        write(OUTPUT_DIR / "archives" / f"{y:04d}" / f"{m:02d}" / "index.html",
              page_shell(3, f"{VN_MONTHS[m]} {y} · {SITE_TITLE}", body, sidebar3))

    # --- tags index (depth 2) ---
    tag_blocks = "\n".join(
        f'    <li><a href="{tag_slug(tag)}.html">{esc(tag)}</a> <span class="count">{len(posts)}</span></li>'
        for tag, posts in sorted(by_tag.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    )
    body = ('    <h1 class="page-title">Tags</h1>\n    <ul class="tag-index">\n'
            + tag_blocks + "\n    </ul>")
    write(OUTPUT_DIR / "archives" / "tags" / "index.html",
          page_shell(2, f"Tags · {SITE_TITLE}", body, sidebar2))

    # --- per-tag (depth 2) ---
    for tag, posts in by_tag.items():
        posts_sorted = sorted(posts, key=lambda t: t.dt, reverse=True)
        items = "\n".join(
            f'      <li><a href="{rel(2, p.permalink)}">{esc(p.title)}</a> '
            f'<span class="when">{p.dt.strftime("%d %b %Y")}</span></li>'
            for p in posts_sorted
        )
        body = (f'    <h1 class="page-title">Tag: {esc(tag)}</h1>\n'
                f'    <ul class="post-list">\n{items}\n    </ul>')
        write(OUTPUT_DIR / "archives" / "tags" / f"{tag_slug(tag)}.html",
              page_shell(2, f"{tag} · {SITE_TITLE}", body, sidebar2))

    print(f"Built {len(thoughts)} entr{'y' if len(thoughts) == 1 else 'ies'} → {OUTPUT_DIR}")
    if md_lib is None:
        print("NOTE: the 'markdown' package is not installed; using a plain-text "
              "fallback. Run: pip install markdown pygments")


# --------------------------------------------------------------------------- #
# `new` command
# --------------------------------------------------------------------------- #

def cmd_new(title, tags, date_str):
    dt = parse_date(date_str, datetime.now())
    slug = slugify(title)
    fname = f"{dt.strftime('%Y-%m-%d')}-{slug}.md"
    path = ENTRIES_DIR / dt.strftime("%Y%m") / fname
    if path.exists():
        print(f"Already exists: {path}", file=sys.stderr)
        sys.exit(1)
    path.parent.mkdir(parents=True, exist_ok=True)
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    content = (
        "---\n"
        f"title: {title}\n"
        f"date: {dt.strftime('%Y-%m-%d %H:%M')}\n"
        f"tags: [{', '.join(tag_list)}]\n"
        "---\n\n"
        "Write your thought here...\n"
    )
    path.write_text(content, encoding="utf-8")
    print(f"Created {path}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def cmd_serve(port):
    build()
    import http.server
    import os
    import socketserver
    os.chdir(OUTPUT_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving {OUTPUT_DIR} at http://localhost:{port} (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main():
    parser = argparse.ArgumentParser(description="Tiny thoughts-journal generator.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("build", help="Build the site into public/")

    p_serve = sub.add_parser("serve", help="Build and serve for local preview")
    p_serve.add_argument("port", nargs="?", type=int, default=8000)

    p_new = sub.add_parser("new", help="Scaffold a new thought")
    p_new.add_argument("title")
    p_new.add_argument("--tags", default="")
    p_new.add_argument("--date", default="")

    args = parser.parse_args()

    if args.command == "new":
        cmd_new(args.title, args.tags, args.date)
    elif args.command == "serve":
        cmd_serve(args.port)
    else:  # build / None
        build()


if __name__ == "__main__":
    main()
