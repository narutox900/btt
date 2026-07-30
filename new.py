#!/usr/bin/env python3
"""
Simple authoring helper: create a new post or register a new tag.

  python new.py                 interactive menu
  python new.py post            create a new post (interactive)
  python new.py tag <name>      register a new tag
  python new.py tags            list known tags

Tags are kept in tags.txt (one per line) so they stay consistent across posts.
Posts are plain Markdown files under entries/YYYYMM/ — build with generate.py.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from generate import ROOT, ENTRIES_DIR, Thought, slugify

TAGS_FILE = ROOT / "tags.txt"

# Make interactive I/O robust to locale/terminal encoding quirks: a stray
# non-UTF-8 byte should never crash the prompt, and UTF-8 titles (e.g. tiếng
# Việt) must round-trip cleanly.
for _stream, _kw in ((sys.stdin, {"errors": "replace"}), (sys.stdout, {}), (sys.stderr, {})):
    try:
        _stream.reconfigure(encoding="utf-8", **_kw)
    except (AttributeError, ValueError):
        pass


def ask(prompt, default=""):
    """input() that's resilient to EOF and undecodable stray bytes."""
    try:
        # drop any U+FFFD introduced by a bad byte so titles/tags stay clean
        return input(prompt).replace("�", "")
    except EOFError:
        print()
        return default


# --------------------------------------------------------------------------- #
# Tag registry
# --------------------------------------------------------------------------- #

def load_registered_tags():
    if not TAGS_FILE.exists():
        return []
    return [line.strip() for line in TAGS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def load_used_tags():
    """Tags that already appear in existing posts."""
    used = set()
    for p in ENTRIES_DIR.rglob("*.md"):
        try:
            used.update(Thought(p).tags)
        except Exception:
            pass
    return used


def all_known_tags():
    """Union of registered tags and tags already used, sorted, case-insensitive dedup."""
    seen, out = {}, []
    for t in list(load_registered_tags()) + sorted(load_used_tags(), key=str.lower):
        key = t.lower()
        if key not in seen:
            seen[key] = True
            out.append(t)
    return sorted(out, key=str.lower)


def register_tag(name):
    name = name.strip()
    if not name:
        print("Empty tag, nothing to do.")
        return
    existing = {t.lower() for t in load_registered_tags()}
    if name.lower() in existing:
        print(f"Tag '{name}' is already registered.")
        return
    with TAGS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(name + "\n")
    print(f"Registered tag: {name}")


# --------------------------------------------------------------------------- #
# New post
# --------------------------------------------------------------------------- #

def choose_tags():
    known = all_known_tags()
    if known:
        print("\nExisting tags:")
        for i, t in enumerate(known, 1):
            print(f"  {i:>2}. {t}")
        print("Pick by number and/or type new tag names, comma-separated.")
    else:
        print("\nNo tags yet — just type new tag names, comma-separated.")

    raw = ask("Tags: ").strip()
    chosen = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if token.isdigit() and known and 1 <= int(token) <= len(known):
            chosen.append(known[int(token) - 1])
        else:
            chosen.append(token)
            register_tag(token)  # remember any freshly-typed tag
    # de-dup, keep order
    seen, out = set(), []
    for t in chosen:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def create_post(title=None):
    if not title:
        title = ask("Title: ").strip()
    if not title:
        print("A title is required.")
        return

    tags = choose_tags()
    dt = datetime.now()
    slug = slugify(title)
    path = ENTRIES_DIR / dt.strftime("%Y%m") / f"{dt.strftime('%Y-%m-%d')}-{slug}.md"
    if path.exists():
        print(f"Already exists: {path}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "---\n"
        f"title: {title}\n"
        f"date: {dt.strftime('%Y-%m-%d %H:%M')}\n"
        f"tags: [{', '.join(tags)}]\n"
        "---\n\n"
        "Write your thought here...\n"
    )
    path.write_text(body, encoding="utf-8")
    print(f"\nCreated {path}")

    if ask("Open in $EDITOR now? [y/N] ").strip().lower() == "y":
        editor = __import__("os").environ.get("EDITOR", "vi")
        subprocess.call([editor, str(path)])


# --------------------------------------------------------------------------- #
# Menu / CLI
# --------------------------------------------------------------------------- #

def menu():
    print("What do you want to do?")
    print("  1. New post")
    print("  2. New tag")
    print("  3. List tags")
    choice = ask("> ").strip()
    if choice == "1":
        create_post()
    elif choice == "2":
        register_tag(ask("New tag name: "))
    elif choice == "3":
        for t in all_known_tags():
            print(f"  {t}")
    else:
        print("Nothing to do.")


def main():
    args = sys.argv[1:]
    if not args:
        menu()
        return
    cmd = args[0].lower()
    if cmd == "post":
        create_post(" ".join(args[1:]) or None)
    elif cmd == "tag":
        register_tag(" ".join(args[1:]))
    elif cmd == "tags":
        for t in all_known_tags():
            print(f"  {t}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
