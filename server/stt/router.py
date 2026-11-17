"""한 앱 연결을 한 STT 연결로 중계한다. 음성·원문을 저장하지 않는다."""

import asyncio
from contextlib import suppress
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from server.config import (
    COMMIT_AUDIO_BYTES, MAX_SESSION_SECONDS, PROVIDER_TIMEOUT_SECONDS,
    START_TIMEOUT_SECONDS, load_stt_settings,
)
from server.stt.contracts import (
    ErrorMessage, ReadyMessage, StartMessage, StatusMessage, StoppedMessage,
    StopMessage, TranscriptMessage, parse_client_message, validate_audio_chunk,
)
from server.stt.elevenlabs import SttError, open_stt_connection, receive_event, send_audio
from server.security import access
from server.security import limits
from server.security.device_store import DeviceStoreError


router = APIRouter()
ERROR_MESSAGES = {
    "invalid_message": "시작·종료 메시지 형식을 확인해 주세요.",
    "invalid_audio": "16kHz 모노 16비트 PCM 음성 형식을 확인해 주세요.",
    "invalid_state": "STT 메시지 전송 순서가 올바르지 않습니다.",
    "stt_unavailable": "음성 인식 서비스에 연결할 수 없습니다.",
    "stt_failed": "음성 인식 연결에 문제가 발생했습니다. 새 세션을 시작해 주세요.",
    "finalization_timeout": "마지막 발화 확정 결과를 받지 못했습니다.",
}


async def receive_app_message(websocket: WebSocket):
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    if message.get("bytes") is not None:
        try:
            validate_audio_chunk(message["bytes"])
        except ValueError:
            raise SttError("invalid_audio") from None
        return message["bytes"]
    try:
        return parse_client_message(message.get("text", ""))
    except ValidationError:
        raise SttError("invalid_message") from None


async def relay_audio(websocket: WebSocket, connection, conversation_id: str) -> None:
    utterance_id = 0
    uncommitted_bytes = 0
    commit_pending = False
    finalizing = False
    acknowledged = asyncio.Event()
    deadline = asyncio.get_running_loop().time() + MAX_SESSION_SECONDS

    async def receive_transcripts():
        nonlocal utterance_id
        while True:
            event = await receive_event(connection)
            if event["message_type"] == "partial_transcript":
                if not finalizing:
                    await websocket.send_json(StatusMessage(
                        conversation_id=conversation_id, status="recognizing",
                    ).model_dump())
            elif event["message_type"] == "committed_transcript":
                if not commit_pending:
                    raise SttError("stt_failed")
                text = event["text"].strip()
                if text:
                    utterance_id += 1
                    await websocket.send_json(TranscriptMessage(
                        conversation_id=conversation_id, utterance_id=utterance_id, text=text,
                    ).model_dump())
                acknowledged.set()
            else:
                raise SttError("stt_failed")

    async def commit_segment():
        nonlocal commit_pending, uncommitted_bytes
        if not uncommitted_bytes:
            return
        acknowledged.clear()
        commit_pending = True
        await send_audio(connection, b"", commit=True)
        try:
            await asyncio.wait_for(acknowledged.wait(), PROVIDER_TIMEOUT_SECONDS)
        except TimeoutError:
            raise SttError("finalization_timeout") from None
        commit_pending = False
        uncommitted_bytes = 0

    async def send_app_audio():
        nonlocal uncommitted_bytes, finalizing
        reason = "user_stop"
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                reason = "time_limit"
                break
            try:
                message = await asyncio.wait_for(receive_app_message(websocket), remaining)
            except TimeoutError:
                reason = "time_limit"
                break
            if isinstance(message, StopMessage):
                break
            if not isinstance(message, bytes):
                raise SttError("invalid_state")
            while message:
                available = COMMIT_AUDIO_BYTES - uncommitted_bytes
                chunk, message = message[:available], message[available:]
                await send_audio(connection, chunk)
                uncommitted_bytes += len(chunk)
                if uncommitted_bytes == COMMIT_AUDIO_BYTES:
                    await commit_segment()
        finalizing = True
        await websocket.send_json(StatusMessage(
            conversation_id=conversation_id, status="finalizing",
        ).model_dump())
        await commit_segment()
        return reason

    receiver = asyncio.create_task(receive_transcripts())
    sender = asyncio.create_task(send_app_audio())
    try:
        done, _ = await asyncio.wait((receiver, sender), return_when=asyncio.FIRST_COMPLETED)
        if receiver in done:
            await receiver  # 공급자 오류를 먼저 전파한다.
        reason = await sender
        await websocket.send_json(StoppedMessage(
            conversation_id=conversation_id, reason=reason, last_utterance_id=utterance_id,
        ).model_dump())
    finally:
        for task in (sender, receiver):
            task.cancel()
        await asyncio.gather(sender, receiver, return_exceptions=True)


@router.websocket("/api/v1/stt")
async def stt_websocket(websocket: WebSocket):
    peer = websocket.client.host if websocket.client else "unknown"
    if limits.invalid_auth_attempts.blocked(peer):
        await websocket.close(code=1008)
        return
    try:
        owner = await asyncio.to_thread(access.authenticate_header, websocket.headers.get("authorization"))
    except DeviceStoreError:
        await websocket.close(code=1011)
        return
    if owner is None:
        limits.invalid_auth_attempts.allow(peer)
        await websocket.close(code=1008)
        return
    if not limits.stt_sessions.acquire(owner):
        await websocket.close(code=1008)
        return
    try:
        await _run_authenticated_stt(websocket, owner)
    finally:
        limits.stt_sessions.release(owner)


async def _run_authenticated_stt(websocket: WebSocket, owner: str) -> None:
    await websocket.accept()
    conversation_id = None
    close_code = 1000
    try:
        try:
            start = await asyncio.wait_for(receive_app_message(websocket), START_TIMEOUT_SECONDS)
        except TimeoutError:
            raise SttError("invalid_message") from None
        if not isinstance(start, StartMessage):
            raise SttError("invalid_state")
        try:
            settings = load_stt_settings()
        except RuntimeError:
            raise SttError("stt_unavailable") from None
        conversation_id = str(uuid4())
        try:
            await asyncio.to_thread(access.device_store.register_conversation, owner, conversation_id)
        except DeviceStoreError:
            raise SttError("stt_unavailable") from None
        async with open_stt_connection(settings) as connection:
            await websocket.send_json(ReadyMessage(
                conversation_id=conversation_id, max_session_seconds=MAX_SESSION_SECONDS,
            ).model_dump())
            await relay_audio(websocket, connection, conversation_id)
    except WebSocketDisconnect:
        return
    except SttError as error:
        close_code = 1008 if error.code.startswith("invalid_") else 1011
        with suppress(WebSocketDisconnect):
            await websocket.send_json(ErrorMessage(
                conversation_id=conversation_id, code=error.code,
                message=ERROR_MESSAGES[error.code],
            ).model_dump())
    finally:
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.close(code=close_code)
