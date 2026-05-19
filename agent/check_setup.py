"""
ARTY Setup Checker — run this if ARTY won't start.
Checks every dependency and API key without launching the full app.
"""
import os
import sys

PASS = "[OK]"
FAIL = "[!!]"
WARN = "[??]"

print("\n========================================")
print("  ARTY Setup Checker")
print("========================================\n")

# ── .env file ─────────────────────────────────────────────────────────────
from config import ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, ARTY_VOICE_ID, ENV_PATH, VERSION, CLAUDE_MODEL

print(f"  ARTY version  : v{VERSION}")
print(f"  Claude model  : {CLAUDE_MODEL}")
print(f"  Config file   : {ENV_PATH}")
print(f"  .env exists   : {'Yes' if os.path.exists(ENV_PATH) else 'NO — create it!'}")
print()

errors = 0

# ── Anthropic key ──────────────────────────────────────────────────────────
masked_anth = (ANTHROPIC_API_KEY[:12] + "..." + ANTHROPIC_API_KEY[-4:]) if len(ANTHROPIC_API_KEY) > 16 else "(empty)"
if not ANTHROPIC_API_KEY or not ANTHROPIC_API_KEY.startswith("sk-"):
    print(f"  {FAIL} ANTHROPIC_API_KEY : missing or wrong format — got: {masked_anth}")
    errors += 1
else:
    print(f"  Checking Anthropic key ({masked_anth}) ...")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        client.messages.create(model=CLAUDE_MODEL, max_tokens=5, messages=[{"role": "user", "content": "hi"}])
        print(f"  {PASS} ANTHROPIC_API_KEY : valid and working")
    except anthropic.AuthenticationError:
        print(f"  {FAIL} ANTHROPIC_API_KEY : REJECTED by Anthropic — key is invalid or revoked")
        errors += 1
    except Exception as e:
        print(f"  {WARN} ANTHROPIC_API_KEY : could not verify ({e})")

# ── ElevenLabs key ────────────────────────────────────────────────────────
masked_el = (ELEVENLABS_API_KEY[:8] + "..." + ELEVENLABS_API_KEY[-4:]) if len(ELEVENLABS_API_KEY) > 12 else "(empty)"
if not ELEVENLABS_API_KEY:
    print(f"  {WARN} ELEVENLABS_API_KEY: missing — voice output will be disabled")
else:
    print(f"  {PASS} ELEVENLABS_API_KEY: present ({masked_el})")

if not ARTY_VOICE_ID:
    print(f"  {WARN} ARTY_VOICE_ID     : not set — set this to your ElevenLabs voice ID")
else:
    print(f"  {PASS} ARTY_VOICE_ID     : {ARTY_VOICE_ID}")

# ── Python packages ───────────────────────────────────────────────────────
print()
packages = ["anthropic", "elevenlabs", "whisper", "chromadb", "rich", "colorama", "dotenv"]
for pkg in packages:
    try:
        __import__(pkg if pkg != "dotenv" else "dotenv")
        print(f"  {PASS} {pkg}")
    except ImportError:
        print(f"  {FAIL} {pkg} — run: pip install -r requirements.txt")
        errors += 1

# ── Summary ───────────────────────────────────────────────────────────────
print()
if errors == 0:
    print("  All checks passed. ARTY should start fine.\n")
else:
    print(f"  {errors} issue(s) found. Fix the above before running ARTY.\n")

print("========================================\n")
