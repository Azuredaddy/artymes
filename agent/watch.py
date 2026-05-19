"""
watch.py — ARTY silent observation mode.
Watches your screen all day, logs to data/observe_*.txt. No voice, no interruptions.
Run: python watch.py
Stop: Ctrl+C
"""

import sys
import os
from datetime import datetime

# Minimal startup — no banner, no voice
print(f"  ARTY watching... started {datetime.now().strftime('%H:%M:%S')}")
print(f"  Press Ctrl+C to stop.\n")

from config import ANTHROPIC_API_KEY
if not ANTHROPIC_API_KEY or not ANTHROPIC_API_KEY.startswith("sk-"):
    print("  ERROR: ANTHROPIC_API_KEY missing in .env")
    sys.exit(1)

from eyes.screen import ArtyEyes
from brain.trainer import ObserveSession


class _SilentVoice:
    def speak(self, text): pass


class _SilentHands:
    def type_into_window(self, *a, **kw): pass
    def open_app(self, *a, **kw): pass


eyes = ArtyEyes()
session = ObserveSession(
    duration_minutes=600,   # 10 hours — effectively all day
    eyes=eyes,
    hands=_SilentHands(),
    voice=_SilentVoice(),
    memory=None,
)
session.open_notepad()
print(f"  Log file: {session.log_path}\n")

try:
    session.run()
except KeyboardInterrupt:
    session.stop()
    count = len(session.observations)
    print(f"\n  Stopped. {count} observations saved to:\n  {session.log_path}")
