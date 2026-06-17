---
name: web-accessibility
description: >
  Use this skill whenever you need to audit, check, or report on the accessibility of a web page or HTML file.
  Triggers include: "check accessibility", "audit this page", "WCAG compliance", "a11y report",
  "screen reader", "color contrast", "keyboard navigation", "ARIA", "alt text", "generate accessibility report".
  This skill provides a Python script that analyses an HTML file or live URL and produces a rich, self-contained
  HTML accessibility report covering WCAG 2.2 Level A and AA criteria. Use it whenever the user wants to know
  what accessibility issues exist and get actionable guidance to fix them.
license: Provided as-is for accessibility guidance.
---

# Web Accessibility Audit Skill

## Overview

This skill audits an HTML page for WCAG 2.2 (Level A & AA) accessibility issues and generates a
**self-contained HTML report** with:

- Executive summary (score, issue counts by severity)
- Interactive issue table (filterable by severity and category)
- Per-issue details: WCAG criterion, impact, affected element snippet, and fix guidance
- Color-contrast checker (foreground/background pairs extracted from inline styles)
- Visual score gauge

The checker runs entirely with Python's **standard library** — no pip installs required.

---

## Quick Start

```bash
# Audit a local HTML file
python scripts/a11y_audit.py path/to/page.html

# Audit a live URL (fetches HTML and audits it)
python scripts/a11y_audit.py https://example.com

# Specify a custom output path for the report
python scripts/a11y_audit.py path/to/page.html --output /mnt/user-data/outputs/report.html
```

The script prints a summary to stdout and writes a full HTML report.
The default output path is `/mnt/user-data/outputs/accessibility_report.html`.

---

## What the Script Checks

### Structure & Semantics
| Check | WCAG | Level |
|---|---|---|
| `<html>` has a `lang` attribute | 3.1.1 | A |
| `<title>` exists and is non-empty | 2.4.2 | A |
| Exactly one `<main>` landmark | 1.3.1 | A |
| `<header>`, `<nav>`, `<footer>` landmarks present | 1.3.1 | A |
| Heading hierarchy (no skipped levels, one `<h1>`) | 1.3.1 / 2.4.6 | A / AA |
| Skip link present as first focusable element | 2.4.1 | A |
| Viewport meta doesn't block zoom | 1.4.4 | AA |

### Images & Media
| Check | WCAG | Level |
|---|---|---|
| All `<img>` have an `alt` attribute | 1.1.1 | A |
| `alt` is non-empty for meaningful images | 1.1.1 | A |
| SVG icons have `aria-hidden` or accessible name | 1.1.1 | A |
| `<video>` elements have a `<track kind="captions">` | 1.2.2 | A |

### Forms
| Check | WCAG | Level |
|---|---|---|
| All `<input>`, `<select>`, `<textarea>` have an associated label | 1.3.1 / 3.3.2 | A |
| `<fieldset>` used for radio/checkbox groups | 1.3.1 | A |
| Required fields marked with `required` attribute | 3.3.2 | A |
| Inputs have meaningful `autocomplete` where applicable | 1.3.5 | AA |

### Keyboard & Focus
| Check | WCAG | Level |
|---|---|---|
| No positive `tabindex` values | 2.4.3 | A |
| Interactive elements are natively focusable (not bare `<div onclick>`) | 2.1.1 | A |
| `<a>` tags have an `href` (not empty anchors used as buttons) | 2.1.1 | A |

### Links & Buttons
| Check | WCAG | Level |
|---|---|---|
| No empty `<a>` (no text, no `aria-label`) | 2.4.4 | A |
| No empty `<button>` (no text, no `aria-label`) | 4.1.2 | A |
| Links are distinguishable (not relying on color alone) | 1.4.1 | A |
| Generic link text ("click here", "read more") flagged | 2.4.4 | A |

### ARIA
| Check | WCAG | Level |
|---|---|---|
| `aria-labelledby` references exist in DOM | 4.1.2 | A |
| `aria-describedby` references exist in DOM | 4.1.2 | A |
| No duplicate `id` attributes | 4.1.1 | A |
| `role="img"` elements have `aria-label` | 1.1.1 | A |
| Interactive ARIA roles have required owned elements | 4.1.2 | A |

### Color Contrast (inline styles)
| Check | WCAG | Level |
|---|---|---|
| Text contrast ≥ 4.5:1 (normal) / 3:1 (large) | 1.4.3 | AA |
| UI component contrast ≥ 3:1 | 1.4.11 | AA |

---

## Severity Levels

| Level | Meaning |
|---|---|
| **Critical** | Blocks access entirely for some users (missing alt, keyboard trap, no label) |
| **Serious** | Significantly impairs access (contrast failure, missing landmark, skip link) |
| **Moderate** | Creates friction or confusion (generic link text, skipped heading, no autocomplete) |
| **Info** | Best-practice suggestions (redundant role, advisory improvements) |

---

## Report Layout

The generated HTML report contains:

1. **Header** – page title, URL/file audited, timestamp, WCAG version
2. **Score Gauge** – 0–100 score based on issues found, color-coded
3. **Summary Cards** – counts of Critical / Serious / Moderate / Info issues
4. **Category Breakdown** – horizontal bar chart per check category
5. **Issue Table** – every issue with: severity badge, WCAG criterion, element snippet, description, fix guidance
6. **Filters** – filter the table by severity or category with one click
7. **Footer** – reminder that automated checks are ~30% of WCAG; manual testing is required

---

## Limitations

Automated static analysis catches roughly **25–40% of all WCAG issues**. Things this script
cannot check (require manual testing):

- Whether alt text is *accurate and meaningful*
- Whether focus *order* is logical
- Whether dynamic content updates are announced via live regions
- Keyboard operability of custom widgets
- Actual color contrast from external CSS files (only inline styles checked)
- Cognitive load, plain language, understandable error messages
- Screen reader announcement quality

Always follow the automated audit with:
1. **Keyboard pass** – Tab through the page end-to-end with no mouse
2. **Screen reader pass** – VoiceOver (macOS, Cmd+F5), NVDA (Windows, free), or JAWS
3. **Zoom test** – 200% and 400% browser zoom; reflow at 320px width

---

## Files

| File | Purpose |
|---|---|
| `scripts/a11y_audit.py` | Main audit script – runs checks, generates HTML report |
| `scripts/checks/` | Individual check modules imported by the main script |

---

## References

- WCAG 2.2 standard — https://www.w3.org/TR/WCAG22/
- How to Meet WCAG (quick ref) — https://www.w3.org/WAI/WCAG22/quickref/
- WAI-ARIA Authoring Practices — https://www.w3.org/WAI/ARIA/apg/
- MDN Accessibility — <a href="https://developer.mozilla.org/en-US/docs/Web/Accessibility" rel="noreferrer noopener" title="https://developer.mozilla.org/en-us/docs/web/accessibility" target="_blank">https://developer.mozilla.org/en-US/docs/Web/Accessibility</a>