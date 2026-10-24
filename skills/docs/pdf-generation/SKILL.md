---
name: pdf-generation
description: "Compile Markdown to PDF in ~/system-docs with generate_pdf.py / build-pdf.sh: one render, a definitive pages=/bookmarks= report, and the exact WeasyPrint bookmark tuple shape. Prevents infinite re-render loops."
version: 1.0.0
author: CoreyAI
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Documentation, PDF, WeasyPrint, Markdown, Verification, Loops]
    related_skills: [mempalace]
---

# PDF Generation (Markdown -> PDF)

Docs live in `~/system-docs`. `generate_pdf.py` converts Markdown -> HTML -> PDF with
an embedded stylesheet. `build-pdf.sh` is the wrapper to use.

## The One Rule

**Never call WeasyPrint directly to inspect a PDF you just generated.** Use the
wrapper; it renders once and reports everything:

```bash
cd ~/system-docs && ./build-pdf.sh home_assistant_inventory.md
```

```
home_assistant_inventory.md -> home_assistant_inventory.pdf
pages=15 bookmarks=32 bytes=191120
Home Assistant — Configuration, Automations & Entity Inventory -> p1
  1. Summary -> p1
  ...
```

**A PDF is DONE when the command exits 0 and prints `pages=N bookmarks=M`.** The
outline it prints IS the PDF's outline. There is nothing left to verify, so there is
nothing to re-render.

Machine-readable, for scripts and agents:

```bash
./.venv/bin/python generate_pdf.py -i doc.md --check --json   # writes no file
```

## Exit codes — trust them, do not re-run

| Code | Meaning | Correct next move |
|---|---|---|
| 0 | Success; `pages=`/`bookmarks=` printed | Done. Report the numbers. |
| 2 | Bad input / usage / missing stylesheet | Fix the argument. Re-rendering cannot help. |
| 3 | Render failed **or** exceeded `GENERATE_PDF_TIMEOUT` (default 300 s) | Read the error text; fix the document or raise the timeout. |
| 4 | Cannot write the output file | Fix the path/permissions. |

## The retry rule (this is how the loop happened)

**If a command produces identical output twice, stop and change the approach. Never
issue it a third time.**

Re-rendering the same Markdown is deterministic: same input, same output, ~2-65 s
wasted per attempt. A retry is only rational if something changed — a file, a flag,
an environment variable. If you cannot name what you changed, do not re-run.

## Why this skill exists

On 2026-10-24 an agent rendered the same PDF **581 times over ~90 minutes** trying to
read PDF bookmarks. Two causes:

1. `generate_pdf.py` set no `bookmark-level` CSS, so the PDF genuinely had no outline.
2. Its probe unpacked WeasyPrint's bookmark tuple wrong, so it printed `-> p?` forever
   and concluded every render had failed.

Both are fixed in the script. The bookmark CSS is now built in, and `--summary`
reports the outline from the render that already happened.

## WeasyPrint bookmark tuple (if you must touch it directly)

`Document.make_bookmark_tree()` returns nodes shaped:

```python
(label, (page, x, y), children, state)
```

The page number is the **first element of the second tuple**, and it is **0-based**.
The children list is element 2 — *not* a page number. Scanning `item[2:]` for an int
always fails.

```python
def bookmark_outline(document):
    """(depth, label, page) with 1-based pages."""
    out = []
    def walk(nodes, depth):
        for item in nodes:
            label, (page, _x, _y), children, *_rest = item
            out.append((depth, str(label), int(page) + 1))
            walk(children, depth + 1)
    walk(document.make_bookmark_tree(), 1)
    return out
```

`generate_pdf.bookmark_outline()` already does this — import it rather than rewriting it.

## Other facts

- Headings `h1`-`h4` become bookmarks; `h5`/`h6` deliberately do not.
- One render per invocation. Never render twice to inspect — reuse the `Document`.
- WeasyPrint output is **not byte-stable** (embedded creation timestamp), so never
  compare PDF bytes to detect "no change". Compare `pages`/`bookmarks` instead.
- `report_unresolved_anchors()` should return `[]` for a healthy document; a non-empty
  list means an in-document `[§x](#anchor)` link points at a heading that does not exist.
- Regenerating a PDF is cheap (~2.5 s for 15 pages). There is no reason to be clever
  about caching, and no reason to loop.
