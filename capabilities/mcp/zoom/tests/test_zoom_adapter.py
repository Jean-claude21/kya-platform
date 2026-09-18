from __future__ import annotations

import httpx
import respx

from kya_zoom_mcp.adapters.zoom import ZoomAPIAdapter, ZoomCredentials


@respx.mock
async def test_create_strips_privileged_host_url() -> None:
    respx.post("https://zoom.us/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
    )
    respx.post("https://api.zoom.us/v2/users/host/meetings").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": 123,
                "topic": "Point projet",
                "join_url": "https://zoom.us/j/123",
                "start_url": "https://zoom.us/s/123?zak=privileged-host-secret",
                "password": "shareable",
            },
        )
    )

    async with httpx.AsyncClient() as http:
        adapter = ZoomAPIAdapter(
            ZoomCredentials(account_id="account", client_id="client", client_secret="secret"),
            http,
        )
        meeting = await adapter.create_meeting("host", {"topic": "Point projet"})

    dumped = meeting.model_dump(mode="json")
    assert dumped["join_url"] == "https://zoom.us/j/123"
    assert "start_url" not in dumped
    assert "zak" not in str(dumped)


@respx.mock
async def test_token_is_cached_between_zoom_requests() -> None:
    token = respx.post("https://zoom.us/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
    )
    respx.get("https://api.zoom.us/v2/meetings/123").mock(
        return_value=httpx.Response(200, json={"id": 123, "topic": "Point projet"})
    )

    async with httpx.AsyncClient() as http:
        adapter = ZoomAPIAdapter(
            ZoomCredentials(account_id="account", client_id="client", client_secret="secret"),
            http,
        )
        await adapter.get_meeting("123")
        await adapter.get_meeting("123")

    assert token.call_count == 1
