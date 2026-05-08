import anthropic
import random
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CONVERSATION_WINDOW
from brain.personality import ARTY_SYSTEM_PROMPT, ARTY_UNCERTAINTY_PHRASES, ARTY_LEARNING_PHRASES
from brain.memory import ArtyMemory


class ArtyBrain:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.memory = ArtyMemory()
        self.session_id = None

    def set_session(self, session_id: str):
        self.session_id = session_id

    def think(self, user_input: str) -> tuple[str, bool]:
        """
        Process user input and return (response_text, needs_help).
        needs_help=True triggers the uncertainty/escalation flow.
        """
        self.memory.save_message("user", user_input, self.session_id)

        knowledge_context = self.memory.build_context_for_query(user_input)
        recent_messages = self.memory.get_recent_messages(CONVERSATION_WINDOW)

        system = ARTY_SYSTEM_PROMPT
        if knowledge_context:
            system += f"\n\n{knowledge_context}"

        messages = recent_messages if recent_messages else []
        if not messages or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": user_input})

        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system,
            messages=messages
        )

        reply = response.content[0].text
        needs_help = self._detect_uncertainty(reply)

        if needs_help:
            reply = random.choice(ARTY_UNCERTAINTY_PHRASES)

        self.memory.save_message("assistant", reply, self.session_id)
        return reply, needs_help

    def learn(self, topic: str, content: str, source: str = None):
        """Store a training note into long-term memory."""
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
