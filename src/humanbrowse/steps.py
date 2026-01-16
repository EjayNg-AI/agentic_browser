from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import Page

from .artifacts import RunArtifacts
from .config import Settings
from .extractors import extract_links, extract_quote, extract_readable, extract_selector
from .models import (
    ClickStep,
    ExtractReadableStep,
    ExtractStep,
    GotoStep,
    LinksStep,
    PauseForUserStep,
    PressStep,
    QuoteStep,
    ScreenshotStep,
    ScrollStep,
    Step,
    TypeStep,
    WaitForStep,
)
from .policy import DomainPolicy


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StepOutcome:
    status: str
    error: Optional[str] = None
    message: Optional[str] = None
    screenshot: Optional[str] = None


def _step_record(index: int, step: Step, status: str, result: dict) -> dict:
    return {
        "type": "step",
        "index": index,
        "timestamp": _utc_now(),
        "step": step.model_dump(),
        "status": status,
        "result": result,
    }


def _note_record(
    note_kind: str, url: str, title: str, content: dict, evidence: dict
) -> dict:
    return {
        "type": "note",
        "note_kind": note_kind,
        "url": url,
        "title": title,
        "timestamp": _utc_now(),
        "content": content,
        "evidence": evidence,
    }


def _policy_violation_record(
    kind: str, message: str, step_index: Optional[int] = None, step: Optional[Step] = None
) -> dict:
    record = {
        "type": "policy_violation",
        "kind": kind,
        "message": message,
        "timestamp": _utc_now(),
    }
    if step_index is not None:
        record["step_index"] = step_index
    if step is not None:
        record["step"] = step.model_dump()
    return record


async def _handle_goto(page: Page, step: GotoStep) -> dict:
    if step.wait_until:
        await page.goto(step.url, wait_until=step.wait_until)
    else:
        await page.goto(step.url)
    return {"url": page.url, "title": await page.title()}


async def _handle_wait_for(page: Page, step: WaitForStep) -> dict:
    if step.selector:
        await page.wait_for_selector(step.selector)
    elif step.text:
        locator = page.get_by_text(step.text)
        await locator.first.wait_for()
    elif step.load_state:
        await page.wait_for_load_state(step.load_state)
    return {"url": page.url, "title": await page.title()}


async def _handle_click(page: Page, step: ClickStep) -> dict:
    if step.selector:
        await page.click(step.selector)
    elif step.text:
        await page.get_by_text(step.text).first.click()
    elif step.role:
        await page.get_by_role(step.role).first.click()
    return {"url": page.url, "title": await page.title()}


async def _handle_type(page: Page, step: TypeStep) -> dict:
    await page.fill(step.selector, step.text)
    return {"url": page.url, "title": await page.title()}


async def _handle_press(page: Page, step: PressStep) -> dict:
    await page.keyboard.press(step.key)
    return {"url": page.url, "title": await page.title()}


async def _handle_scroll(page: Page, step: ScrollStep) -> dict:
    if step.to_selector:
        await page.locator(step.to_selector).scroll_into_view_if_needed()
    else:
        await page.mouse.wheel(0, step.pixels or 0)
    return {"url": page.url, "title": await page.title()}


async def _handle_screenshot(
    page: Page, step: ScreenshotStep, artifacts: RunArtifacts, index: int
) -> dict:
    path = artifacts.screenshot_path(step.label, index)
    await page.screenshot(path=str(path))
    return {
        "url": page.url,
        "title": await page.title(),
        "screenshot": str(path.relative_to(artifacts.run_dir)),
    }


async def _maybe_capture_html(
    page: Page, artifacts: RunArtifacts, index: int, label: Optional[str], enabled: bool
) -> Optional[str]:
    if not enabled:
        return None
    html = await page.content()
    path = artifacts.html_snapshot_path(label, index)
    path.write_text(html, encoding="utf-8")
    return str(path.relative_to(artifacts.run_dir))


async def execute_steps(
    page: Page,
    steps: list[Step],
    artifacts: RunArtifacts,
    settings: Settings,
    policy: Optional[DomainPolicy] = None,
) -> StepOutcome:
    start_time = time.monotonic()
    deadline = None
    if settings.max_total_runtime_s > 0:
        deadline = start_time + settings.max_total_runtime_s

    for index, step in enumerate(steps):
        if deadline and time.monotonic() > deadline:
            artifacts.append_record(
                _policy_violation_record(
                    "max_total_runtime_s",
                    "Maximum total runtime exceeded",
                    step_index=index,
                )
            )
            return StepOutcome(status="POLICY_VIOLATION", message="Runtime limit exceeded")
        if isinstance(step, GotoStep) and policy and not policy.is_allowed(step.url):
            artifacts.append_record(
                _policy_violation_record(
                    "domain_blocked",
                    f"Domain blocked by policy: {step.url}",
                    step_index=index,
                    step=step,
                )
            )
            return StepOutcome(
                status="POLICY_VIOLATION", message="Domain blocked by policy"
            )
        try:
            if isinstance(step, GotoStep):
                result = await _handle_goto(page, step)
            elif isinstance(step, WaitForStep):
                result = await _handle_wait_for(page, step)
            elif isinstance(step, ClickStep):
                result = await _handle_click(page, step)
            elif isinstance(step, TypeStep):
                result = await _handle_type(page, step)
            elif isinstance(step, PressStep):
                result = await _handle_press(page, step)
            elif isinstance(step, ScrollStep):
                result = await _handle_scroll(page, step)
            elif isinstance(step, ScreenshotStep):
                result = await _handle_screenshot(page, step, artifacts, index)
            elif isinstance(step, ExtractReadableStep):
                extract = await extract_readable(page, settings.max_extract_chars)
                html_path = await _maybe_capture_html(
                    page, artifacts, index, "readable", settings.capture_html_snapshot
                )
                artifacts.append_record(
                    _note_record(
                        "readable_extract",
                        page.url,
                        await page.title(),
                        extract,
                        {"html": html_path} if html_path else {},
                    )
                )
                result = {
                    "chars": extract.get("chars"),
                    "truncated": extract.get("truncated"),
                }
            elif isinstance(step, ExtractStep):
                extract = await extract_selector(
                    page, step.selector, settings.max_extract_chars
                )
                html_path = await _maybe_capture_html(
                    page, artifacts, index, "extract", settings.capture_html_snapshot
                )
                artifacts.append_record(
                    _note_record(
                        "extract",
                        page.url,
                        await page.title(),
                        extract,
                        {"html": html_path} if html_path else {},
                    )
                )
                result = {
                    "chars": extract.get("chars"),
                    "truncated": extract.get("truncated"),
                }
            elif isinstance(step, LinksStep):
                links = await extract_links(page, step.scope)
                html_path = await _maybe_capture_html(
                    page, artifacts, index, "links", settings.capture_html_snapshot
                )
                artifacts.append_record(
                    _note_record(
                        "links",
                        page.url,
                        await page.title(),
                        links,
                        {"html": html_path} if html_path else {},
                    )
                )
                result = {"count": links.get("count"), "scope": links.get("scope")}
            elif isinstance(step, QuoteStep):
                context_chars = step.context_chars
                if settings.max_extract_chars > 0:
                    context_chars = min(context_chars, settings.max_extract_chars)
                quote = await extract_quote(
                    page, step.query, context_chars, settings.max_extract_chars
                )
                html_path = await _maybe_capture_html(
                    page, artifacts, index, "quote", settings.capture_html_snapshot
                )
                artifacts.append_record(
                    _note_record(
                        "quote",
                        page.url,
                        await page.title(),
                        quote,
                        {"html": html_path} if html_path else {},
                    )
                )
                result = {"found": quote.get("found"), "query": step.query}
            elif isinstance(step, PauseForUserStep):
                path = artifacts.screenshot_path("manual_assist", index)
                await page.screenshot(path=str(path))
                result = {
                    "reason": step.reason,
                    "screenshot": str(path.relative_to(artifacts.run_dir)),
                }
                artifacts.append_record(
                    _step_record(index, step, "needs_manual_assist", result)
                )
                return StepOutcome(
                    status="NEEDS_MANUAL_ASSIST",
                    message=step.reason,
                    screenshot=result["screenshot"],
                )
            else:
                raise ValueError(f"Unsupported step type: {step.type}")

            artifacts.append_record(_step_record(index, step, "ok", result))
            if policy and not policy.is_allowed(page.url):
                artifacts.append_record(
                    _policy_violation_record(
                        "domain_blocked",
                        f"Domain blocked by policy: {page.url}",
                        step_index=index,
                        step=step,
                    )
                )
                return StepOutcome(
                    status="POLICY_VIOLATION", message="Domain blocked by policy"
                )
        except Exception as exc:
            artifacts.append_record(
                _step_record(
                    index,
                    step,
                    "error",
                    {"error": str(exc), "url": page.url if page else None},
                )
            )
            return StepOutcome(status="error", error=str(exc))

        delay_s = settings.min_delay_ms_between_actions / 1000.0
        if delay_s > 0 and index < len(steps) - 1:
            await asyncio.sleep(delay_s)
        else:
            await asyncio.sleep(0)

    return StepOutcome(status="ok")
