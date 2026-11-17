"""STT 연결 설정. 환경변수는 연결 준비 시 명시적으로 읽는다."""

import os
from dataclasses import dataclass, field


SAMPLE_RATE = 16_000
MAX_AUDIO_CHUNK_BYTES = SAMPLE_RATE * 2  # 모노 16비트 PCM 최대 1초
MAX_SESSION_SECONDS = 600
COMMIT_AUDIO_BYTES = SAMPLE_RATE * 2 * 9 // 2  # 오디오 4.5초마다 발화 확정 요청
START_TIMEOUT_SECONDS = 10
PROVIDER_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class SttSettings:
    api_key: str = field(repr=False)
    url: str = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
    model_id: str = "scribe_v2_realtime"
    audio_format: str = "pcm_16000"
    language_code: str = "ko"
    commit_strategy: str = "manual"


def load_stt_settings() -> SttSettings:
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")
    return SttSettings(api_key=api_key)
