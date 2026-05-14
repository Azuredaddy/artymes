import re
import anthropic
import random
from datetime import datetime
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CONVERSATION_WINDOW
from brain.personality import ARTY_SYSTEM_PROMPT, ARTY_UNCERTAINTY_PHRASES, ARTY_LEARNING_PHRASES
from brain.memory import ArtyMemory

_context_cache = None
_context_built_at = None
_CONTEXT_TTL_SECONDS = 300


def _build_context_cached() -> str:
    global _context_cache, _context_built_at
    now = datetime.now()
    if _context_cache is None or (now - _context_built_at).total_seconds() > _CONTEXT_TTL_SECONDS:
        try:
            from brain.context import build_live_context
            _context_cache = build_live_context()
        except Exception:
            _context_cache = (
                f"## Live Awareness\n"
                f"Current date: {now.strftime('%A, %d %B %Y')}\n"
                f"Current time: {now.strftime('%H:%M')}"
            )
        _context_built_at = now
    return _context_cache


def _split_sentence(buffer: str):
    """Return (sentence_to_speak, remaining_buffer) or (None, buffer) if no complete sentence yet."""
    match = re.search(r'[.!?]["\']?\s+', buffer)
    if match and len(buffer[:match.end()].split()) >= 4:
        return buffer[:match.end()].strip(), buffer[match.end():]
    return None, buffer


class ArtyBrain:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.memory = ArtyMemory()
        self.session_id = None
        ctx = _build_context_cached()
        print(f"\n[Context loaded]\n{ctx}\n")

    def set_session(self, session_id: str):
        self.session_id = session_id

    def _build_messages(self, user_input: str) -> tuple[str, list]:
        knowledge_context = self.memory.build_context_for_query(user_input)
        recent_messages = self.memory.get_recent_messages(CONVERSATION_WINDOW)

        system = ARTY_SYSTEM_PROMPT + f"\n\n{_build_context_cached()}"
        if knowledge_context:
            system += f"\n\n{knowledge_context}"

        messages = recent_messages[:]
        if not messages or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": user_input})

        return system, messages

    def think_streaming(self, user_input: str, voice) -> tuple[str, bool]:
        """Stream Claude's reply, speaking each sentence as it arrives."""
        self.memory.save_message("user", user_input, self.session_id)
        system, messages = self._build_messages(user_input)

        full_reply = ""
        buffer = ""

        with self.client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_reply += text
                buffer += text
                sentence, buffer = _split_sentence(buffer)
                if sentence:
                    voice.speak(sentence)

        if buffer.strip():
            voice.speak(buffer.strip())

        needs_help = self._detect_uncertainty(full_reply)
        self.memory.save_message("assistant", full_reply, self.session_id)
        return full_reply, needs_help

    def think(self, user_input: str) -> tuple[str, bool]:
        """Non-streaming fallback — returns full reply without speaking."""
        self.memory.save_message("user", user_input, self.session_id)
        system, messages = self._build_messages(user_input)

        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system,
            messages=messages,
        )

        reply = response.content[0].text
        needs_help = self._detect_uncertainty(reply)

        if needs_help:
            reply = random.choice(ARTY_UNCERTAINTY_PHRASES)

        self.memory.save_message("assistant", reply, self.session_id)
        return reply, needs_help

    def learn(self, topic: str, content: str, source: str = None):
        self.memory.save_training_note(topic, content, source)
        return random.choice(ARTY_LEARNING_PHRASES)

    def log_task(self, title: str, description: str = None, confidence: float = 1.0) -> int:
        return self.memory.save_task(title, description, confidence)

    def get_tasks(self) -> list[dict]:
        return self.memory.get_open_tasks()

    def _detect_uncertainty(self, reply: str) -> bool:
        uncertainty_signals = [
            "i'm not sure", "i don't know", "i'm uncertain",
            "not confident", "unsure", "i'd need to check",
            "i don't have enough", "outside my training",
            "i'm not trained on", "you'd know better"
        ]
        lower = reply.lower()
        return any(signal in lower for signal in uncertainty_signals)
