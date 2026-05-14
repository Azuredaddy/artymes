import os
from dotenv import load_dotenv

ARTY_VERSION = "1.5.0"
VERSION = ARTY_VERSION  # alias used by check_setup.py

# Always load .env from the same folder as this file, regardless of working directory
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
ENV_PATH = _env_path  # exported so check_setup.py can show the path
load_dotenv(dotenv_path=_env_path, encoding="utf-8-sig")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip().strip('"').strip("'")
ARTY_VOICE_ID = os.getenv("ARTY_VOICE_ID", "").strip().strip('"').strip("'")
WAKE_WORD = os.getenv("WAKE_WORD", "hey arty")
PUSH_TO_TALK = os.getenv("PUSH_TO_TALK", "false").lower() == "true"
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "./data/arty_memory.db")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")

CLAUDE_MODEL = "claude-opus-4-7"
# Computer Use requires a model that supports the computer-use-2025-01-24 beta
COMPUTER_USE_MODEL = "claude-sonnet-4-5-20251001"
WHISPER_MODEL = "base"

CONVERSATION_WINDOW = 20
UNCERTAINTY_THRESHOLD = 0.4

GITHUB_VERSION_URL = "https://raw.githubusercontent.com/Azuredaddy/artymes/main/version.txt"
