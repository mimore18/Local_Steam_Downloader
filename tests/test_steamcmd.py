from pathlib import Path

from steam_workshop_dl.core.models import NodeKind, WorkshopNode
from steam_workshop_dl.services.steamcmd import (
    build_command,
    parse_line,
    write_runscript,
)


def test_parse_success_line() -> None:
    parsed = parse_line('Success. Downloaded item 111 to "/tmp/steamapps/workshop/content/4000/111" (123 bytes)')
    assert parsed is not None
    assert parsed.kind == "success"
    assert parsed.item_id == "111"
    assert parsed.path == Path("/tmp/steamapps/workshop/content/4000/111")


def test_parse_failure_line() -> None:
    parsed = parse_line("ERROR! Download item 222 failed (Failure).")
    assert parsed is not None
    assert parsed.kind == "failure"
    assert parsed.item_id == "222"


def test_parse_irrelevant_line() -> None:
    assert parse_line("Update state (0x61) downloading, progress: 50.00") is None


def test_write_runscript(tmp_path: Path) -> None:
    script = tmp_path / "download.txt"
    items = [
        WorkshopNode(id="1", kind=NodeKind.ITEM, appid=4000),
        WorkshopNode(id="2", kind=NodeKind.ITEM, appid=730),
    ]
    write_runscript(script, items, auth_mode="anonymous", username=None, validate=True)
    text = script.read_text(encoding="utf-8")
    assert "@ShutdownOnFailedCommand 0" in text
    assert "login anonymous" in text
    assert "workshop_download_item 4000 1 validate" in text
    assert "workshop_download_item 730 2 validate" in text
    assert text.endswith("quit\n")


def test_build_command() -> None:
    command = build_command(Path("/opt/steamcmd.sh"), Path("/tmp/script.txt"))
    assert command == ["/opt/steamcmd.sh", "+runscript", "/tmp/script.txt", "+quit"]
