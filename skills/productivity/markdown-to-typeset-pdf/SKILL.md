---
name: markdown-to-typeset-pdf
description: "Markdown to typeset PDF via fpdf2 when pandoc is absent."
version: 0.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [pdf, markdown, fpdf2, typesetting, weasyprint, reportlab]
    category: productivity
    related_skills: [pdf, grounded-citations, pdf-generation]
---

# Markdown → typeset PDF without pandoc/LaTeX

Turns a long markdown report into a books-quality A4 PDF (cover, contents with real page
numbers and dotted leaders, chapter page breaks, striped tables, footers with `Page N / M`,
PDF bookmarks) using **fpdf2** only. Verified on a 14,000-word report → 34 pages.

## When to Use

**First: are you on the host or in the Hermes container?** This skill is for the
**container**. The `coreyai` host has a working WeasyPrint 70.0 install with pango and a
maintained wrapper — `~/system-docs/build-pdf.sh doc.md` (see the `pdf-generation`
skill). Do not build an fpdf2 renderer on the host to work around a pango problem the
host does not have.

Use this skill when:

- The user asks for a PDF of a markdown document and this box has no pandoc / xelatex / wkhtmltopdf.
- WeasyPrint is installed but its system libs are missing (see step 1) and you cannot `apt-get`.
  *Verified in the Hermes container: `import weasyprint` fails with*
  *`cannot load library 'libpangoft2-1-0-0'`. This does NOT apply to the host.*
- The headless browser is unavailable (`browser_exec` → "agent-browser CLI not found") so
  HTML `Page.printToPDF` is not an option.
- Not for generating PDFs from a JSON spec or filling forms — the `pdf` skill covers those.

## Environment reality (check before promising anything)

```bash
for c in pandoc xelatex pdflatex wkhtmltopdf weasyprint libreoffice; do command -v $c; done
python3 -m pip --version          # Hermes' own python ships pip even when the `pip` binary is absent
/opt/data/home/gpt-researcher-venv/bin/python -c "import fpdf, pymupdf; print(fpdf.__version__)"
```

On this box: no pandoc/LaTeX/wkhtmltopdf, no root (no `sudo`, no `apt-get install`), WeasyPrint is
installed in the gpt-researcher venv but dies with
`OSError: cannot load library 'libpangoft2-1.0-0'` (pango/cairo absent, uninstallable without root).
PyPI is reachable, so **fpdf2 installs into the existing venv**:

```bash
/opt/data/home/gpt-researcher-venv/bin/python -m pip install -q fpdf2    # pure python, 2.8.x
```

Use that venv rather than creating a new one: it already has Pillow, fontTools, pypdf and PyMuPDF,
all of which the render and the verification need.

Fonts: only `/usr/share/fonts/truetype/dejavu/{DejaVuSans,DejaVuSans-Bold,DejaVuSerif,DejaVuSerif-Bold,DejaVuSansMono}.ttf`
exist — **no italic or oblique serif face anywhere on the system**. Register the regular TTF for
the `I`/`BI` styles so `**bold**`/`__italic__` runs resolve instead of raising; italic text then
renders upright, which is an acceptable cosmetic loss.

## Procedure

1. **Install fpdf2** (above) and confirm `import fpdf`.
2. **Parse markdown into blocks** (`h1`/`h2`/`h3`, paragraph, bullet, numbered, table, hr,
   fenced code) — do NOT feed markdown to fpdf2 directly. A working parser + renderer lives at
   `/opt/data/ai-profit-research/scripts/md_to_pdf.py`; a newer variant that also handles fenced
   code blocks lives at `/opt/data/router-migration/md_to_pdf_pack.py` — prefer it. Fence handling:
   consume everything between ``` markers as ONE atomic `code` block (render mono ~7.4pt, light
   fill, border=1, `max_line_height` set) and make the paragraph/bullet absorbers stop at `` ``` ``.
   Never let fence lines fall through to the paragraph parser — shell `$`/`#` lines become garbage
   bullets.
3. **Two-pass build for the table of contents.** Pass 1 renders with no TOC and records
   `heading -> page_no`; pass 2 injects the TOC. Pass 1 has one fewer page, so **add +1 to every
   recorded page number before pass 2** — otherwise every TOC entry is off by one.
4. **Render options that matter:** `add_font` for serif/sans/mono, `set_auto_page_break(True, 20)`,
   `alias_nb_pages()` plus a `footer()` that prints `Page {page_no} / {nb}`, `start_section()` for
   bookmarks (PyMuPDF then reports them via `get_toc()`), `set_title/author/subject/creator`.
5. **Verify with PyMuPDF, not by eye alone** (raster page images and read them with `vision_analyze`
   for the final check):
   - page count, page size in mm, metadata;
   - `allt.count("**") == 0` and `allt.count("__") == 0` and backticks gone — catches markdown that
     leaked into the rendered text;
   - every TOC entry matches the page its heading actually appears on (skip the TOC page itself when
     searching, or every entry "matches" page 2);
   - no text block whose `x1 > 195 mm` outside the footer band (`get_text("blocks")`), which is how
     you catch cells overrunning the right margin;
   - raster page 1 (cover), the TOC and a table-heavy page at 110–130 dpi and *look* at them.

## Pitfalls

1. **Bullets and numbered items swallow wrapped lines.** Markdown wraps a bullet over several source
   lines; a parser that reads only the first line emits a broken continuation paragraph at the left
   margin. Absorb following non-blank, non-structural lines into the item text.
2. **Table cells print `**` literally.** Tables are drawn with `multi_cell(..., markdown=False)`, so
   emphasis markers must be stripped *before* drawing. Detect a cell containing `**` and render that
   whole row in the bold font instead — that is how a "Total" row should look.
3. **Headings must not be passed through the inline converter.** An `*italic*` heading becomes
   `__italic__`, which then prints literally because headings are drawn with `markdown=False`.
   Strip `*`/`_`/`` ` `` from headings (and from TOC labels) rather than converting them.
4. **`cell(w=0, …)` does not stop at the right margin in a row that already printed cells** — the
   TOC's page number ran to 209.8 mm on a 210 mm page. Compute explicit widths from
   `LEFT`/`RIGHT` constants instead of relying on `w=0`.
5. **No italic face exists.** Register the regular TTF for `I` so `markdown=True` runs resolve;
   otherwise `add_font` raises `FileNotFoundError` and the run aborts mid-build.
6. **Write pass-1 output to the scratch dir**, not `/tmp` (`$TMPDIR` is the profile scratch dir on
   this box; system temp is not the agreed place for throwaway artifacts).
7. **Wrong interpreter is the usual import failure**: Hermes' own python has neither fpdf2 nor
   pymupdf — always call the venv python explicitly.
8. **Sidecar references are invisible in the PDF.** A source line like "full list: see file.csv"
   renders fine but the reader cannot open the sidecar from a PDF — before rendering, grep the
   source for `see .*\.csv` / file-manifest pointers and inline the actual table (generate it from
   the CSV in the build script). Users notice missing data rows immediately.
9. **If the raster eyeball check is unavailable** (vision endpoint without an encoder), run the
   full structural suite instead — TOC match, stray markdown, margin overflow, plus a count of
   expected data tokens (e.g. regex-count MACs/rows and assert it equals the source count) — and
   tell the user the visual pass was skipped rather than implying it ran.

## Verification

```bash
/opt/data/home/gpt-researcher-venv/bin/python scripts/md_to_pdf.py            # writes the PDF
/opt/data/home/gpt-researcher-venv/bin/python - <<'PY'
import pymupdf, re
p = "REVIEW-LLM-monetisation-10000-words.pdf"
d = pymupdf.open(p); t = "\n".join(pg.get_text() for pg in d)
pairs = re.findall(r"^(.*?)\s*\.{2,}\s*(\d+)\s*$", d[1].get_text(), re.M)
pages = [(" ".join(pg.get_text().split()), i+1) for i, pg in enumerate(d)]
ok = sum(1 for l, n in pairs if next((q for t2, q in pages if q > 2 and l.strip()[:30] in t2), None) == int(n))
print(d.page_count, "pages |", len(d.get_toc()), "bookmarks | TOC", f"{ok}/{len(pairs)} correct |",
      "stray markdown:", t.count("**") + t.count("__"))
PY
```

Green means: `stray markdown: 0`, TOC entries all correct, bookmark count ≈ heading count, and the
rasterised cover/TOC/table pages show no overlap, clipping or tofu.
