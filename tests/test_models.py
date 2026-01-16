import pytest
from pydantic import ValidationError

from humanbrowse.models import (
    ClickStep,
    QuoteStep,
    RunStepsRequest,
    ScrollStep,
    WaitForStep,
)


def test_wait_for_requires_one_target() -> None:
    WaitForStep(type="wait_for", selector="#main")
    with pytest.raises(ValidationError):
        WaitForStep(type="wait_for")
    with pytest.raises(ValidationError):
        WaitForStep(type="wait_for", selector="#a", text="b")


def test_click_requires_one_target() -> None:
    ClickStep(type="click", selector="#submit")
    with pytest.raises(ValidationError):
        ClickStep(type="click")
    with pytest.raises(ValidationError):
        ClickStep(type="click", text="Ok", role="button")


def test_scroll_requires_one_target() -> None:
    ScrollStep(type="scroll", pixels=120)
    with pytest.raises(ValidationError):
        ScrollStep(type="scroll")
    with pytest.raises(ValidationError):
        ScrollStep(type="scroll", pixels=120, to_selector="#footer")


def test_quote_requires_non_negative_context() -> None:
    QuoteStep(type="quote", query="hello", context_chars=10)
    with pytest.raises(ValidationError):
        QuoteStep(type="quote", query="hello", context_chars=-1)


def test_run_steps_request_union_parses() -> None:
    payload = {
        "steps": [
            {"type": "wait_for", "selector": "#main"},
            {"type": "click", "text": "Submit"},
        ]
    }
    req = RunStepsRequest(**payload)
    assert len(req.steps) == 2
