import json
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console

console = Console()

class DatasetManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.results_path = self.base_dir / "results.jsonl"

    def ensure_dirs(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.results_path.exists():
            self.results_path.write_text("", encoding="utf-8")

    def write_result(self, item: Dict[str, Any]):
        line = json.dumps(item, ensure_ascii=False)
        with self.results_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def export_summary(self, items: List[Dict[str, Any]], export_path: Path):
        summary = {
            "total": len(items),
            "followed": sum(1 for i in items if i.get("action") == "followed"),
            "unfollowed": sum(1 for i in items if i.get("action") == "unfollowed"),
            "path_results_jsonl": str(self.results_path),
            "path_export_json": str(export_path),
        }
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
        console.log(f"[green]Wrote {len(items)} items[/green]")
        return summary