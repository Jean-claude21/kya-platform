"""GitHub App pull-request adapter contract tests."""

import json
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from kya_platform.contracts.artifact_package import PackageFileKind
from kya_platform.contracts.proposal_package import ProposalFile, ProposalPackage
from kya_platform.domain.catalog import ArtifactType
from kya_platform.infrastructure.github import GitHubAppPullRequestAdapter, GitHubUnavailableError

TEST_PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC8QDk9imWqgdgy
dZgE7TLjU/ttAvZqT4xMs9hcfwydVybI0kTq5nctNf9Pcf6xfHQY+l7GnXtZV45T
G72FDs7uA99nrnH7Z24hY5io3rZufHaQ84Sw2bMjAdld+XWFzIdbneEmpoF+O23h
Hd7scj+zzKRHMLdyi9VOosgdPBUYM8kJ/PbmdFPAowivo+/yNdonh0xPveExcolU
A4aD7ZzxDE8h29F77/Ua0X+WbRznST2+rYa4wtJ/qfeEEOdZb8oNPiLusWs3vcLg
vpOdLdVuVHO4Tc9NA2V3Q/h6UPSTCtikpF3Gxgvamo030ayiaSLuGhq3NI9w1Dk9
tH96RzPVAgMBAAECggEAD2r1JTCqDfJvegZ+ilzA77RnobB97QwR0hBitoSjTFmg
cA8knNZ+SUIkZGXSNcgbHBaZX4vzV8hffDgH6Bdj5EOF7xBu/meksfBdxuripx7j
eRCwu+lAjivvGQ6+zNQI+/xsvcUiUuvcHnVbViMvS3MFu1zmkWeZc0TKvfY3RhGH
mMnt8NUhtEsmKK/sZMJgtz9dBXWbCxDTVwR4ADAGU9uD3thDwoROgr+jzCo/dSoo
p9UQSSWgklYTmVkzdUWzIIdpwwXMRQwhIlgrFMPr2MHbCT84lpe+BxrZcHjg0q+Y
CtmFV6oZnv6GOhRFxld+leAd3bfUyJIHG0oqGFhmKwKBgQDwVMi8whLM6GbkzKBj
7xbghftVe3JwLWNF6358OV+0nXAoOZAnBnh4bK4qxqoVdTRXG5peXnk2rfDsZ+tB
hKm9TtqFwbbsaUeSdwhAMWCH3FQ0dCt+30i+vBrccSkMjfkTOHPnUeRBx8BcLBns
NqMmZYsw5bTGfIFaRsl62Kc3zwKBgQDIhjMquWw1YteOCeGDWNCjXqCsslqhzJLJ
CCNopbJ9CyVPdFHuxIp98QW1+XftpahbXp9x+55BgvLH1yqkHYw/t9piFdgFq4Gm
phQ3SNeBGH1cC3wPJM/3CDFn/2k70N8uKY6gUs6aQWUppfAV9J6qdRz1s8CT7D+e
KA3jY0nfGwKBgHMT1e70avYtDh/ej6pqcKTf4uIis0Bdq1xuj+lBu78LaAoKziix
o3veZmNbL1QJBB/1uqwXRqlVDrjUZcTAllpsaJyFjmaTXs8WKiA6xIMpkDRxr+YX
WojiH2aQ1NwLG0oFzRHll4ub71LzVxJRczvOgaDPTQmB0pp8rLsjBKbnAoGAfEz8
EMLqOdmwhwLHATWf93VkIklY9y0p3GYoFOmJ0AuFsFAJrfm1Y8ZxZNFkrzLePu1T
50MzYaa7unc9nogWdTURsXWa+EDNWLFgnLiRphu5McKIv5ZxN8+jWLUx1XtvrVzj
ZayPF33sKLoNLn75j+6S6hfoC4oKEY8AtPDKTPsCgYEAjTaRkuy29vpovVOKznXB
7Rje4SiWI7J+l2ubOw/xPRkbVzmYXV43Td0aRQjOYD2MrlCapVtJj3oN2+nDIXJc
8oQ9HAsUP/vvnPcbLyB33Q00N/giwPJoURyY44j3QbIdTJHs7GvdoUA9Qchi71PJ
1A9dSNHClyPTagPU6HXwBkQ=
-----END PRIVATE KEY-----\n"""

PROPOSAL_ID = UUID("01991d00-0000-7000-8000-000000000301")
APPROVER_ID = UUID("01991d00-0000-7000-8000-000000000302")


def package() -> ProposalPackage:
    return ProposalPackage(
        files=[
            ProposalFile(
                path="SKILL.md",
                kind=PackageFileKind.INSTRUCTION,
                content_base64="LS0tCm5hbWU6IHNvbGFyLWJyaWVmCi0tLQo=",
            )
        ]
    )


def adapter(
    handler: httpx.MockTransport,
) -> tuple[GitHubAppPullRequestAdapter, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    return (
        GitHubAppPullRequestAdapter(
            client,
            app_id="app-1",
            installation_id="install-1",
            private_key=SecretStr(TEST_PRIVATE_KEY_PEM),
            base_branch="dev",
            api_url="https://api.github.test",
        ),
        client,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("artifact_type", "source_directory"),
    (
        (ArtifactType.SKILL, "skills"),
        (ArtifactType.MCP_SERVER, "mcp-servers"),
        (ArtifactType.APPLICATION, "applications"),
        (ArtifactType.DOCUMENT_TYPE, "document-types"),
    ),
)
async def test_open_pull_request_never_holds_standing_merge_rights(
    artifact_type: ArtifactType, source_directory: str
) -> None:
    calls: list[str] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": "installation-token"})
        if request.url.path.endswith("/git/ref/heads/dev"):
            assert request.headers["Authorization"] == "Bearer installation-token"
            return httpx.Response(200, json={"object": {"sha": "a" * 40}})
        if request.url.path.endswith(f"/git/commits/{'a' * 40}"):
            return httpx.Response(200, json={"tree": {"sha": "base-tree-sha"}})
        if request.url.path.endswith("/git/blobs"):
            body = json.loads(request.content)
            assert body["encoding"] == "base64"
            return httpx.Response(201, json={"sha": "blob-sha"})
        if request.url.path.endswith("/git/trees"):
            body = json.loads(request.content)
            assert body["base_tree"] == "base-tree-sha"
            assert body["tree"][0]["path"] == (
                f"catalog/sources/{source_directory}/solar-brief/SKILL.md"
            )
            return httpx.Response(201, json={"sha": "tree-sha"})
        if request.url.path.endswith("/git/commits"):
            body = json.loads(request.content)
            assert body["parents"] == ["a" * 40]
            return httpx.Response(201, json={"sha": "new-commit-sha"})
        if request.url.path.endswith(
            "/git/refs/heads/feat-proposal-solar-brief-" + PROPOSAL_ID.hex[:12]
        ):
            body = json.loads(request.content)
            assert body["sha"] == "new-commit-sha"
            return httpx.Response(200, json={})
        if request.url.path.endswith("/git/refs"):
            body = json.loads(request.content)
            assert body["ref"] == (f"refs/heads/feat-proposal-solar-brief-{PROPOSAL_ID.hex[:12]}")
            return httpx.Response(201, json={})
        if request.url.path.endswith("/pulls"):
            body = json.loads(request.content)
            assert body["base"] == "dev"
            assert str(PROPOSAL_ID) in body["body"]
            return httpx.Response(
                201, json={"html_url": "https://github.test/kya/kya-platform/pull/9"}
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    service, client = adapter(httpx.MockTransport(handle))
    async with client:
        url = await service.open_pull_request(
            repository="kya-energy/kya-platform",
            slug="solar-brief",
            artifact_type=artifact_type,
            package=package(),
            required_approver_id=APPROVER_ID,
            proposal_id=PROPOSAL_ID,
        )

    assert url == "https://github.test/kya/kya-platform/pull/9"
    assert any(call.endswith("/access_tokens") for call in calls)
    assert not any("merge" in call for call in calls)


@pytest.mark.anyio
async def test_get_merge_commit_returns_none_while_still_open() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": "installation-token"})
        assert request.url.path == "/repos/kya/kya-platform/pulls/9"
        return httpx.Response(200, json={"merged": False})

    service, client = adapter(httpx.MockTransport(handle))
    async with client:
        result = await service.get_merge_commit("https://github.test/kya/kya-platform/pull/9")

    assert result is None


@pytest.mark.anyio
async def test_get_merge_commit_returns_the_real_commit_once_merged() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": "installation-token"})
        return httpx.Response(200, json={"merged": True, "merge_commit_sha": "b" * 40})

    service, client = adapter(httpx.MockTransport(handle))
    async with client:
        result = await service.get_merge_commit("https://github.test/kya/kya-platform/pull/9")

    assert result == "b" * 40


@pytest.mark.anyio
async def test_provider_failures_do_not_leak_response_content() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": "installation-token"})
        return httpx.Response(500, text="secret-leak-should-not-appear")

    service, client = adapter(httpx.MockTransport(handle))
    async with client:
        with pytest.raises(GitHubUnavailableError) as failure:
            await service.get_merge_commit("https://github.test/kya/kya-platform/pull/9")

    assert "secret-leak-should-not-appear" not in str(failure.value)


@pytest.mark.anyio
async def test_installation_token_is_cached_across_calls() -> None:
    token_requests = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        if request.url.path.endswith("/access_tokens"):
            token_requests += 1
            return httpx.Response(201, json={"token": "installation-token"})
        return httpx.Response(200, json={"merged": False})

    service, client = adapter(httpx.MockTransport(handle))
    async with client:
        await service.get_merge_commit("https://github.test/kya/kya-platform/pull/9")
        await service.get_merge_commit("https://github.test/kya/kya-platform/pull/9")

    assert token_requests == 1


def test_missing_credentials_are_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="required"):
        GitHubAppPullRequestAdapter(
            httpx.AsyncClient(),
            app_id="",
            installation_id="install-1",
            private_key=SecretStr(TEST_PRIVATE_KEY_PEM),
        )


def test_malformed_pull_request_url_is_rejected() -> None:
    with pytest.raises(GitHubUnavailableError, match="malformed"):
        GitHubAppPullRequestAdapter._parse_pull_request_url("not-a-url")
