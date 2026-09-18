"""Async Zoom API adapter with token caching and safe result projection."""

from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from kya_zoom_mcp.contracts import MeetingList, MeetingRecord


class ZoomCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    client_secret: SecretStr


class ZoomAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str, code: int | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"Zoom API {status_code}: {message}")


@dataclass(slots=True)
class _CachedToken:
    value: str
    expires_at: float

    def is_valid(self) -> bool:
        return time.monotonic() < self.expires_at - 60


class ZoomAPIAdapter:
    def __init__(
        self,
        credentials: ZoomCredentials,
        http: httpx.AsyncClient,
        *,
        api_base_url: str = "https://api.zoom.us/v2",
        oauth_endpoint: str = "https://zoom.us/oauth/token",
    ) -> None:
        self._credentials = credentials
        self._http = http
        self._api_base_url = api_base_url.rstrip("/")
        self._oauth_endpoint = oauth_endpoint
        self._token: _CachedToken | None = None
        self._token_lock = asyncio.Lock()

    async def _access_token(self) -> str:
        cached = self._token
        if cached is not None and cached.is_valid():
            return cached.value
        async with self._token_lock:
            cached = self._token
            if cached is not None and cached.is_valid():
                return cached.value
            raw = (
                f"{self._credentials.client_id}:"
                f"{self._credentials.client_secret.get_secret_value()}"
            )
            encoded = base64.b64encode(raw.encode()).decode()
            response = await self._http.post(
                self._oauth_endpoint,
                params={
                    "grant_type": "account_credentials",
                    "account_id": self._credentials.account_id,
                },
                headers={"Authorization": f"Basic {encoded}"},
            )
            if response.status_code != 200:
                raise ZoomAPIError(response.status_code, "Zoom OAuth rejected the connection")
            payload = response.json()
            token = payload.get("access_token")
            if not isinstance(token, str) or not token:
                raise ZoomAPIError(502, "Zoom OAuth response has no access_token")
            self._token = _CachedToken(
                value=token,
                expires_at=time.monotonic() + float(payload.get("expires_in", 3_600)),
            )
            return token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int | float | bool | None] | None = None,
        body: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        for attempt in (1, 2):
            token = await self._access_token()
            response = await self._http.request(
                method,
                f"{self._api_base_url}{path}",
                params=params,
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 401 and attempt == 1:
                self._token = None
                continue
            if response.status_code == 204:
                return {}
            payload = response.json()
            if response.is_success and isinstance(payload, dict):
                return payload
            if not isinstance(payload, dict):
                raise ZoomAPIError(response.status_code, "Unexpected Zoom response")
            raise ZoomAPIError(
                response.status_code,
                str(payload.get("message") or payload.get("error") or "Unknown Zoom error"),
                payload.get("code") if isinstance(payload.get("code"), int) else None,
            )
        raise ZoomAPIError(401, "Zoom authentication failed after token renewal")

    @staticmethod
    def _safe_meeting(payload: dict[str, Any]) -> MeetingRecord:
        """Project the provider response; privileged host URLs never cross this boundary."""

        return MeetingRecord(
            meeting_id=str(payload["id"]),
            topic=str(payload.get("topic") or "Untitled meeting"),
            start_time=payload.get("start_time"),
            timezone=payload.get("timezone"),
            duration_minutes=payload.get("duration"),
            status=payload.get("status"),
            join_url=payload.get("join_url"),
            passcode=payload.get("password"),
        )

    async def create_meeting(self, host_id: str, payload: dict[str, object]) -> MeetingRecord:
        response = await self._request("POST", f"/users/{host_id}/meetings", body=payload)
        return self._safe_meeting(response)

    async def list_meetings(
        self, host_id: str, *, page_size: int, next_page_token: str | None
    ) -> MeetingList:
        response = await self._request(
            "GET",
            f"/users/{host_id}/meetings",
            params={
                "type": "upcoming",
                "page_size": page_size,
                "next_page_token": next_page_token or "",
            },
        )
        meetings = response.get("meetings", [])
        if not isinstance(meetings, list):
            raise ZoomAPIError(502, "Zoom meetings payload is not a list")
        return MeetingList(
            items=[self._safe_meeting(item) for item in meetings if isinstance(item, dict)],
            next_page_token=response.get("next_page_token") or None,
        )

    async def get_meeting(self, meeting_id: str) -> MeetingRecord:
        response = await self._request("GET", f"/meetings/{meeting_id}")
        return self._safe_meeting(response)
