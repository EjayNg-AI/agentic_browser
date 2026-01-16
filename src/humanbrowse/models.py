from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


class StepBase(BaseModel):
    type: str


class GotoStep(StepBase):
    type: Literal["goto"] = "goto"
    url: str
    wait_until: Optional[str] = None


class WaitForStep(StepBase):
    type: Literal["wait_for"] = "wait_for"
    selector: Optional[str] = None
    text: Optional[str] = None
    load_state: Optional[str] = None

    @model_validator(mode="after")
    def validate_target(self) -> "WaitForStep":
        targets = [self.selector, self.text, self.load_state]
        if sum(1 for t in targets if t) != 1:
            raise ValueError("wait_for requires exactly one of selector, text, load_state")
        return self


class ExtractStep(StepBase):
    type: Literal["extract"] = "extract"
    selector: Optional[str] = None


class ExtractReadableStep(StepBase):
    type: Literal["extract_readable"] = "extract_readable"


class ClickStep(StepBase):
    type: Literal["click"] = "click"
    selector: Optional[str] = None
    text: Optional[str] = None
    role: Optional[str] = None

    @model_validator(mode="after")
    def validate_target(self) -> "ClickStep":
        targets = [self.selector, self.text, self.role]
        if sum(1 for t in targets if t) != 1:
            raise ValueError("click requires exactly one of selector, text, role")
        return self


class TypeStep(StepBase):
    type: Literal["type"] = "type"
    selector: str
    text: str


class PressStep(StepBase):
    type: Literal["press"] = "press"
    key: str


class ScrollStep(StepBase):
    type: Literal["scroll"] = "scroll"
    pixels: Optional[int] = None
    to_selector: Optional[str] = None

    @model_validator(mode="after")
    def validate_target(self) -> "ScrollStep":
        targets = [self.pixels, self.to_selector]
        if sum(1 for t in targets if t is not None) != 1:
            raise ValueError("scroll requires exactly one of pixels, to_selector")
        return self


class LinksStep(StepBase):
    type: Literal["links"] = "links"
    scope: str = "main"


class QuoteStep(StepBase):
    type: Literal["quote"] = "quote"
    query: str
    context_chars: int = 400

    @model_validator(mode="after")
    def validate_context(self) -> "QuoteStep":
        if self.context_chars < 0:
            raise ValueError("context_chars must be non-negative")
        return self


class PauseForUserStep(StepBase):
    type: Literal["pause_for_user"] = "pause_for_user"
    reason: str


class ScreenshotStep(StepBase):
    type: Literal["screenshot"] = "screenshot"
    label: Optional[str] = None


Step = Annotated[
    Union[
        GotoStep,
        WaitForStep,
        ScreenshotStep,
        ExtractStep,
        ExtractReadableStep,
        ClickStep,
        TypeStep,
        PressStep,
        ScrollStep,
        LinksStep,
        QuoteStep,
        PauseForUserStep,
    ],
    Field(discriminator="type"),
]


class RunStepsRequest(BaseModel):
    session_id: Optional[str] = None
    new_session: bool = False
    steps: List[Step]


class RunStepsResponse(BaseModel):
    status: str
    run_id: str
    session_id: str
    run_url: str
    message: Optional[str] = None
    screenshot: Optional[str] = None


class ResumeRequest(BaseModel):
    session_id: str


class CloseSessionRequest(BaseModel):
    session_id: str
