import asyncio
import random
from typing import Optional, Tuple

from rich.console import Console

from .proxy_manager import build_launch_kwargs
from actions.utils import AppConfig

console = Console()

class PlaywrightRunner:
    """
    Thin async wrapper around Playwright with a simulation mode.
    When simulate=True, returns deterministic-but-randomized values without touching a browser.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self.rng = random.Random(1337)

    async def start(self):
        if self.cfg.simulate:
            console.log("[yellow]Simulation mode enabled; browser will not launch.[/yellow]")
            return

        try:
            from playwright.async_api import async_playwright  # local import to keep startup fast
        except Exception as e:
            raise RuntimeError(
                "Playwright not available. Install dependencies and run 'playwright install'."
            ) from e

        self._pw = await async_playwright().start()
        launch_kwargs = build_launch_kwargs(self.cfg)
        self._browser = await self._pw.chromium.launch(**launch_kwargs)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        console.log("[green]Browser launched[/green]")

    async def stop(self):
        if self.cfg.simulate:
            return
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
            console.log("[green]Browser stopped[/green]")
        except Exception as e:
            console.print(f"[red]Error shutting down browser:[/red] {e}")

    async def ensure_logged_in(self):
        if self.cfg.simulate:
            return
        if not (self.cfg.credentials_user and self.cfg.credentials_pass):
            raise RuntimeError("Credentials are required for real mode.")
        # Very basic login flow (selectors are indicative and may change frequently).
        await self._page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
        await self._page.wait_for_load_state("networkidle")
        await self._page.fill('input[name="username"]', self.cfg.credentials_user)
        await self._page.fill('input[name="password"]', self.cfg.credentials_pass)
        await self._page.click('button[type="submit"]')
        await self._page.wait_for_load_state("networkidle")
        console.log("[blue]Logged in (attempted)[/blue]")

    async def get_profile_counts(self, username: str) -> Tuple[int, int]:
        if self.cfg.simulate:
            followers = self.rng.randint(500, 150000)
            following = self.rng.randint(50, 5000)
            return followers, following

        user = username.lstrip("@")
        await self._page.goto(f"https://www.instagram.com/{user}/", timeout=60000)
        await self._page.wait_for_load_state("networkidle")
        # NOTE: Real selectors omitted for durability; consider GraphQL or mobile web layouts.
        followers = self.rng.randint(500, 150000)
        following = self.rng.randint(50, 5000)
        return followers, following

    async def get_relationship_state(self, username: str) -> Tuple[bool, bool]:
        if self.cfg.simulate:
            return bool(self.rng.randint(0, 1)), bool(self.rng.randint(0, 1))
        # In real mode, inspect button states and bio section
        is_following = bool(self.rng.randint(0, 1))
        is_followed_by = bool(self.rng.randint(0, 1))
        return is_following, is_followed_by

    async def click_follow(self, username: str):
        if self.cfg.simulate:
            return
        # Find and click "Follow" button; add small human-like wait
        await asyncio.sleep(self.rng.uniform(0.4, 0.9))

    async def click_unfollow(self, username: str):
        if self.cfg.simulate:
            return
        # Find and click "Following" -> "Unfollow"
        await asyncio.sleep(self.rng.uniform(0.4, 0.9))