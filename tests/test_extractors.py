import asyncio
from pathlib import Path

from humanbrowse.artifacts import init_run, read_run_records
from humanbrowse.config import Settings
from humanbrowse.models import ExtractReadableStep
from humanbrowse.steps import execute_steps


class FakeLocator:
    def __init__(self, count: int = 0, text: str = "") -> None:
        self._count = count
        self._text = text
        self.first = self

    async def count(self) -> int:
        return self._count

    async def inner_text(self) -> str:
        return self._text


class FakePage:
    def __init__(self, html: str) -> None:
        self._html = html
        self.url = "https://example.com"

    def locator(self, _selector: str) -> FakeLocator:
        return FakeLocator(count=0)

    async def content(self) -> str:
        return self._html

    async def title(self) -> str:
        return "Sample Article"


def test_extract_readable_trims_and_writes_note(tmp_path: Path) -> None:
    html = (Path(__file__).parent / "fixtures" / "sample.html").read_text(
        encoding="utf-8"
    )
    settings = Settings(
        max_extract_chars=80,
        capture_html_snapshot=False,
        min_delay_ms_between_actions=0,
    )
    artifacts = init_run(tmp_path, "session-test")
    page = FakePage(html)
    step = ExtractReadableStep(type="extract_readable")

    outcome = asyncio.run(execute_steps(page, [step], artifacts, settings))
    assert outcome.status == "ok"

    records = read_run_records(artifacts.run_dir)
    notes = [record for record in records if record.get("type") == "note"]
    assert notes, "Expected at least one note record"
    note = notes[0]
    assert note.get("note_kind") == "readable_extract"
    content = note.get("content", {})
    assert content.get("truncated") is True
    assert len(content.get("text", "")) <= settings.max_extract_chars
    assert set(note.keys()) >= {
        "type",
        "note_kind",
        "url",
        "timestamp",
        "content",
        "evidence",
    }
