import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ARTY_VOICE_ID = os.getenv("ARTY_VOICE_ID", "")
WAKE_WORD = os.getenv("WAKE_WORD", "hey arty")
PUSH_TO_TALK = os.getenv("PUSH_TO_TALK", "false").lower() == "true"
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "./data/arty_memory.db")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")

CLAUDE_MODEL = "claude-sonnet-4-6"
WHISPER_MODEL = "base"

CONVERSATION_WINDOW = 20
UNCERTAINTY_THRESHOLD = 0.4
