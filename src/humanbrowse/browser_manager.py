import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .cdp_endpoints import select_cdp_endpoint
from .config import Settings
from .log import get_logger

logger = get_logger(__name__)


class BrowserManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> Browser:
        async with self._lock:
            if self._browser:
                return self._browser

            endpoint, version = select_cdp_endpoint(
                self.settings.cdp_port,
                allow_nat=self.settings.cdp_allow_nat,
                timeout_s=self.settings.cdp_timeout_ms / 1000.0,
            )
            logger.info("CDP endpoint selected: %s", endpoint)
            if version:
                logger.info("CDP version: %s", version.get("Browser"))

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(
                endpoint_url=endpoint,
                timeout=self.settings.cdp_timeout_ms,
                slow_mo=self.settings.slow_mo_ms,
            )
            return self._browser

    async def close(self) -> None:
        async with self._lock:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None


@dataclass
class Session:
    session_id: str
    context: BrowserContext
    page: Page
    created_at: str
    last_active: str
    status: str = "active"
    last_run_id: Optional[str] = None
    last_manual_assist: Optional[dict] = None


class SessionManager:
    def __init__(self, browser_manager: BrowserManager) -> None:
        self.browser_manager = browser_manager
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_session(
        self, session_id: Optional[str], new_session: bool
    ) -> Session:
        async with self._lock:
            if (
                session_id
                and session_id in self._sessions
                and not new_session
            ):
                session = self._sessions[session_id]
                if session.status != "closed":
                    session.last_active = _utc_now()
                    return session

            browser = await self.browser_manager.connect()
            context = await browser.new_context()
            page = await context.new_page()
            sid = uuid4().hex
            session = Session(
                session_id=sid,
                context=context,
                page=page,
                created_at=_utc_now(),
                last_active=_utc_now(),
            )
            self._sessions[sid] = session
            return session

    async def close_session(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            await session.context.close()
            session.status = "closed"
            return True

    def resume_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.status = "active"
        session.last_active = _utc_now()
        return True

    def get_status(self, session_id: str) -> Optional[dict]:
        session = self._sessions.get(session_id)
        if not session:
            return None
        return {
            "session_id": session.session_id,
            "status": session.status,
            "created_at": session.created_at,
            "last_active": session.last_active,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
