import io
import os
import numpy as np
import sounddevice as sd
import soundfile as sf
from elevenlabs import ElevenLabs, VoiceSettings
from config import ELEVENLABS_API_KEY, ARTY_VOICE_ID


def _pyttsx3_speak(text: str):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"  [Local TTS error]: {e}")
        print(f"  [ARTY would say]: {text}")


class ArtyVoice:
    def __init__(self):
        self._use_elevenlabs = bool(ELEVENLABS_API_KEY and ARTY_VOICE_ID)
        if self._use_elevenlabs:
            self.client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            self.voice_id = ARTY_VOICE_ID
            self.voice_settings = VoiceSettings(
                stability=0.45,
                similarity_boost=0.85,
                style=0.35,
                use_speaker_boost=True
            )
        else:
            print("  [TTS] No ElevenLabs keys — using local voice.")

    def speak(self, text: str):
        if not text.strip():
            return
        if not self._use_elevenlabs:
            _pyttsx3_speak(text)
            return
        try:
            # PCM output: raw 16-bit samples at 24kHz — no MP3 decoding, plays on first chunk
            chunks = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id="eleven_turbo_v2_5",
                voice_settings=self.voice_settings,
                output_format="pcm_24000",
            )
            with sd.OutputStream(samplerate=24000, channels=1, dtype="int16") as out:
                for chunk in chunks:
                    if chunk:
                        out.write(np.frombuffer(chunk, dtype=np.int16).reshape(-1, 1))
        except Exception as e:
            print(f"  [ElevenLabs error — falling back to local voice]: {e}")
            _pyttsx3_speak(text)

    def speak_async(self, text: str):
        import threading
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()
