from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from typing import Any


def collect_system_info() -> dict[str, Any]:
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
