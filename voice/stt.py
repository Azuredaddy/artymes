import whisper
import numpy as np
import sounddevice as sd
import soundfile as sf
import tempfile
import os
from config import WHISPER_MODEL, WAKE_WORD, PUSH_TO_TALK


class ArtyEars:
    def __init__(self):
        print("Loading Whisper model...")
        self.model = whisper.load_model(WHISPER_MODEL)
        self.sample_rate = 16000
        self.silence_threshold = 0.01
        self.silence_duration = 1.5  # seconds of silence to stop recording
        self.max_duration = 30       # max recording seconds

    def record_until_silence(self) -> np.ndarray:
        """Record audio from mic, stopping on silence."""
        print("  [Listening...]")
        chunk_duration = 0.1  # seconds per chunk
        chunk_samples = int(self.sample_rate * chunk_duration)
        silence_chunks = int(self.silence_duration / chunk_duration)

        audio_chunks = []
        silent_count = 0
        started = False

        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='float32') as stream:
            total_chunks = int(self.max_duration / chunk_duration)
            for _ in range(total_chunks):
                chunk, _ = stream.read(chunk_samples)
                rms = np.sqrt(np.mean(chunk ** 2))

                if rms > self.silence_threshold:
                    started = True
                    silent_count = 0
                    audio_chunks.append(chunk)
                elif started:
                    audio_chunks.append(chunk)
                    silent_count += 1
                    if silent_count >= silence_chunks:
                        break

        if not audio_chunks:
            return np.array([])
        return np.concatenate(audio_chunks, axis=0).flatten()

    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) == 0:
            return ""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        try:
            sf.write(tmp_path, audio, self.sample_rate)
            result = self.model.transcribe(tmp_path, language="en", fp16=False)
            return result["text"].strip()
        finally:
            os.unlink(tmp_path)

    def listen(self) -> str:
        """Full listen cycle: record then transcribe."""
        audio = self.record_until_silence()
        if len(audio) == 0:
            return ""
        text = self.transcribe(audio)
        if text:
            print(f"  [You said]: {text}")
        return text

    def wait_for_wake_word(self) -> bool:
        """Listen for wake word, return True when heard."""
        print(f"  [Waiting for wake word: '{WAKE_WORD}']")
        audio = self.record_until_silence()
        text = self.transcribe(audio).lower()
        return WAKE_WORD.lower() in text
