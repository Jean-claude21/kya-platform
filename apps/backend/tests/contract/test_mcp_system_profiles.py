"""Initial MCP profiles are bounded, explicit and cover every active handler."""

from kya_platform.mcp.registry.profiles import SYSTEM_PROFILES, TOOL_REGISTRATIONS


def test_tool_registration_matches_active_handlers_once() -> None:
    keys = [item.key for item in TOOL_REGISTRATIONS]
    assert len(keys) == len(set(keys))
    assert len(keys) == 19
    assert all(item.description and item.oauth_scope for item in TOOL_REGISTRATIONS)


def test_system_profiles_are_bounded_and_reference_registered_tools() -> None:
    known = {item.key for item in TOOL_REGISTRATIONS}
    assert {profile.key for profile in SYSTEM_PROFILES} == {
        "registry-reader",
        "data-reader",
        "data-operator",
        "catalog-publisher",
    }
    assert all(0 < len(profile.tool_keys) <= 24 for profile in SYSTEM_PROFILES)
    assert all(set(profile.tool_keys) <= known for profile in SYSTEM_PROFILES)
    assert "start_ingestion" not in next(
        profile.tool_keys for profile in SYSTEM_PROFILES if profile.key == "data-reader"
    )
    assert "start_ingestion" in next(
        profile.tool_keys for profile in SYSTEM_PROFILES if profile.key == "data-operator"
    )
