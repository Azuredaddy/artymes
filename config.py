import os
from dotenv import load_dotenv

# Always load .env from the same folder as this file, regardless of working directory
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=_env_path)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip().strip('"').strip("'")
ARTY_VOICE_ID = os.getenv("ARTY_VOICE_ID", "").strip().strip('"').strip("'")
WAKE_WORD = os.getenv("WAKE_WORD", "hey arty")
PUSH_TO_TALK = os.getenv("PUSH_TO_TALK", "false").lower() == "true"
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "./data/arty_memory.db")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")

CLAUDE_MODEL = "claude-sonnet-4-6"
WHISPER_MODEL = "base"

CONVERSATION_WINDOW = 20
UNCERTAINTY_THRESHOLD = 0.4
