import numpy as np
import sounddevice as sd
import soundfile as sf
import tempfile
import os
from faster_whisper import WhisperModel
from config import WHISPER_MODEL, WAKE_WORD, PUSH_TO_TALK


class ArtyEars:
    def __init__(self):
        print("Loading Whisper model...")
        _model_dir = os.path.join(os.path.dirname(__file__), "..", "data", "whisper_model")
        os.makedirs(_model_dir, exist_ok=True)
        self.model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", download_root=_model_dir)
        self.sample_rate = 16000
        self.silence_threshold = 0.01
        self.silence_duration = 2.0   # seconds of silence before cutting off
        self.max_duration = 60

    def record_until_silence(self) -> np.ndarray:
        print("  [Listening...]")
        chunk_duration = 0.1
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
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="C:\\Temp") as f:
            tmp_path = f.name
        try:
            sf.write(tmp_path, audio, self.sample_rate)
            segments, _ = self.model.transcribe(tmp_path, language="en")
            return " ".join(seg.text for seg in segments).strip()
        finally:
            os.unlink(tmp_path)

    def listen(self) -> str:
        audio = self.record_until_silence()
        if len(audio) == 0:
            return ""
        text = self.transcribe(audio)
        if text:
            print(f"  [You said]: {text}")
        return text

    def wait_for_wake_word(self) -> bool:
        print(f"  [Waiting for wake word: '{WAKE_WORD}']")
        audio = self.record_until_silence()
        text = self.transcribe(audio).lower()
        return WAKE_WORD.lower() in text
