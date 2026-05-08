import io
import os
import sounddevice as sd
import soundfile as sf
import numpy as np
from elevenlabs import ElevenLabs, VoiceSettings
from config import ELEVENLABS_API_KEY, ARTY_VOICE_ID


class ArtyVoice:
    def __init__(self):
        self.client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        self.voice_id = ARTY_VOICE_ID
        self.voice_settings = VoiceSettings(
            stability=0.45,         # slightly varied = more natural
            similarity_boost=0.85,
            style=0.35,             # adds expressiveness
            use_speaker_boost=True
        )

    def speak(self, text: str):
        """Convert text to speech and play it."""
        if not text.strip():
            return
        try:
            audio_bytes = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id="eleven_turbo_v2_5",
                voice_settings=self.voice_settings
            )
            audio_data = b"".join(audio_bytes)
            buf = io.BytesIO(audio_data)
            data, samplerate = sf.read(buf)
            if data.ndim == 1:
                data = data.reshape(-1, 1)
            sd.play(data, samplerate)
            sd.wait()
        except Exception as e:
            print(f"  [TTS error]: {e}")
            print(f"  [ARTY would say]: {text}")

    def speak_async(self, text: str):
        """Speak without blocking — use for non-critical output."""
        import threading
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()
