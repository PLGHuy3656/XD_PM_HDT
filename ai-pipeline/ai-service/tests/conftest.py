"""Pytest configuration for services/ai-service."""
from __future__ import annotations

import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent
AI_PIPELINE_SRC = SERVICE_ROOT.parent / "src"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

if str(AI_PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_SRC))
