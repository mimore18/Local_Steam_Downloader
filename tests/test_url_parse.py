import pytest

from steam_workshop_dl.core.errors import InvalidTargetError
from steam_workshop_dl.services.steam_api import parse_target_id


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("123456789", "123456789"),
        ("https://steamcommunity.com/sharedfiles/filedetails/?id=123456789", "123456789"),
        ("https://steamcommunity.com/sharedfiles/filedetails/?id=123&x=1", "123"),
        ("  ?id=42  ", "42"),
    ],
)
def test_parse_target_id(value: str, expected: str) -> None:
    assert parse_target_id(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "https://example.com/", "0x12"])
def test_parse_target_id_rejects_garbage(value: str) -> None:
    with pytest.raises(InvalidTargetError):
        parse_target_id(value)
