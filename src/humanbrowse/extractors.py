from __future__ import annotations

from typing import Optional

from lxml import html as lxml_html
from playwright.async_api import Page
from readability import Document

MAIN_SELECTORS = ["article", "main", "[role='main']", "#content"]


def _trim_text(text: str, max_chars: int) -> dict:
    cleaned = text.strip()
    truncated = False
    if max_chars > 0 and len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
        truncated = True
    return {"text": cleaned, "truncated": truncated, "chars": len(cleaned)}


async def _text_from_selector(page: Page, selector: str) -> Optional[str]:
    try:
        locator = page.locator(selector)
        if await locator.count() == 0:
            return None
        return await locator.first.inner_text()
    except Exception:
        return None


def _readability_text(html: str) -> str:
    doc = Document(html)
    summary = doc.summary(html_partial=True)
    root = lxml_html.fromstring(summary)
    return root.text_content()


async def extract_readable(page: Page, max_chars: int) -> dict:
    for selector in MAIN_SELECTORS:
        text = await _text_from_selector(page, selector)
        if text and text.strip():
            trimmed = _trim_text(text, max_chars)
            trimmed["source"] = selector
            return trimmed

    html = await page.content()
    readable = _readability_text(html)
    trimmed = _trim_text(readable, max_chars)
    trimmed["source"] = "readability"
    return trimmed


async def extract_selector(page: Page, selector: Optional[str], max_chars: int) -> dict:
    if selector:
        text = await _text_from_selector(page, selector) or ""
        trimmed = _trim_text(text, max_chars)
        trimmed["source"] = selector
        return trimmed
    return await extract_readable(page, max_chars)


async def extract_links(page: Page, scope: str = "main") -> dict:
    if scope == "main":
        selector = None
        for candidate in MAIN_SELECTORS:
            if await page.locator(candidate).count() > 0:
                selector = candidate
                break
        if selector:
            links = await page.evaluate(
                """
                (sel) => {
                  const root = document.querySelector(sel);
                  if (!root) return [];
                  return Array.from(root.querySelectorAll('a[href]')).map((a) => ({
                    text: (a.innerText || '').trim(),
                    href: a.href
                  }));
                }
                """,
                selector,
            )
        else:
            links = []
    else:
        links = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href]')).map((a) => ({
              text: (a.innerText || '').trim(),
              href: a.href
            }))
            """
        )
    return {"scope": scope, "count": len(links), "links": links}


async def extract_quote(
    page: Page, query: str, context_chars: int, max_chars: int
) -> dict:
    text = await page.inner_text("body")
    lowered = text.lower()
    needle = query.lower()
    idx = lowered.find(needle)
    if idx == -1:
        return {
            "query": query,
            "found": False,
            "context": "",
            "context_chars": context_chars,
        }
    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(query) + context_chars)
    context = text[start:end]
    trimmed = _trim_text(context, min(max_chars, len(context)))
    return {
        "query": query,
        "found": True,
        "context": trimmed["text"],
        "context_chars": context_chars,
        "truncated": trimmed["truncated"],
    }
