#!/usr/bin/env python3
"""
a11y_audit.py — Web Accessibility Auditor
==========================================
Audits an HTML file or URL for WCAG 2.2 Level A & AA issues and generates
a rich, self-contained HTML report.

Usage:
    python a11y_audit.py <path-or-url> [--output <report.html>]

Dependencies: Python 3.8+ standard library only (html.parser, urllib, re, json)
"""

import argparse
import html as html_module
import json
import math
import os
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from typing import List, Optional, Tuple
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"critical": 0, "serious": 1, "moderate": 2, "info": 3}
SEVERITY_COLORS = {
    "critical": "#d93025",
    "serious":  "#e8710a",
    "moderate": "#f5a623",
    "info":     "#1a73e8",
}
SEVERITY_BG = {
    "critical": "#fce8e6",
    "serious":  "#fef0e6",
    "moderate": "#fef9e6",
    "info":     "#e8f0fe",
}


@dataclass
class Issue:
    severity: str          # critical | serious | moderate | info
    category: str          # Structure, Images, Forms, Keyboard, Links, ARIA, Contrast
    wcag: str              # e.g. "1.1.1"
    wcag_level: str        # A | AA
    title: str
    description: str
    fix: str
    element: str = ""      # Short HTML snippet of the offending element
    count: int = 1         # How many elements share this issue


@dataclass
class AuditResult:
    source: str
    html: str
    issues: List[Issue] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def score(self) -> int:
        """0–100 accessibility score (higher is better)."""
        if not self.issues:
            return 100
        weights = {"critical": 20, "serious": 10, "moderate": 4, "info": 1}
        penalty = sum(weights.get(i.severity, 1) * i.count for i in self.issues)
        return max(0, min(100, 100 - penalty))

    def by_severity(self, sev: str) -> List[Issue]:
        return [i for i in self.issues if i.severity == sev]

    def count_by_severity(self, sev: str) -> int:
        return sum(i.count for i in self.issues if i.severity == sev)


# ---------------------------------------------------------------------------
# Minimal DOM-like tree built with html.parser
# ---------------------------------------------------------------------------

class Node:
    def __init__(self, tag: str, attrs: dict, parent=None, line: int = 0):
        self.tag = tag.lower() if tag else ""
        self.attrs = {k.lower(): (v or "") for k, v in attrs}
        self.parent = parent
        self.children: List["Node"] = []
        self.text_parts: List[str] = []
        self.line = line

    @property
    def text(self) -> str:
        parts = list(self.text_parts)
        for c in self.children:
            parts.append(c.full_text)
        return " ".join(p.strip() for p in parts if p.strip())

    @property
    def full_text(self) -> str:
        return self.text

    def get(self, attr: str, default: str = "") -> str:
        return self.attrs.get(attr.lower(), default)

    def has_attr(self, attr: str) -> bool:
        return attr.lower() in self.attrs

    def outerhtml(self, max_len: int = 120) -> str:
        attr_str = ""
        for k, v in list(self.attrs.items())[:5]:
            if v:
                attr_str += f' {k}="{html_module.escape(v[:60])}"'
            else:
                attr_str += f" {k}"
        raw = f"<{self.tag}{attr_str}>"
        return raw[:max_len] + ("…" if len(raw) > max_len else "")


class DOMParser(HTMLParser):
    VOID_ELEMENTS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self):
        super().__init__()
        self.root = Node("__root__", [], line=0)
        self._stack: List[Node] = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, parent=self._stack[-1], line=self.getpos()[0])
        self._stack[-1].children.append(node)
        if tag.lower() not in self.VOID_ELEMENTS:
            self._stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag.lower():
                self._stack = self._stack[:i]
                return

    def handle_data(self, data):
        if self._stack:
            self._stack[-1].text_parts.append(data)

    def all_nodes(self) -> List[Node]:
        result = []
        def walk(n):
            result.append(n)
            for c in n.children:
                walk(c)
        walk(self.root)
        return result

    def find(self, tag: str) -> List[Node]:
        return [n for n in self.all_nodes() if n.tag == tag.lower()]

    def find_one(self, tag: str) -> Optional[Node]:
        nodes = self.find(tag)
        return nodes[0] if nodes else None

    def find_by_id(self, id_val: str) -> Optional[Node]:
        for n in self.all_nodes():
            if n.get("id") == id_val:
                return n
        return None

    def all_ids(self) -> List[str]:
        return [n.get("id") for n in self.all_nodes() if n.has_attr("id") and n.get("id")]


def parse_html(source: str) -> Tuple[DOMParser, str]:
    """Fetch (if URL) and parse HTML, returning (dom, raw_html)."""
    if source.startswith("http://") or source.startswith("https://"):
        req = urllib.request.Request(source, headers={"User-Agent": "a11y-audit/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    else:
        with open(source, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    dom = DOMParser()
    dom.feed(raw)
    return dom, raw


# ---------------------------------------------------------------------------
# Color contrast helper
# ---------------------------------------------------------------------------

def parse_color(css: str) -> Optional[Tuple[int, int, int]]:
    """Parse a CSS hex or rgb() color. Returns (r, g, b) or None."""
    css = css.strip().lower()
    m = re.match(r"#([0-9a-f]{6})", css)
    if m:
        h = m.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    m = re.match(r"#([0-9a-f]{3})$", css)
    if m:
        h = m.group(1)
        return int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16)
    m = re.match(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", css)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def relative_luminance(r: int, g: int, b: int) -> float:
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    l1 = relative_luminance(*c1)
    l2 = relative_luminance(*c2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def is_large_text(style: str) -> bool:
    m = re.search(r"font-size\s*:\s*([\d.]+)(px|pt|em|rem)", style)
    if not m:
        return False
    val, unit = float(m.group(1)), m.group(2)
    px = val if unit == "px" else val * 16 if unit in ("em", "rem") else val * (4/3)
    bold = bool(re.search(r"font-weight\s*:\s*(bold|[789]\d\d)", style))
    return px >= 24 or (bold and px >= 18.67)


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

def check_lang(dom: DOMParser) -> List[Issue]:
    issues = []
    html_el = dom.find_one("html")
    if not html_el:
        issues.append(Issue(
            severity="critical", category="Structure", wcag="3.1.1", wcag_level="A",
            title="Page has no <html> element",
            description="The document is missing an <html> root element.",
            fix='Add <!DOCTYPE html><html lang="en"> at the top of the document.',
        ))
    elif not html_el.has_attr("lang") or not html_el.get("lang").strip():
        issues.append(Issue(
            severity="serious", category="Structure", wcag="3.1.1", wcag_level="A",
            title='<html> element missing lang attribute',
            description="Screen readers rely on the lang attribute to choose the correct voice/pronunciation engine.",
            fix='Add a lang attribute: <html lang="en">. Use the appropriate BCP 47 language tag.',
            element=html_el.outerhtml(),
        ))
    return issues


def check_title(dom: DOMParser) -> List[Issue]:
    title_el = dom.find_one("title")
    if not title_el or not title_el.text.strip():
        return [Issue(
            severity="serious", category="Structure", wcag="2.4.2", wcag_level="A",
            title="Page is missing a descriptive <title>",
            description="The page title is what screen readers announce first and what appears in browser tabs/history.",
            fix="Add <title>Descriptive Page Name – Site Name</title> in the <head>. Each page should have a unique, descriptive title.",
            element=title_el.outerhtml() if title_el else "<title> not found",
        )]
    return []


def check_viewport(dom: DOMParser) -> List[Issue]:
    for meta in dom.find("meta"):
        if meta.get("name").lower() == "viewport":
            content = meta.get("content").lower()
            if "user-scalable=no" in content or "maximum-scale=1" in content:
                return [Issue(
                    severity="serious", category="Structure", wcag="1.4.4", wcag_level="AA",
                    title="Viewport meta tag disables user zoom",
                    description="Preventing zoom breaks access for low-vision users who rely on browser zoom.",
                    fix='Remove user-scalable=no and maximum-scale=1 from the viewport meta. Use: <meta name="viewport" content="width=device-width, initial-scale=1">',
                    element=meta.outerhtml(),
                )]
    return []


def check_landmarks(dom: DOMParser) -> List[Issue]:
    issues = []
    mains = dom.find("main") + [n for n in dom.all_nodes()
                                  if n.get("role") == "main"]
    if not mains:
        issues.append(Issue(
            severity="serious", category="Structure", wcag="1.3.1", wcag_level="A",
            title="No <main> landmark found",
            description="Without a <main> landmark, keyboard users cannot skip directly to the primary content.",
            fix="Wrap the page's primary content in a <main> element. There should be exactly one <main> per page.",
        ))
    elif len(mains) > 1:
        issues.append(Issue(
            severity="moderate", category="Structure", wcag="1.3.1", wcag_level="A",
            title=f"Multiple <main> landmarks found ({len(mains)})",
            description="A page should have exactly one <main> landmark. Multiple <main> elements confuse screen reader navigation.",
            fix="Remove extra <main> elements. Only the primary content region should be <main>.",
            count=len(mains),
        ))
    return issues


def check_skip_link(dom: DOMParser) -> List[Issue]:
    all_focusable = [n for n in dom.all_nodes()
                     if n.tag in ("a", "button", "input", "select", "textarea")
                     or (n.has_attr("tabindex") and n.get("tabindex") != "-1")]
    if not all_focusable:
        return []
    first = all_focusable[0]
    # Check if it's an anchor pointing to an id (skip link pattern)
    if first.tag == "a" and first.get("href", "").startswith("#"):
        return []
    # Look for any skip link in the first 5 focusable elements
    for node in all_focusable[:5]:
        href = node.get("href", "")
        if href.startswith("#") and node.tag == "a":
            return []
    return [Issue(
        severity="serious", category="Structure", wcag="2.4.1", wcag_level="A",
        title="No skip navigation link found",
        description="Without a skip link, keyboard users must Tab through all navigation links on every page load.",
        fix='Add <a class="skip-link" href="#main">Skip to main content</a> as the very first element in <body>, styled to be visible on focus.',
    )]


def check_headings(dom: DOMParser) -> List[Issue]:
    issues = []
    headings = [(n, int(n.tag[1])) for n in dom.all_nodes() if re.match(r"^h[1-6]$", n.tag)]
    if not headings:
        return []

    h1s = [n for n, lvl in headings if lvl == 1]
    if not h1s:
        issues.append(Issue(
            severity="serious", category="Structure", wcag="1.3.1", wcag_level="A",
            title="Page has no <h1>",
            description="Every page should have exactly one <h1> that describes its main topic.",
            fix="Add a single <h1> that describes the page's primary content.",
        ))
    elif len(h1s) > 1:
        issues.append(Issue(
            severity="moderate", category="Structure", wcag="2.4.6", wcag_level="AA",
            title=f"Multiple <h1> elements found ({len(h1s)})",
            description="Multiple <h1> elements weaken the document outline. Use a single <h1> for the page title.",
            fix="Keep only one <h1>. Demote others to <h2> or appropriate level.",
            count=len(h1s),
        ))

    skipped = []
    levels = [lvl for _, lvl in headings]
    for i in range(1, len(levels)):
        if levels[i] > levels[i - 1] + 1:
            skipped.append((headings[i][0], levels[i - 1], levels[i]))
    if skipped:
        el = skipped[0][0]
        issues.append(Issue(
            severity="moderate", category="Structure", wcag="1.3.1", wcag_level="A",
            title=f"Heading level(s) skipped ({len(skipped)} occurrence(s))",
            description=f"Heading levels should not be skipped (e.g. jumping from h{skipped[0][1]} to h{skipped[0][2]}). This breaks the document outline.",
            fix="Use heading levels in order: h1 → h2 → h3. Choose heading level for structure, not visual appearance.",
            element=el.outerhtml(),
            count=len(skipped),
        ))
    return issues


def check_images(dom: DOMParser) -> List[Issue]:
    issues = []
    imgs = dom.find("img")
    missing_alt, empty_suspicious = [], []

    for img in imgs:
        if not img.has_attr("alt"):
            missing_alt.append(img)
        elif img.get("alt").strip() == "" and not img.has_attr("role"):
            # empty alt is fine for decorative; flag if it looks like it has meaningful src
            src = img.get("src", "")
            if any(kw in src.lower() for kw in ["logo", "icon", "banner", "hero", "product", "photo"]):
                empty_suspicious.append(img)

    if missing_alt:
        issues.append(Issue(
            severity="critical", category="Images", wcag="1.1.1", wcag_level="A",
            title=f"{len(missing_alt)} image(s) missing alt attribute",
            description="Images without alt attributes are announced by screen readers as the filename, which is meaningless.",
            fix='Add alt="descriptive text" to meaningful images. Add alt="" to purely decorative images.',
            element=missing_alt[0].outerhtml(),
            count=len(missing_alt),
        ))

    if empty_suspicious:
        issues.append(Issue(
            severity="moderate", category="Images", wcag="1.1.1", wcag_level="A",
            title=f"{len(empty_suspicious)} image(s) may need alt text (empty alt, meaningful-looking src)",
            description="Images with empty alt and a content-looking src may be meaningful. Verify these are truly decorative.",
            fix='If the image conveys information, add descriptive alt text. If truly decorative, keep alt="" and consider adding role="presentation".',
            element=empty_suspicious[0].outerhtml(),
            count=len(empty_suspicious),
        ))

    # SVG without accessible name
    bad_svgs = []
    for svg in dom.find("svg"):
        has_title = any(c.tag == "title" for c in svg.children)
        if (not svg.has_attr("aria-hidden") and not svg.has_attr("aria-label")
                and not svg.has_attr("aria-labelledby") and not has_title):
            # Only flag interactive/standalone SVGs (has no aria-hidden)
            bad_svgs.append(svg)
    if bad_svgs:
        issues.append(Issue(
            severity="moderate", category="Images", wcag="1.1.1", wcag_level="A",
            title=f"{len(bad_svgs)} SVG element(s) lack accessible name or aria-hidden",
            description="SVGs used as images need an accessible name. Decorative SVGs should have aria-hidden='true'.",
            fix='For informative SVGs, add a <title> child element or aria-label. For decorative SVGs, add aria-hidden="true" focusable="false".',
            element=bad_svgs[0].outerhtml(),
            count=len(bad_svgs),
        ))

    # Video captions
    for video in dom.find("video"):
        tracks = video.children
        has_caption = any(c.tag == "track" and "caption" in c.get("kind", "").lower()
                          for c in tracks)
        if not has_caption:
            issues.append(Issue(
                severity="critical", category="Images", wcag="1.2.2", wcag_level="A",
                title="<video> element missing captions track",
                description="Videos with audio must have synchronized captions for deaf and hard-of-hearing users.",
                fix='Add <track kind="captions" src="captions.vtt" srclang="en" label="English"> inside the <video> element.',
                element=video.outerhtml(),
            ))
    return issues


def check_forms(dom: DOMParser) -> List[Issue]:
    issues = []
    inputs = [n for n in dom.find("input")
              if n.get("type", "text").lower() not in ("hidden", "submit", "button", "reset", "image")]
    inputs += dom.find("select")
    inputs += dom.find("textarea")

    all_ids = dom.all_ids()
    unlabeled = []
    for inp in inputs:
        inp_id = inp.get("id")
        has_for_label = any(
            lbl.get("for") == inp_id
            for lbl in dom.find("label")
            if inp_id
        )
        is_wrapped = inp.parent and inp.parent.tag == "label"
        has_aria_label = inp.has_attr("aria-label") and inp.get("aria-label").strip()
        has_aria_lb = inp.has_attr("aria-labelledby") and inp.get("aria-labelledby").strip()
        if not any([has_for_label, is_wrapped, has_aria_label, has_aria_lb]):
            unlabeled.append(inp)

    if unlabeled:
        issues.append(Issue(
            severity="critical", category="Forms", wcag="1.3.1", wcag_level="A",
            title=f"{len(unlabeled)} form control(s) have no accessible label",
            description="Form controls without labels leave screen reader users unable to understand what to enter.",
            fix='Use <label for="inputId">Label text</label> with matching id on the input, or wrap the input in a <label>, or add aria-label="...".',
            element=unlabeled[0].outerhtml(),
            count=len(unlabeled),
        ))

    # Placeholder-only label (input with placeholder but no label)
    placeholder_only = [inp for inp in unlabeled if inp.has_attr("placeholder")]
    if placeholder_only:
        issues.append(Issue(
            severity="serious", category="Forms", wcag="3.3.2", wcag_level="A",
            title=f"{len(placeholder_only)} input(s) use placeholder as the only label",
            description="Placeholder text disappears on focus and has low contrast. It does not substitute for a label.",
            fix="Add a visible <label> element. The placeholder can remain as a hint but must not be the sole identifier.",
            element=placeholder_only[0].outerhtml(),
            count=len(placeholder_only),
        ))

    # Radio/checkbox groups without fieldset
    radio_groups: dict = {}
    for inp in dom.find("input"):
        if inp.get("type", "").lower() == "radio" and inp.get("name"):
            radio_groups.setdefault(inp.get("name"), []).append(inp)

    for name, radios in radio_groups.items():
        if len(radios) > 1:
            # Check if wrapped in fieldset
            in_fieldset = any(_ancestor_tag(r, "fieldset") for r in radios)
            if not in_fieldset:
                issues.append(Issue(
                    severity="moderate", category="Forms", wcag="1.3.1", wcag_level="A",
                    title=f'Radio button group "{name}" not wrapped in <fieldset>',
                    description="Related radio buttons should be grouped in a <fieldset> with a <legend> so screen readers announce the group name.",
                    fix=f'Wrap the radio group in <fieldset><legend>Group label here</legend>…radios…</fieldset>.',
                    element=radios[0].outerhtml(),
                ))
    return issues


def _ancestor_tag(node: Node, tag: str) -> bool:
    parent = node.parent
    while parent:
        if parent.tag == tag:
            return True
        parent = parent.parent
    return False


def check_keyboard(dom: DOMParser) -> List[Issue]:
    issues = []
    bad_tabindex = []
    for n in dom.all_nodes():
        if n.has_attr("tabindex"):
            try:
                val = int(n.get("tabindex"))
                if val > 0:
                    bad_tabindex.append(n)
            except ValueError:
                pass

    if bad_tabindex:
        issues.append(Issue(
            severity="serious", category="Keyboard", wcag="2.4.3", wcag_level="A",
            title=f"{len(bad_tabindex)} element(s) use positive tabindex",
            description="Positive tabindex values create a custom tab order that is almost always wrong and confusing.",
            fix="Remove tabindex values > 0. Use tabindex='0' to include an element in natural order, or tabindex='-1' for programmatic focus only.",
            element=bad_tabindex[0].outerhtml(),
            count=len(bad_tabindex),
        ))

    # Clickable divs/spans (non-interactive elements with onclick)
    clickable_non_interactive = []
    for n in dom.all_nodes():
        if n.tag in ("div", "span", "p", "li", "td") and n.has_attr("onclick"):
            if not n.has_attr("role") and not n.has_attr("tabindex"):
                clickable_non_interactive.append(n)

    if clickable_non_interactive:
        issues.append(Issue(
            severity="critical", category="Keyboard", wcag="2.1.1", wcag_level="A",
            title=f"{len(clickable_non_interactive)} non-interactive element(s) have onclick with no role/tabindex",
            description="<div> and <span> with onclick handlers are not focusable or keyboard-operable by default.",
            fix="Replace with <button> or <a href>. If a div must be used, add role='button' tabindex='0' and handle keydown for Enter/Space.",
            element=clickable_non_interactive[0].outerhtml(),
            count=len(clickable_non_interactive),
        ))

    # <a> with no href
    anchors_no_href = [n for n in dom.find("a") if not n.has_attr("href")]
    if anchors_no_href:
        issues.append(Issue(
            severity="serious", category="Keyboard", wcag="2.1.1", wcag_level="A",
            title=f"{len(anchors_no_href)} <a> element(s) have no href attribute",
            description="An <a> without href is not keyboard focusable and is announced as 'clickable' without a role.",
            fix="Add href if it's a navigation link. If it's an action button, use <button> instead.",
            element=anchors_no_href[0].outerhtml(),
            count=len(anchors_no_href),
        ))
    return issues


def check_links_buttons(dom: DOMParser) -> List[Issue]:
    issues = []

    # Empty links
    empty_links = []
    for a in dom.find("a"):
        has_text = bool(a.text.strip())
        has_aria_label = a.has_attr("aria-label") and a.get("aria-label").strip()
        has_aria_lb = a.has_attr("aria-labelledby") and a.get("aria-labelledby").strip()
        has_img_alt = any(c.tag == "img" and c.get("alt", "").strip() for c in a.children)
        has_svg_title = any(c.tag == "svg" and any(gc.tag == "title" for gc in c.children)
                            for c in a.children)
        if not any([has_text, has_aria_label, has_aria_lb, has_img_alt, has_svg_title]):
            empty_links.append(a)

    if empty_links:
        issues.append(Issue(
            severity="critical", category="Links & Buttons", wcag="2.4.4", wcag_level="A",
            title=f"{len(empty_links)} link(s) have no accessible name",
            description="Links without text are announced by screen readers as 'link' with no destination context.",
            fix="Add descriptive text inside the <a>, or add aria-label='destination description'.",
            element=empty_links[0].outerhtml(),
            count=len(empty_links),
        ))

    # Empty buttons
    empty_buttons = []
    for btn in dom.find("button"):
        has_text = bool(btn.text.strip())
        has_aria_label = btn.has_attr("aria-label") and btn.get("aria-label").strip()
        has_aria_lb = btn.has_attr("aria-labelledby") and btn.get("aria-labelledby").strip()
        has_img_alt = any(c.tag == "img" and c.get("alt", "").strip() for c in btn.children)
        if not any([has_text, has_aria_label, has_aria_lb, has_img_alt]):
            empty_buttons.append(btn)

    if empty_buttons:
        issues.append(Issue(
            severity="critical", category="Links & Buttons", wcag="4.1.2", wcag_level="A",
            title=f"{len(empty_buttons)} button(s) have no accessible name",
            description="Buttons without text are announced as 'button' with no description of their action.",
            fix="Add descriptive text inside the <button>, or add aria-label='Action description'.",
            element=empty_buttons[0].outerhtml(),
            count=len(empty_buttons),
        ))

    # Generic link text
    GENERIC = {"click here", "here", "read more", "more", "learn more", "click",
               "link", "this link", "details", "info", "information"}
    generic_links = [a for a in dom.find("a")
                     if a.text.strip().lower() in GENERIC
                     and not a.has_attr("aria-label")
                     and not a.has_attr("aria-labelledby")]
    if generic_links:
        issues.append(Issue(
            severity="moderate", category="Links & Buttons", wcag="2.4.4", wcag_level="A",
            title=f"{len(generic_links)} link(s) use generic text (e.g. 'click here', 'read more')",
            description="Generic link text forces screen reader users to listen to surrounding content for context.",
            fix='Make link text descriptive of the destination: "Read the annual report" instead of "read more". Or add aria-label="Read the 2025 annual report" if the visible text must stay short.',
            element=generic_links[0].outerhtml(),
            count=len(generic_links),
        ))
    return issues


def check_aria(dom: DOMParser) -> List[Issue]:
    issues = []
    all_ids = set(dom.all_ids())

    # Duplicate IDs
    id_list = [n.get("id") for n in dom.all_nodes() if n.has_attr("id") and n.get("id")]
    seen, dupes = set(), set()
    for id_val in id_list:
        if id_val in seen:
            dupes.add(id_val)
        seen.add(id_val)
    if dupes:
        issues.append(Issue(
            severity="serious", category="ARIA", wcag="4.1.1", wcag_level="A",
            title=f"{len(dupes)} duplicate id attribute(s) found",
            description="Duplicate IDs break aria-labelledby, aria-describedby, and <label for='...'> associations.",
            fix="Every id must be unique per page. Rename or remove duplicate id values.",
            element=f"Duplicate ids: {', '.join(list(dupes)[:5])}",
            count=len(dupes),
        ))

    # aria-labelledby pointing to nonexistent id
    broken_lb = []
    for n in dom.all_nodes():
        if n.has_attr("aria-labelledby"):
            for ref_id in n.get("aria-labelledby").split():
                if ref_id not in all_ids:
                    broken_lb.append((n, ref_id))
    if broken_lb:
        issues.append(Issue(
            severity="serious", category="ARIA", wcag="4.1.2", wcag_level="A",
            title=f"{len(broken_lb)} aria-labelledby reference(s) point to missing id",
            description="When aria-labelledby references a non-existent id, the accessible name is empty.",
            fix="Ensure every id referenced by aria-labelledby exists in the DOM.",
            element=broken_lb[0][0].outerhtml(),
            count=len(broken_lb),
        ))

    # aria-describedby pointing to nonexistent id
    broken_db = []
    for n in dom.all_nodes():
        if n.has_attr("aria-describedby"):
            for ref_id in n.get("aria-describedby").split():
                if ref_id not in all_ids:
                    broken_db.append((n, ref_id))
    if broken_db:
        issues.append(Issue(
            severity="moderate", category="ARIA", wcag="4.1.2", wcag_level="A",
            title=f"{len(broken_db)} aria-describedby reference(s) point to missing id",
            description="When aria-describedby references a non-existent id, the description is silently lost.",
            fix="Ensure every id referenced by aria-describedby exists in the DOM.",
            element=broken_db[0][0].outerhtml(),
            count=len(broken_db),
        ))

    # role="img" without aria-label
    role_img = [n for n in dom.all_nodes()
                if n.get("role") == "img"
                and not n.has_attr("aria-label")
                and not n.has_attr("aria-labelledby")]
    if role_img:
        issues.append(Issue(
            severity="serious", category="ARIA", wcag="1.1.1", wcag_level="A",
            title=f"{len(role_img)} element(s) with role='img' have no accessible name",
            description='An element with role="img" must have an accessible name via aria-label or aria-labelledby.',
            fix='Add aria-label="Description of image" to the element.',
            element=role_img[0].outerhtml(),
            count=len(role_img),
        ))

    # Redundant role (e.g. <nav role="navigation">)
    REDUNDANT_ROLES = {
        "nav": "navigation", "main": "main", "header": "banner",
        "footer": "contentinfo", "aside": "complementary", "form": "form",
        "article": "article", "section": "region", "button": "button",
        "a": "link", "ul": "list", "ol": "list",
    }
    redundant = [n for n in dom.all_nodes()
                 if n.tag in REDUNDANT_ROLES and n.get("role") == REDUNDANT_ROLES[n.tag]]
    if redundant:
        issues.append(Issue(
            severity="info", category="ARIA", wcag="4.1.2", wcag_level="A",
            title=f"{len(redundant)} element(s) have a redundant ARIA role",
            description="Assigning a native element its own implicit role (e.g. <nav role='navigation'>) is harmless but unnecessary.",
            fix="Remove the role attribute — the HTML element already provides it.",
            element=redundant[0].outerhtml(),
            count=len(redundant),
        ))
    return issues


def check_color_contrast(dom: DOMParser) -> List[Issue]:
    issues = []
    fail_normal, fail_large = [], []

    for n in dom.all_nodes():
        style = n.get("style")
        if not style or "color" not in style:
            continue
        fg_match = re.search(r"(?<![a-z-])color\s*:\s*([^;]+)", style)
        bg_match = re.search(r"background(?:-color)?\s*:\s*([^;]+)", style)
        if not fg_match or not bg_match:
            continue
        fg = parse_color(fg_match.group(1).strip())
        bg = parse_color(bg_match.group(1).strip())
        if not fg or not bg:
            continue
        ratio = contrast_ratio(fg, bg)
        large = is_large_text(style)
        threshold = 3.0 if large else 4.5
        if ratio < threshold:
            entry = (n, ratio, threshold, large)
            if large:
                fail_large.append(entry)
            else:
                fail_normal.append(entry)

    if fail_normal:
        n, ratio, thresh, _ = fail_normal[0]
        issues.append(Issue(
            severity="serious", category="Contrast", wcag="1.4.3", wcag_level="AA",
            title=f"{len(fail_normal)} element(s) fail normal-text contrast (< 4.5:1)",
            description=f"Insufficient contrast makes text hard to read for low-vision users. Worst found: {ratio:.2f}:1 (required ≥4.5:1).",
            fix="Increase the contrast between foreground and background colors. Use a contrast checker at https://webaim.org/resources/contrastchecker/",
            element=n.outerhtml(),
            count=len(fail_normal),
        ))

    if fail_large:
        n, ratio, thresh, _ = fail_large[0]
        issues.append(Issue(
            severity="moderate", category="Contrast", wcag="1.4.3", wcag_level="AA",
            title=f"{len(fail_large)} large-text element(s) fail contrast (< 3:1)",
            description=f"Large text (≥24px or ≥18.7px bold) requires a minimum 3:1 contrast ratio. Worst found: {ratio:.2f}:1.",
            fix="Darken the text or lighten the background to achieve ≥3:1. Large text is ≥24px normal weight or ≥18.7px bold.",
            element=n.outerhtml(),
            count=len(fail_large),
        ))
    return issues


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_audit(source: str) -> AuditResult:
    print(f"Fetching and parsing: {source}")
    dom, raw_html = parse_html(source)
    result = AuditResult(source=source, html=raw_html)

    checks = [
        check_lang, check_title, check_viewport,
        check_landmarks, check_skip_link, check_headings,
        check_images, check_forms, check_keyboard,
        check_links_buttons, check_aria, check_color_contrast,
    ]
    for check in checks:
        try:
            result.issues.extend(check(dom))
        except Exception as exc:
            result.issues.append(Issue(
                severity="info", category="Structure", wcag="—", wcag_level="—",
                title=f"Check '{check.__name__}' encountered an error",
                description=str(exc),
                fix="This may indicate malformed HTML. Validate your HTML at https://validator.w3.org/",
            ))

    result.issues.sort(key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), i.category))
    return result


# ---------------------------------------------------------------------------
# HTML report generator
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return html_module.escape(str(s))


def _gauge_svg(score: int) -> str:
    color = "#34a853" if score >= 80 else "#e8710a" if score >= 50 else "#d93025"
    # Semi-circular gauge: arc from 180° to 0° (left to right)
    r = 70
    cx, cy = 90, 90
    angle = math.pi * (1 - score / 100)
    ex = cx + r * math.cos(angle)
    ey = cy - r * math.sin(angle)
    large_arc = 1 if score < 50 else 0
    # Background arc (full 180)
    return f"""<svg width="180" height="100" viewBox="0 0 180 100" aria-label="Accessibility score: {score} out of 100">
  <path d="M{cx-r},{cy} A{r},{r} 0 0,1 {cx+r},{cy}" fill="none" stroke="#e0e0e0" stroke-width="14" stroke-linecap="round"/>
  <path d="M{cx-r},{cy} A{r},{r} 0 0,1 {ex:.2f},{ey:.2f}" fill="none" stroke="{color}" stroke-width="14" stroke-linecap="round"/>
  <text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="28" font-weight="700" fill="{color}">{score}</text>
  <text x="{cx}" y="{cy+16}" text-anchor="middle" font-size="11" fill="#666">/100</text>
</svg>"""


def generate_report(result: AuditResult, output_path: str) -> None:
    score = result.score()
    score_label = "Good" if score >= 80 else "Needs Work" if score >= 50 else "Poor"
    score_color = "#34a853" if score >= 80 else "#e8710a" if score >= 50 else "#d93025"

    counts = {sev: result.count_by_severity(sev)
              for sev in ("critical", "serious", "moderate", "info")}
    total_issues = sum(counts.values())

    # Category breakdown
    categories = {}
    for issue in result.issues:
        categories.setdefault(issue.category, 0)
        categories[issue.category] += issue.count
    cat_max = max(categories.values(), default=1)

    categories_html = ""
    cat_colors = {
        "Structure": "#4285f4", "Images": "#ea4335", "Forms": "#fbbc04",
        "Keyboard": "#34a853", "Links & Buttons": "#ff6d00",
        "ARIA": "#9c27b0", "Contrast": "#00acc1",
    }
    for cat, cnt in sorted(categories.items(), key=lambda x: -x[1]):
        pct = int(cnt / cat_max * 100)
        col = cat_colors.get(cat, "#666")
        categories_html += f"""
        <div class="cat-row">
          <div class="cat-label">{_esc(cat)}</div>
          <div class="cat-bar-wrap">
            <div class="cat-bar" style="width:{pct}%;background:{col}"></div>
          </div>
          <div class="cat-count">{cnt}</div>
        </div>"""

    # Build issue rows
    rows_html = ""
    for idx, issue in enumerate(result.issues):
        sev = issue.severity
        sc = SEVERITY_COLORS.get(sev, "#666")
        bg = SEVERITY_BG.get(sev, "#fff")
        el_html = f'<code class="el-snippet">{_esc(issue.element)}</code>' if issue.element else ""
        count_badge = f'<span class="count-badge">×{issue.count}</span>' if issue.count > 1 else ""

        rows_html += f"""
        <tr class="issue-row" data-severity="{sev}" data-category="{_esc(issue.category)}">
          <td><span class="sev-badge" style="background:{bg};color:{sc}">{_esc(sev.upper())}</span></td>
          <td><span class="wcag-pill">WCAG {_esc(issue.wcag)}</span><br><small style="color:#666">{_esc(issue.wcag_level)}</small></td>
          <td class="cat-cell">{_esc(issue.category)}</td>
          <td>
            <strong>{_esc(issue.title)}</strong> {count_badge}
            <div class="issue-desc">{_esc(issue.description)}</div>
            {el_html}
          </td>
          <td class="fix-cell">{_esc(issue.fix)}</td>
        </tr>"""

    if not rows_html:
        rows_html = """<tr><td colspan="5" style="text-align:center;padding:40px;color:#34a853;font-size:1.1em">
          ✓ No issues detected by automated checks. Complete with a manual keyboard + screen reader review.
        </td></tr>"""

    # Build filter buttons
    sev_filters = ""
    for sev in ("critical", "serious", "moderate", "info"):
        col = SEVERITY_COLORS.get(sev, "#666")
        cnt = counts[sev]
        sev_filters += f'<button class="filter-btn" onclick="filterSev(\'{sev}\')" style="border-color:{col};color:{col}">{sev.title()} ({cnt})</button> '

    cat_filters = ""
    for cat in sorted(categories.keys()):
        cat_filters += f'<button class="filter-btn cat-filter-btn" onclick="filterCat(\'{_esc(cat)}\')">{_esc(cat)}</button> '

    source_display = _esc(result.source)
    gauge = _gauge_svg(score)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Accessibility Report – {source_display}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8f9fa; color: #202124; line-height: 1.5; }}
    a:focus-visible, button:focus-visible {{ outline: 3px solid #1a73e8; outline-offset: 2px; }}

    /* Header */
    .report-header {{ background: #1a1a2e; color: #fff; padding: 32px 40px; }}
    .report-header h1 {{ font-size: 1.6rem; font-weight: 700; margin-bottom: 6px; }}
    .report-header .meta {{ font-size: .85rem; color: #aab; }}

    /* Summary grid */
    .summary {{ display: grid; grid-template-columns: auto 1fr 1fr; gap: 24px;
                padding: 32px 40px; background: #fff; border-bottom: 1px solid #e0e0e0; }}
    .gauge-wrap {{ display:flex; flex-direction:column; align-items:center; gap:4px; }}
    .score-label {{ font-weight: 700; font-size: 1.05rem; color: {score_color}; }}
    .stat-cards {{ display: grid; grid-template-columns: repeat(2,1fr); gap: 12px; }}
    .stat-card {{ border-radius: 10px; padding: 16px 20px; }}
    .stat-card .num {{ font-size: 2rem; font-weight: 800; }}
    .stat-card .lbl {{ font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; opacity: .8; }}
    .stat-critical {{ background: #fce8e6; color: #d93025; }}
    .stat-serious  {{ background: #fef0e6; color: #e8710a; }}
    .stat-moderate {{ background: #fef9e6; color: #b07d00; }}
    .stat-info     {{ background: #e8f0fe; color: #1a73e8; }}
    .category-bars {{ background: #fff; }}
    .cat-row {{ display:flex; align-items:center; gap:10px; margin-bottom:10px; font-size:.85rem; }}
    .cat-label {{ width: 120px; text-align:right; flex-shrink:0; color:#555; }}
    .cat-bar-wrap {{ flex:1; background:#f1f3f4; border-radius:4px; height:14px; overflow:hidden; }}
    .cat-bar {{ height:100%; border-radius:4px; transition: width .3s; }}
    .cat-count {{ width:28px; text-align:right; font-weight:700; font-size:.8rem; }}

    /* Filters */
    .filters {{ padding: 20px 40px; background: #fff; border-bottom: 1px solid #e0e0e0; }}
    .filters h3 {{ font-size: .85rem; font-weight: 600; color: #555; margin-bottom: 10px; text-transform:uppercase; letter-spacing:.05em; }}
    .filter-btn {{ border: 2px solid #ccc; background: #fff; border-radius: 20px;
                   padding: 5px 14px; font-size: .8rem; cursor: pointer; margin-bottom: 6px; font-weight: 600; }}
    .filter-btn:hover {{ opacity: .8; }}
    .filter-btn.active {{ background: currentColor; }}
    .filter-btn.active span {{ color: #fff; }}
    #clear-btn {{ border-color: #888; color: #444; }}

    /* Table */
    .table-wrap {{ padding: 24px 40px; }}
    .table-wrap h2 {{ font-size: 1.15rem; font-weight: 700; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff;
             border-radius: 12px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    thead th {{ background: #f1f3f4; padding: 12px 14px; text-align: left;
                font-size: .78rem; font-weight: 700; text-transform: uppercase;
                letter-spacing: .06em; color: #555; border-bottom: 2px solid #e0e0e0; }}
    tbody tr {{ border-bottom: 1px solid #f1f3f4; }}
    tbody tr:last-child {{ border-bottom: none; }}
    tbody tr:hover {{ background: #fafafa; }}
    td {{ padding: 14px 14px; vertical-align: top; font-size: .88rem; }}
    .sev-badge {{ display:inline-block; padding: 3px 10px; border-radius: 12px;
                  font-size: .72rem; font-weight: 700; letter-spacing: .06em; white-space:nowrap; }}
    .wcag-pill {{ display:inline-block; background:#e8f0fe; color:#1a73e8; border-radius:4px;
                  padding: 2px 7px; font-size: .75rem; font-weight: 700; }}
    .el-snippet {{ display:block; margin-top:8px; background:#f8f9fa; border:1px solid #e0e0e0;
                   border-radius:6px; padding:6px 10px; font-size:.78rem; color:#444;
                   word-break:break-all; max-width:340px; }}
    .issue-desc {{ color: #555; margin-top:4px; font-size:.83rem; }}
    .fix-cell {{ font-size:.83rem; color:#3c4043; max-width:260px; }}
    .cat-cell {{ color: #555; white-space:nowrap; font-size:.82rem; }}
    .count-badge {{ background:#f1f3f4; border-radius:10px; padding:1px 8px; font-size:.75rem;
                    font-weight:700; color:#555; vertical-align:middle; }}
    .hidden {{ display: none !important; }}

    /* Footer */
    .report-footer {{ padding: 32px 40px; background: #1a1a2e; color: #aab; font-size:.83rem; margin-top: 24px; }}
    .report-footer a {{ color: #7eb3ff; }}
    .manual-note {{ background: #fff3cd; border: 1px solid #ffc107; border-radius:8px;
                    padding:14px 20px; margin: 24px 40px 0; font-size:.88rem; color:#856404; }}
    .manual-note strong {{ color: #533f03; }}

    @media(max-width:768px) {{
      .summary {{ grid-template-columns: 1fr; }}
      .report-header, .filters, .table-wrap, .manual-note {{ padding-left:16px; padding-right:16px; }}
      .table-wrap {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>

<header class="report-header">
  <h1>♿ Accessibility Audit Report</h1>
  <p class="meta">
    Source: <strong>{source_display}</strong> &nbsp;·&nbsp;
    Standard: <strong>WCAG 2.2 Level A &amp; AA</strong> &nbsp;·&nbsp;
    Generated: <strong>{_esc(result.timestamp)}</strong>
  </p>
</header>

<section class="summary" aria-label="Score summary">
  <div class="gauge-wrap">
    {gauge}
    <div class="score-label">{score_label}</div>
  </div>

  <div class="stat-cards" role="list" aria-label="Issue counts by severity">
    <div class="stat-card stat-critical" role="listitem">
      <div class="num">{counts['critical']}</div>
      <div class="lbl">Critical</div>
    </div>
    <div class="stat-card stat-serious" role="listitem">
      <div class="num">{counts['serious']}</div>
      <div class="lbl">Serious</div>
    </div>
    <div class="stat-card stat-moderate" role="listitem">
      <div class="num">{counts['moderate']}</div>
      <div class="lbl">Moderate</div>
    </div>
    <div class="stat-card stat-info" role="listitem">
      <div class="num">{counts['info']}</div>
      <div class="lbl">Info</div>
    </div>
  </div>

  <div class="category-bars" aria-label="Issues by category">
    <h3 style="font-size:.8rem;color:#555;text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px">By Category</h3>
    {categories_html if categories_html else '<p style="color:#aaa;font-size:.85rem">No issues found</p>'}
  </div>
</section>

<div class="manual-note" role="note">
  <strong>⚠ Important:</strong> Automated checks detect approximately <strong>25–40% of WCAG issues</strong>.
  Always follow up with a <strong>keyboard-only pass</strong> (Tab through everything without a mouse) and a
  <strong>screen reader pass</strong> (VoiceOver on macOS: ⌘F5; NVDA on Windows: free download).
</div>

<section class="filters" aria-label="Filter issues">
  <h3>Filter by severity</h3>
  <div>
    {sev_filters}
    <button class="filter-btn" id="clear-btn" onclick="clearFilters()">Show all ({total_issues})</button>
  </div>
  <h3 style="margin-top:12px">Filter by category</h3>
  <div>{cat_filters}</div>
</section>

<section class="table-wrap">
  <h2>Issues <span id="visible-count" style="font-size:.85rem;font-weight:400;color:#555">({total_issues} total)</span></h2>
  <table aria-label="Accessibility issues">
    <thead>
      <tr>
        <th scope="col">Severity</th>
        <th scope="col">WCAG</th>
        <th scope="col">Category</th>
        <th scope="col">Issue</th>
        <th scope="col">How to Fix</th>
      </tr>
    </thead>
    <tbody id="issue-tbody">
      {rows_html}
    </tbody>
  </table>
</section>

<footer class="report-footer">
  <p>
    <strong style="color:#fff">References:</strong>
    <a href="https://www.w3.org/TR/WCAG22/">WCAG 2.2</a> ·
    <a href="https://www.w3.org/WAI/WCAG22/quickref/">How to Meet WCAG (quick ref)</a> ·
    <a href="https://www.w3.org/WAI/ARIA/apg/">ARIA Authoring Practices Guide</a> ·
    <a href="https://webaim.org/resources/contrastchecker/">WebAIM Contrast Checker</a> ·
    <a href="https://wave.webaim.org/">WAVE Accessibility Evaluator</a>
  </p>
  <p style="margin-top:10px">Report generated by a11y_audit.py — for guidance only, not a substitute for full WCAG conformance testing.</p>
</footer>

<script>
(function() {{
  let activeSev = null, activeCat = null;

  function applyFilters() {{
    const rows = document.querySelectorAll('.issue-row');
    let visible = 0;
    rows.forEach(function(row) {{
      const sevMatch = !activeSev || row.dataset.severity === activeSev;
      const catMatch = !activeCat || row.dataset.category === activeCat;
      if (sevMatch && catMatch) {{ row.classList.remove('hidden'); visible++; }}
      else row.classList.add('hidden');
    }});
    document.getElementById('visible-count').textContent = '(' + visible + ' shown)';
  }}

  window.filterSev = function(sev) {{
    activeSev = activeSev === sev ? null : sev;
    applyFilters();
  }};
  window.filterCat = function(cat) {{
    activeCat = activeCat === cat ? null : cat;
    applyFilters();
  }};
  window.clearFilters = function() {{
    activeSev = null; activeCat = null; applyFilters();
  }};
}})();
</script>

</body>
</html>"""

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ Report written to: {output_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Audit an HTML file or URL for WCAG 2.2 accessibility issues and generate an HTML report."
    )
    parser.add_argument("source", help="Path to an HTML file or a URL (http/https)")
    parser.add_argument(
        "--output", "-o",
        default="/mnt/user-data/outputs/accessibility_report.html",
        help="Output path for the HTML report (default: /mnt/user-data/outputs/accessibility_report.html)",
    )
    args = parser.parse_args()

    result = run_audit(args.source)

    # Print summary
    score = result.score()
    print(f"\n{'='*60}")
    print(f"  ACCESSIBILITY AUDIT SUMMARY")
    print(f"{'='*60}")
    print(f"  Source : {result.source}")
    print(f"  Score  : {score}/100")
    print(f"  Issues : {len(result.issues)} types ({sum(i.count for i in result.issues)} total occurrences)")
    print(f"{'─'*60}")
    for sev in ("critical", "serious", "moderate", "info"):
        cnt = result.count_by_severity(sev)
        bar = "█" * min(cnt, 30)
        print(f"  {sev.upper():10s} {bar} {cnt}")
    print(f"{'='*60}\n")

    if result.issues:
        print("Top issues:")
        for issue in result.issues[:5]:
            print(f"  [{issue.severity.upper()}] {issue.title}")
        if len(result.issues) > 5:
            print(f"  … and {len(result.issues) - 5} more. See the full report.")

    generate_report(result, args.output)


if __name__ == "__main__":
    main()
