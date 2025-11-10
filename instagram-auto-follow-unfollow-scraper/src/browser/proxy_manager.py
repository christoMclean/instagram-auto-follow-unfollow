from typing import Dict, Any
from actions.utils import AppConfig

def build_launch_kwargs(cfg: AppConfig) -> Dict[str, Any]:
    launch_kwargs: Dict[str, Any] = {
        "headless": cfg.headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    }
    if cfg.proxy:
        launch_kwargs["proxy"] = {"server": cfg.proxy}
    return launch_kwargs