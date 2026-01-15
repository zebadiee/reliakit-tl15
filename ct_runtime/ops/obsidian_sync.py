#!/usr/bin/env python3
# CT_VENV: core
# Repo-tracked copy of `/srv/ct/obsidian_sync.py` for audits

from pathlib import Path
from datetime import datetime
import yaml
import shutil

BASE = Path("/srv/ct")
RESULTS = BASE / "results"
OBS_RESULTS = BASE / "obsidian" / "Results"
OBS_RECOVERY = BASE / "obsidian" / "Recovery"
SYNCED = RESULTS / "_synced"
LESSONS = BASE / "lessons.yaml"

# Function implementations are intentionally minimal here; runtime logic lives in /srv/ct/obsidian_sync.py
# The runtime extracts lessons and writes them to `/srv/ct/lessons.yaml` as a list of dicts with keys:
# - id, source, rule, enforced_by, confidence, first_seen
