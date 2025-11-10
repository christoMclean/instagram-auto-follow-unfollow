import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.traceback import install as rich_traceback

# Ensure imports resolve when running "python src/main.py"
CURRENT_DIR = Path(__file__).parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from actions.follow_handler import FollowHandler
from actions.unfollow_handler import UnfollowHandler
from actions.utils import (
    AppConfig,
    InputConfig,
    load_app_config,
    load_input_config,
    now_utc_iso,
    sleep_jitter,
    validate_config_against_schema,
)
from browser.playwright_runner import PlaywrightRunner
from storage.dataset_manager import DatasetManager
from storage.request_queue import RequestQueue

rich_traceback(show_locals=False)
console = Console()
shutdown_flag = False

def _handle_sigint(signum, frame):
    global shutdown_flag
    shutdown_flag = True
    console.print("[yellow]Graceful shutdown requested... finishing current item.[/yellow]")

signal.signal(signal.SIGINT, _handle_sigint)

async def run(app_cfg: AppConfig, input_cfg: InputConfig, export_path: Path) -> Dict[str, Any]:
    """
    Orchestrates the end-to-end job:
     - setup runner (real or simulate)
     - build request queue
     - process follow/unfollow according to mode and limits
     - write dataset artifacts
    """
    dataset = DatasetManager(base_dir=Path(__file__).resolve().parents[1] / "data")
    dataset.ensure_dirs()

    runner = PlaywrightRunner(app_cfg)
    await runner.start()

    # Build targets queue
    targets: List[str] = []
    if input_cfg.targets.usernames:
        targets.extend([f"@{u.lstrip('@')}" for u in input_cfg.targets.usernames])

    # Hashtag and location discovery can be expanded here; we simulate discovery to usernames
    for tag in input_cfg.targets.hashtags:
        # Simulated discovery: derive pseudo usernames from hashtags
        for i in range(1, 1 + app_cfg.discovery_per_hashtag):
            targets.append(f"@{tag}_user{i}")

    for loc in input_cfg.targets.locations:
        for i in range(1, 1 + app_cfg.discovery_per_location):
            targets.append(f"@{loc}_user{i}")

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for t in targets:
        if t not in seen:
            deduped.append(t)
            seen.add(t)

    queue = RequestQueue(seed_items=deduped)

    follow_handler = FollowHandler(runner, app_cfg)
    unfollow_handler = UnfollowHandler(runner, app_cfg)

    processed_count = 0
    results: List[Dict[str, Any]] = []
    max_actions = input_cfg.limits.max_actions

    console.rule("[bold cyan]Instagram Auto Follow/Unfollow")
    console.print(f"[bold]Mode:[/bold] {input_cfg.mode} | [bold]Headless:[/bold] {app_cfg.headless} | [bold]Simulate:[/bold] {app_cfg.simulate}")
    console.print(f"[bold]Targets queued:[/bold] {queue.size} | [bold]Max actions:[/bold] {max_actions}\n")

    try:
        if input_cfg.mode in ("follow", "both"):
            while processed_count < max_actions and not queue.is_empty():
                if shutdown_flag:
                    break
                username = queue.pop()
                try:
                    res = await follow_handler.follow_user(username)
                    results.append(res)
                    processed_count += 1
                    dataset.write_result(res)
                except Exception as e:
                    console.print(f"[red]Follow error for {username}:[/red] {e}")
                await sleep_jitter(app_cfg.delay.min_ms, app_cfg.delay.max_ms)

        if input_cfg.mode in ("unfollow", "both") and not shutdown_flag:
            # Unfollow candidates are either provided or derived from previous follows
            candidates = input_cfg.unfollow.usernames or [r["username"] for r in results if r.get("action") == "followed"]
            unfollow_queue = RequestQueue(seed_items=candidates)
            while processed_count < max_actions and not unfollow_queue.is_empty():
                if shutdown_flag:
                    break
                username = unfollow_queue.pop()
                try:
                    res = await unfollow_handler.unfollow_user(username)
                    results.append(res)
                    processed_count += 1
                    dataset.write_result(res)
                except Exception as e:
                    console.print(f"[red]Unfollow error for {username}:[/red] {e}")
                await sleep_jitter(app_cfg.delay.min_ms, app_cfg.delay.max_ms)

    finally:
        await runner.stop()

    # Export summary
    summary = dataset.export_summary(results, export_path)

    # Pretty print final table
    table = Table(title="Session Summary", show_lines=False)
    table.add_column("Username", justify="left")
    table.add_column("Action", justify="left")
    table.add_column("FollowedBy", justify="right")
    table.add_column("Following", justify="right")
    table.add_column("Followers", justify="right")
    table.add_column("When", justify="left")
    for r in results:
        table.add_row(
            r.get("username", ""),
            r.get("action", ""),
            str(r.get("isFollowedBy", "")),
            str(r.get("followingCount", "")),
            str(r.get("followersCount", "")),
            r.get("timestamp", ""),
        )
    console.print()
    console.print(table)
    console.print(f"\n[green]Exported summary ->[/green] {export_path}")

    return summary

def main():
    parser = argparse.ArgumentParser(description="Instagram Auto Follow/Unfollow Scraper")
    parser.add_argument("--settings", default=str(CURRENT_DIR / "config" / "settings.json"), help="Path to settings.json")
    parser.add_argument("--input", default=str(Path(__file__).resolve().parents[1] / "data" / "input.sample.json"), help="Path to input JSON")
    parser.add_argument("--export", default=str(Path(__file__).resolve().parents[1] / "data" / "output.sample.json"), help="Path to write summary JSON")
    args = parser.parse_args()

    settings_path = Path(args.settings)
    input_path = Path(args.input)
    export_path = Path(args.export)

    if not settings_path.exists():
        console.print(f"[red]Missing settings file:[/red] {settings_path}")
        sys.exit(1)

    if not input_path.exists():
        console.print(f"[yellow]Input file not found, creating a sample at {input_path}[/yellow]")
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text(json.dumps({
            "mode": "follow",
            "targets": {"usernames": ["fashion.trends24", "street.style.hub"], "hashtags": ["streetstyle"], "locations": ["nyc"]},
            "limits": {"max_actions": 5},
            "unfollow": {"usernames": []}
        }, indent=2))

    # Validate settings and input against schema
    schema_path = CURRENT_DIR / "config" / "input_schema.json"
    try:
        validate_config_against_schema(input_path, schema_path)
    except Exception as e:
        console.print(f"[red]Input schema validation failed:[/red] {e}")
        sys.exit(1)

    app_cfg = load_app_config(settings_path)
    input_cfg = load_input_config(input_path)

    # Add run metadata
    console.print(f"[blue]Run started:[/blue] {now_utc_iso()}")
    try:
        asyncio.run(run(app_cfg, input_cfg, export_path))
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted[/yellow]")
    console.print(f"[blue]Run finished:[/blue] {now_utc_iso()}")

if __name__ == "__main__":
    main()