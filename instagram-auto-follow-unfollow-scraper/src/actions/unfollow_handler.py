from typing import Any, Dict
from rich.console import Console

from browser.playwright_runner import PlaywrightRunner
from .utils import AppConfig, now_utc_iso

console = Console()

class UnfollowHandler:
    def __init__(self, runner: PlaywrightRunner, app_cfg: AppConfig):
        self.runner = runner
        self.cfg = app_cfg

    async def unfollow_user(self, username: str) -> Dict[str, Any]:
        username = username.strip()
        if not username.startswith("@"):
            username = f"@{username}"

        profile_url = f"https://www.instagram.com/{username[1:]}/"

        if self.cfg.simulate:
            followers = self.runner.rng.randint(500, 100000)
            following = self.runner.rng.randint(50, 5000)
            is_following = False
            is_followed_by = bool(self.runner.rng.randint(0, 1))
        else:
            await self.runner.ensure_logged_in()
            followers, following = await self.runner.get_profile_counts(username)
            is_following, is_followed_by = await self.runner.get_relationship_state(username)
            if is_following:
                await self.runner.click_unfollow(username)
                is_following = False

        result = {
            "username": username[1:],
            "profileUrl": profile_url,
            "followersCount": followers,
            "followingCount": following,
            "isFollowing": is_following,
            "isFollowedBy": is_followed_by,
            "recentActivity": now_utc_iso(),
            "timestamp": now_utc_iso(),
            "action": "unfollowed",
        }
        console.log(f"[magenta]Unfollowed[/magenta] {username}")
        return result