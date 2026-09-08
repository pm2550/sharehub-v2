"""PM Drive (Cloudreve v4) API client.

Wraps the Cloudreve API for file upload, download URL generation, and deletion.
Stores files under cloudreve://my/sharehub/ on the sharehub@pm2550.com account.
"""

import time
import asyncio
import logging
from typing import AsyncIterator, Optional
from urllib.parse import quote

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_URL = settings.PMDRIVE_BASE_URL.rstrip("/")
EMAIL = settings.PMDRIVE_EMAIL
PASSWORD = settings.PMDRIVE_PASSWORD
ROOT_DIR = settings.PMDRIVE_ROOT_DIR.rstrip("/")

_access_token: Optional[str] = None
_access_expires_at: float = 0.0
_refresh_token: Optional[str] = None
_token_lock = asyncio.Lock()


class PMDriveError(Exception):
    pass


async def _login(client: httpx.AsyncClient) -> None:
    global _access_token, _access_expires_at, _refresh_token
    r = await client.post(
        f"{BASE_URL}/api/v4/session/token",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise PMDriveError(f"Login failed: {data.get('msg')}")
    token = data["data"]["token"]
    _access_token = token["access_token"]
    _refresh_token = token["refresh_token"]
    _access_expires_at = time.time() + 3000
    logger.info("pmdrive: logged in as %s", EMAIL)


async def _refresh(client: httpx.AsyncClient) -> None:
    global _access_token, _access_expires_at
    if not _refresh_token:
        await _login(client)
        return
    r = await client.post(
        f"{BASE_URL}/api/v4/session/token/refresh",
        json={"refresh_token": _refresh_token},
        timeout=30,
    )
    if r.status_code != 200:
        await _login(client)
        return
    data = r.json()
    if data.get("code") != 0:
        await _login(client)
        return
    _access_token = data["data"]["access_token"]
    _access_expires_at = time.time() + 3000


async def _ensure_token(client: httpx.AsyncClient) -> str:
    async with _token_lock:
        if _access_token is None:
            await _login(client)
        elif time.time() >= _access_expires_at:
            await _refresh(client)
    return _access_token  # type: ignore[return-value]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _encode_uri(uri: str) -> str:
    return quote(uri, safe="")


async def ensure_root_dir() -> None:
    """Create ROOT_DIR if it doesn't exist. Idempotent."""
    async with httpx.AsyncClient() as client:
        token = await _ensure_token(client)
        r = await client.post(
            f"{BASE_URL}/api/v4/file/create",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"uri": ROOT_DIR, "type": "folder"},
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("code") in (0, 40004):
                return
        logger.warning("pmdrive: ensure_root_dir status=%s body=%s", r.status_code, r.text[:200])


async def create_upload_session(
    client: httpx.AsyncClient,
    filename: str,
    size: int,
    mime_type: str = "application/octet-stream",
) -> dict:
    """Create an upload session. Returns {session_id, chunk_size, uri}."""
    token = await _ensure_token(client)
    uri = f"{ROOT_DIR}/{filename}"
    r = await client.put(
        f"{BASE_URL}/api/v4/file/upload",
        headers={**_auth_headers(token), "Content-Type": "application/json"},
        json={
            "uri": uri,
            "size": size,
            "last_modified": int(time.time() * 1000),
            "mime_type": mime_type,
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise PMDriveError(f"create_upload_session failed: {data.get('msg')}")
    return {
        "session_id": data["data"]["session_id"],
        "chunk_size": data["data"]["chunk_size"],
        "uri": data["data"]["uri"],
    }


async def upload_chunk(
    client: httpx.AsyncClient,
    session_id: str,
    chunk_index: int,
    chunk: bytes,
) -> None:
    token = await _ensure_token(client)
    r = await client.post(
        f"{BASE_URL}/api/v4/file/upload/{session_id}/{chunk_index}",
        headers={**_auth_headers(token), "Content-Type": "application/octet-stream"},
        content=chunk,
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise PMDriveError(f"upload_chunk[{chunk_index}] failed: {data.get('msg')}")


async def cancel_upload_session(client: httpx.AsyncClient, session_id: str, uri: str) -> None:
    """Cancel an upload session and remove the partial entity.

    Both id and uri are required — Cloudreve silently ignores the request
    if uri is empty, leaving an orphan entity that blocks re-upload.
    """
    token = await _ensure_token(client)
    try:
        r = await client.request(
            "DELETE",
            f"{BASE_URL}/api/v4/file/upload",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"id": session_id, "uri": uri},
            timeout=30,
        )
        if r.status_code != 200 or r.json().get("code") != 0:
            logger.warning("pmdrive: cancel_upload_session uri=%s resp=%s", uri, r.text[:200])
    except Exception as e:
        logger.warning("pmdrive: cancel_upload_session error: %s", e)


async def upload_stream(
    filename: str,
    size: int,
    stream: AsyncIterator[bytes],
    mime_type: str = "application/octet-stream",
) -> str:
    """Upload a file via async byte stream. Buffers into Cloudreve chunks.

    Returns the cloudreve URI (e.g. cloudreve://my/sharehub/abc.zip).
    """
    async with httpx.AsyncClient() as client:
        session = await create_upload_session(client, filename, size, mime_type)
        session_id = session["session_id"]
        chunk_size = session["chunk_size"]
        uri = session["uri"]

        try:
            buf = bytearray()
            chunk_index = 0
            async for piece in stream:
                buf.extend(piece)
                while len(buf) >= chunk_size:
                    await upload_chunk(client, session_id, chunk_index, bytes(buf[:chunk_size]))
                    del buf[:chunk_size]
                    chunk_index += 1
            if buf or chunk_index == 0:
                await upload_chunk(client, session_id, chunk_index, bytes(buf))
        except Exception:
            await cancel_upload_session(client, session_id, uri)
            raise

        return uri


async def begin_upload(
    filename: str, size: int, mime_type: str = "application/octet-stream"
) -> dict:
    """Open an upload session that outlives this request.

    Unlike upload_stream(), the caller keeps session_id/uri in the DB and feeds
    chunks across separate HTTP requests via push_chunk(). Returns the same
    {session_id, chunk_size, uri} dict.
    """
    async with httpx.AsyncClient() as client:
        return await create_upload_session(client, filename, size, mime_type)


async def push_chunk(session_id: str, chunk_index: int, chunk: bytes) -> None:
    """Send one chunk to an already-open session (own connection)."""
    async with httpx.AsyncClient() as client:
        await upload_chunk(client, session_id, chunk_index, chunk)


async def abort_upload(session_id: str, uri: str) -> None:
    """Cancel an open session and drop its partial entity."""
    async with httpx.AsyncClient() as client:
        await cancel_upload_session(client, session_id, uri)


async def upload_file(local_path: str, filename: str, mime_type: str = "application/octet-stream") -> str:
    """Upload a file from disk. Returns the cloudreve URI."""
    import os

    size = os.path.getsize(local_path)

    async def _reader() -> AsyncIterator[bytes]:
        with open(local_path, "rb") as f:
            while True:
                buf = f.read(1024 * 1024)
                if not buf:
                    break
                yield buf

    return await upload_stream(filename, size, _reader(), mime_type)


async def get_source_url(uri: str) -> str:
    """Get a signed public download URL for the file. Follow the redirect to get the real link."""
    async with httpx.AsyncClient() as client:
        token = await _ensure_token(client)
        r = await client.put(
            f"{BASE_URL}/api/v4/file/source",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"uris": [uri]},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0 or not data["data"]:
            raise PMDriveError(f"get_source_url failed: {data.get('msg')}")
        return data["data"][0]["link"]


async def delete_file(uri: str) -> None:
    async with httpx.AsyncClient() as client:
        token = await _ensure_token(client)
        r = await client.request(
            "DELETE",
            f"{BASE_URL}/api/v4/file",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"uris": [uri], "unlink": False, "skip_soft_delete": True},
            timeout=30,
        )
        if r.status_code != 200:
            logger.warning("pmdrive: delete %s http=%s body=%s", uri, r.status_code, r.text[:200])
            return
        data = r.json()
        if data.get("code") != 0:
            logger.warning("pmdrive: delete %s code=%s msg=%s", uri, data.get("code"), data.get("msg"))
