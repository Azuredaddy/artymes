"""
brief.py — ARTY briefing mode.

Talk to ARTY naturally while you work. It listens, gives short acknowledgements,
stores everything in memory, and occasionally asks one smart question.
No computer actions. No long replies. Won't interrupt your calls.

Run:  python brief.py
Stop: Ctrl+C or say "bye arty" / "that's it arty"
"""

import sys
import random
import anthropic
from datetime import datetime
from brain.memory import ArtyMemory
from voice.stt import ArtyEars
from voice.tts import ArtyVoice
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

BRIEF_SYSTEM = """You are ARTY, an AI employee being briefed by your colleague while they work.

Your job right now is to LISTEN and LEARN — not to help, not to take actions, just to absorb information.

Rules:
- Reply in 3 words or fewer for most things: "Got it.", "Noted.", "On file.", "Understood.", "Cheers."
- Only ask ONE short question if something genuinely needs clarifying — and only every 5-6 messages, not every time
- Never offer suggestions, advice, or long explanations
- Never say what you're going to remember — just acknowledge
- If the colleague says something that sounds like a question directed at you, answer briefly (1-2 sentences max)
- You are building up knowledge of: clients, systems, processes, common issues, how things work here

Examples of good replies:
  User: "Just reset Niraj's password, he's on Office 365"  →  "Noted."
  User: "We use Connectwise for ticketing"  →  "Got it."
  User: "That client always rings about Outlook"  →  "Logged."
  User: "What system does Niraj use?"  →  "Office 365, based on what you told me."

You may ask one question like: "Is that the same Niraj from earlier?" or "Which site is that client on?"
But ONLY if it's genuinely useful and you haven't asked recently."""

ACK = [
    "Got it.", "Noted.", "On file.", "Understood.", "Logged.",
    "Cheers.", "Right.", "Stored.", "Good to know.", "Yep, noted.",
]

STOP_WORDS = {"bye arty", "that's it arty", "stop arty", "bye", "done arty", "finish arty"}


def is_stop(text: str) -> bool:
    return any(s in text.lower() for s in STOP_WORDS)


def brief():
    print("\n  ARTY briefing mode — talk naturally, I'll listen and learn.")
    print("  Say 'bye Arty' to stop.\n")

    memory = ArtyMemory()
    ears = ArtyEars()
    voice = ArtyVoice()
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    history = []
    msg_count = 0
    session_id = f"brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    voice.speak("Ready.")

    while True:
        try:
            print("  [Listening...]")
            text = ears.listen()
            if not text:
                continue

            print(f"  You: {text}")

            if is_stop(text):
                voice.speak("Got it. Bye.")
                break

            msg_count += 1

            # Save what the user said to memory
            memory.save_message("user", text, session_id)
            memory.add_to_knowledge(
                text,
                metadata={"type": "briefing", "timestamp": datetime.now().isoformat()}
            )

            # Build a short conversation history for context (last 6 messages)
            history.append({"role": "user", "content": text})
            if len(history) > 6:
                history = history[-6:]

            # Decide whether to just ack or to actually respond with Claude
            # Use Claude every ~4 messages or when the user seems to be asking something
            question_words = {"what", "who", "where", "when", "how", "which", "do you", "can you", "did you"}
            is_question = any(text.lower().startswith(w) for w in question_words) or text.strip().endswith("?")

            if is_question or msg_count % 4 == 0:
                try:
                    resp = client.messages.create(
                        model=CLAUDE_MODEL,
                        max_tokens=80,
                        system=BRIEF_SYSTEM,
                        messages=history,
                    )
                    reply = resp.content[0].text.strip()
                except Exception:
                    reply = random.choice(ACK)
            else:
                reply = random.choice(ACK)

            print(f"  ARTY: {reply}")
            voice.speak(reply)

            history.append({"role": "assistant", "content": reply})
            memory.save_message("assistant", reply, session_id)

        except KeyboardInterrupt:
            voice.speak("Stopping. See you.")
            break

    print(f"\n  Session saved. ARTY has learned from this session.")


if __name__ == "__main__":
    brief()
