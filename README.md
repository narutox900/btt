# Random Thoughts

A tiny static journal for random thoughts — inspired by
[pclouds.gitlab.io](https://pclouds.gitlab.io/). Plain Markdown files go in,
static HTML organized by **month** and **tag** comes out. No backend, no
database; everything is just files you can grep and back up.

## How it works

```
entries/        one Markdown file per entry, bucketed into YYYYMM/ folders
files/          images & attachments, referenced as files/...
assets/         style.css
generate.py     the whole generator (build + scaffolding + preview)
public/          generated site (git-ignored; built by CI)
```

## Writing a thought

Easiest — the interactive helper (`new.py`):

```bash
python new.py            # menu: new post / new tag / list tags
python new.py post       # create a post; pick tags by number, no typos
python new.py tag ideas  # register a new tag in tags.txt
python new.py tags       # list known tags
```

Tags live in `tags.txt` (one per line) so they stay consistent — `new.py post`
lets you pick from that list by number, and remembers any new tag you type.

Or scaffold a bare post directly with the generator:

```bash
python generate.py new "Door curtain" --tags home,small-things
```

Either way you get `entries/202607/2026-07-27-door-curtain.md`:

```markdown
---
title: Door curtain
date: 2026-07-27 15:33
tags: [home, small-things]
---

Write your thought here...
```

- **title / date / tags** live in the frontmatter. `date` and the slug also fall
  back to the filename (`YYYY-MM-DD-slug.md`) if omitted.
- Body is normal Markdown: headings, lists, `code`, fenced code blocks (syntax
  highlighted), blockquotes, tables.

## Images

Drop a file into `files/` and reference it with a `files/...` path:

```markdown
![a little sketch](files/sketch.svg)
```

The generator rewrites the path so it resolves correctly on every page
(homepage, month pages, tag pages).

## Preview locally

```bash
pip install -r requirements.txt
python generate.py serve          # builds + serves at http://localhost:8000
```

Or just build:

```bash
python generate.py build          # -> public/
```

## Publishing (GitHub Pages)

1. Push this repo to GitHub (default branch `main`).
2. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Every push to `main` runs `.github/workflows/deploy.yml`, which builds with
   `generate.py` and deploys `public/`. You only ever commit Markdown.

## Structure of the generated site

```
index.html                       recent thoughts + sidebar
archives/index.html              all years
archives/2026/index.html         months in 2026
archives/2026/07/index.html      full posts for July 2026 (canonical permalinks)
archives/tags/index.html         all tags
archives/tags/home.html          posts tagged "home"
```
