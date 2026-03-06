from __future__ import annotations

import asyncio
import logging
import numpy as np

import config

logger = logging.getLogger("kenji.listener")

# Lazy-init whisper model
_whisper_model = None


def _get_model():
    """Lazy-load the Whisper model on first use."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper model '%s' ...", config.WHISPER_MODEL)
        _whisper_model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    return _whisper_model


def _record_system_audio(duration: float, target_rate: int = 16000) -> np.ndarray:
    """Record system audio via WASAPI loopback. Returns mono float32 numpy array at 16kHz."""
    import pyaudio
    import wave
    import io

    p = pyaudio.PyAudio()

    # Find a WASAPI loopback device (Windows system audio capture)
    loopback_index = None
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        name = dev["name"].lower()
        # WASAPI loopback devices typically have "loopback" in the name
        # when using the WASAPI host API
        if dev["maxInputChannels"] > 0 and (
            "loopback" in name
            or "stereo mix" in name
            or "what u hear" in name
            or "wave out" in name
        ):
            loopback_index = i
            logger.info("Found loopback device: [%d] %s", i, dev["name"])
            break

    if loopback_index is None:
        # Fall back: try to find the default output device's loopback
        # On Windows, we can use the default speakers
        default_output = p.get_default_output_device_info()
        logger.warning(
            "No loopback device found. Using default input instead. "
            "For best results, enable 'Stereo Mix' in Windows Sound settings, "
            "or install a virtual audio cable."
        )
        loopback_index = None  # use default input

    # Get device info for sample rate
    if loopback_index is not None:
        dev_info = p.get_device_info_by_index(loopback_index)
        device_rate = int(dev_info["defaultSampleRate"])
        channels = min(dev_info["maxInputChannels"], 2)
    else:
        dev_info = p.get_default_input_device_info()
        device_rate = int(dev_info["defaultSampleRate"])
        channels = min(dev_info["maxInputChannels"], 2)

    logger.info("Recording %ds of audio (device=%s, rate=%d, channels=%d)...",
                int(duration), loopback_index, device_rate, channels)

    chunk_size = 1024
    frames = []

    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=device_rate,
            input=True,
            input_device_index=loopback_index,
            frames_per_buffer=chunk_size,
        )

        total_chunks = int(device_rate / chunk_size * duration)
        for _ in range(total_chunks):
            data = stream.read(chunk_size, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()
    finally:
        p.terminate()

    logger.info("Recording complete.")

    # Convert to numpy float32
    audio = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0

    # Convert stereo to mono if needed
    if channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)

    # Resample to 16kHz if the device rate is different
    if device_rate != target_rate:
        # Simple linear interpolation resampling
        original_length = len(audio)
        target_length = int(original_length * target_rate / device_rate)
        indices = np.linspace(0, original_length - 1, target_length)
        audio = np.interp(indices, np.arange(original_length), audio)

    return audio.astype(np.float32)


def _transcribe(audio: np.ndarray) -> str:
    """Transcribe audio using faster-whisper. Returns the transcribed text."""
    model = _get_model()
    segments, info = model.transcribe(audio, beam_size=5, language="en")
    text = " ".join(seg.text.strip() for seg in segments)
    return text.strip()


async def listen_and_transcribe() -> str | None:
    """Record system audio for LISTEN_DURATION seconds and transcribe it.

    Returns the transcribed text, or None if nothing meaningful was heard.
    """
    loop = asyncio.get_running_loop()

    # Record in a thread so we don't block the event loop
    logger.info("Starting audio recording (%ds)...", config.LISTEN_DURATION)
    try:
        audio = await loop.run_in_executor(None, _record_system_audio, config.LISTEN_DURATION)
        logger.info("Audio recorded, %d samples. Max amplitude: %.4f", len(audio), float(np.max(np.abs(audio))))
    except Exception:
        logger.exception("Failed to record audio")
        return None

    # Check if audio is essentially silence
    if float(np.max(np.abs(audio))) < 0.01:
        logger.info("Audio is silence, skipping transcription.")
        return None

    # Transcribe in a thread
    logger.info("Starting transcription...")
    try:
        text = await loop.run_in_executor(None, _transcribe, audio)
    except Exception:
        logger.exception("Failed to transcribe audio")
        return None

    if not text or len(text.strip()) < 10:
        logger.info("No meaningful audio detected. Transcription: '%s'", text)
        return None

    logger.info("Transcribed: %s", text[:200])
    return text
