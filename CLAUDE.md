# CLAUDE.md

Tiny static-site generator for a personal "random thoughts" journal. No backend,
no database — Markdown in, plain static HTML out. Inspired by pclouds.gitlab.io
("Cùi Bắp").

## Commands

```bash
python3 generate.py                 # build site into public/
python3 generate.py build           # same as above
python3 generate.py serve [PORT]    # build, then serve public/ (default :8000)
python3 generate.py new "Title" --tags home,misc [--date 2026-07-27]
```

`python` is not on PATH here — use `python3`. Deps: `pip install -r requirements.txt`
(`markdown`, `pygments`). Without them the build still works via a plain-text fallback.

## Layout

```
generate.py      # the whole generator: parse → build → CLI (see sections below)
new.py           # standalone helper to scaffold a new entry
entries/         # source posts, bucketed into entries/YYYYMM/*.md
files/           # images & attachments, referenced in Markdown as files/...
assets/style.css # the single stylesheet, copied to public/styles/style.css on build
public/          # BUILD OUTPUT — wiped and regenerated every build; never edit by hand
tags.txt         # scratch list of tags
```

## How it works

- **Entries** are Markdown with YAML-ish frontmatter (`title`, `date`, `tags: [...]`).
  Filenames may carry a `YYYY-MM-DD-slug.md` prefix; missing dates fall back to the
  filename date, then file mtime. Parsed by the `Thought` class.
- **Build** (`build()` in `generate.py`) groups posts by year / month / tag and emits:
  homepage (depth 0), archives index (1), per-year (2), per-month full posts (3),
  tags index + per-tag pages (2). "depth" = how many dirs deep the page sits; all
  internal links go through `rel(depth, path)` to stay relative.
- **Page chrome** lives in `page_shell()` — header, sidebar, footer, mobile menu JS.
  The right **sidebar** is built by `build_sidebar()`: Archives, Tags, and an
  **Elsewhere** block of external profile links driven by the `LINKS` list near the
  top of `generate.py` (edit that list to change/add links).
- **Config constants** at the top of `generate.py`: `SITE_TITLE`, `SITE_TAGLINE`,
  `AUTHOR`, `HOME_RECENT`, `LINKS`.

## Conventions

- Edit `generate.py` / `assets/style.css` / `entries/`, then rebuild. Never edit
  `public/` directly — it is deleted and rewritten on every build.
- `slugify()` transliterates Vietnamese diacritics to ASCII for URL-safe slugs.
