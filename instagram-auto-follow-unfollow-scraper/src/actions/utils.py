import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from jsonschema import validate
from pydantic import BaseModel, Field

def now_utc_iso() -> str:
    import datetime as _dt
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

async def sleep_jitter(min_ms: int, max_ms: int):