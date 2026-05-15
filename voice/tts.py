import io
import asyncio
import numpy as np
import sounddevice as sd
from elevenlabs import ElevenLabs, VoiceSettings
from config import ELEVENLABS_API_KEY, ARTY_VOICE_ID


def _edge_speak(text: str, voice: str = "en-AU-WilliamNeural"):
    """Microsoft Edge TTS — free neural voices, plays via sounddevice."""
    try:
        import edge_tts
        import av

        async def _generate():
            communicate = edge_tts.Communicate(text, voice)
            mp3_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_data += chunk["data"]
            return mp3_data

        mp3_data = asyncio.run(_generate())
        if not mp3_data:
            raise RuntimeError("edge-tts returned no audio")

        # Decode mp3 with PyAV (already installed via faster-whisper)
        container = av.open(io.BytesIO(mp3_data))
        stream = container.streams.audio[0]
        sample_rate = stream.rate
        samples = []
        for frame in container.decode(stream):
            samples.append(frame.to_ndarray())
        container.close()

        audio = np.concatenate(samples, axis=1).flatten()
        # Convert to int16 — same format ElevenLabs uses with sd.OutputStream
        if audio.dtype != np.int16:
            audio = (audio / max(np.abs(audio).max(), 1) * 32767).astype(np.int16)

        with sd.OutputStream(samplerate=sample_rate, channels=1, dtype="int16") as out:
            out.write(audio.reshape(-1, 1))

    except Exception as e:
        print(f"  [edge-tts error]: {e}")
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
            print("  [TTS] No ElevenLabs keys — using edge-tts.")

    def speak(self, text: str):
        if not text.strip():
            return
        if not self._use_elevenlabs:
            _edge_speak(text)
            return
        try:
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
            print(f"  [ElevenLabs error — falling back to edge-tts]: {e}")
            _edge_speak(text)

    def speak_async(self, text: str):
        import threading
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()
