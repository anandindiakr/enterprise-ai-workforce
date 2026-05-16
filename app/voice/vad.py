"""Energy-based Voice Activity Detection (VAD) utility.

Operates on raw PCM-16 audio frames to determine whether a frame contains
speech or silence.  The algorithm is a simplified WebRTC-style energy VAD:

1. Compute root-mean-square energy of the frame.
2. Apply a slowly-adapting background-noise floor estimate.
3. Trip "speech detected" when energy exceeds the noise floor by
   ``speech_ratio`` dB.
4. Hold the "speech" state for ``hangover_frames`` frames after the last
   energetic frame to absorb short pauses.

This is used server-side when receiving raw PCM16 audio over WebSocket to
decide when to send the accumulated audio to the STT provider.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field


@dataclass
class VADResult:
    is_speech: bool
    energy_db: float          # Current frame energy in dBFS
    noise_floor_db: float     # Current estimated noise floor
    snr_db: float             # Signal-to-noise ratio


@dataclass
class EnergyVAD:
    """Stateful energy-based VAD.

    Parameters
    ----------
    sample_rate:
        Audio sample rate in Hz (default 16 000 Hz).
    frame_ms:
        Frame duration in milliseconds (default 20 ms).
    speech_ratio_db:
        dB above noise floor that triggers speech (default 10 dB).
    hangover_frames:
        Extra frames to hold "speech" state after energy drops below threshold
        (default 8 frames ≈ 160 ms at 20 ms frames).
    noise_adapt_rate:
        EMA rate for noise-floor adaptation during non-speech (default 0.95).
    """

    sample_rate: int = 16_000
    frame_ms: int = 20
    speech_ratio_db: float = 10.0
    hangover_frames: int = 8
    noise_adapt_rate: float = 0.95

    _noise_floor: float = field(default=-60.0, init=False, repr=False)
    _hangover: int      = field(default=0,     init=False, repr=False)

    # ── Public API ────────────────────────────────────────────────────────────

    def process_pcm16_bytes(self, raw: bytes) -> VADResult:
        """Process a chunk of raw PCM-16 little-endian audio bytes."""
        if len(raw) < 2:
            return VADResult(is_speech=False, energy_db=-96.0, noise_floor_db=self._noise_floor, snr_db=-96.0)

        n_samples = len(raw) // 2
        samples = struct.unpack(f"<{n_samples}h", raw[: n_samples * 2])
        return self._process_samples(samples)

    def process_pcm16_array(self, samples: list[int] | tuple[int, ...]) -> VADResult:
        return self._process_samples(samples)

    def reset(self) -> None:
        self._noise_floor = -60.0
        self._hangover = 0

    # ── Internal ──────────────────────────────────────────────────────────────

    def _process_samples(self, samples: list[int] | tuple[int, ...]) -> VADResult:
        # RMS energy
        if not samples:
            energy_db = -96.0
        else:
            rms = math.sqrt(sum(s * s for s in samples) / len(samples))
            energy_db = 20.0 * math.log10(max(rms, 1e-10) / 32768.0)

        snr_db = energy_db - self._noise_floor
        is_above = snr_db >= self.speech_ratio_db

        if is_above:
            self._hangover = self.hangover_frames
            is_speech = True
        elif self._hangover > 0:
            self._hangover -= 1
            is_speech = True
        else:
            is_speech = False
            # Adapt noise floor upward slowly during silence
            self._noise_floor = (
                self.noise_adapt_rate * self._noise_floor
                + (1 - self.noise_adapt_rate) * energy_db
            )

        return VADResult(
            is_speech=is_speech,
            energy_db=energy_db,
            noise_floor_db=self._noise_floor,
            snr_db=snr_db,
        )


# ── Convenience helpers ───────────────────────────────────────────────────────

def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """Decode 8-bit µ-law (Twilio format) to 16-bit PCM little-endian."""
    out = bytearray(len(mulaw_bytes) * 2)
    for i, byte in enumerate(mulaw_bytes):
        sample = _mulaw_decode(byte)
        struct.pack_into("<h", out, i * 2, sample)
    return bytes(out)


def _mulaw_decode(u: int) -> int:
    """Decode a single µ-law byte to a signed 16-bit PCM sample."""
    u = ~u & 0xFF
    sign = u & 0x80
    exp  = (u >> 4) & 0x07
    mant = u & 0x0F
    sample = ((mant << 1) + 33) << (exp + 2)
    sample -= 33
    return -sample if sign else sample
