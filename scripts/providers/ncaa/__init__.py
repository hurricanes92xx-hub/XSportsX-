"""NCAA provider wrapper that removes known-invalid ESPN secondary routes.

The public NCAA API covers these sports directly; broken ESPN 400 routes add latency
and noise without improving coverage. All other legacy NCAA behavior is preserved.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path

_LEGACY_PATH = Path(__file__).resolve().parents[1] / "ncaa.py"
_spec = importlib.util.spec_from_file_location("_xsportsx_ncaa_legacy", _LEGACY_PATH)
_legacy = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_legacy)

for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

# ESPN's public scoreboard returns HTTP 400 for these NCAA routes. The NCAA public
# feed supports both sports, so do not spend eight parallel calls on dead endpoints.
ESPN_FALLBACK = dict(getattr(_legacy, "ESPN_FALLBACK", {}))
ESPN_FALLBACK.pop("NCAA Softball", None)
ESPN_FALLBACK.pop("NCAA Beach Volleyball", None)
