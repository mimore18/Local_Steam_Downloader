from pathlib import Path

from steam_workshop_dl.core.models import NodeKind, WorkshopNode
from steam_workshop_dl.services.steamcmd import (
    build_command,
    decode_steamcmd,
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
    assert parse_line("Connecting anonymously to Steam Public...") is None


def test_parse_start_line() -> None:
    parsed = parse_line("Downloading item 333 ...")
    assert parsed is not None
    assert parsed.kind == "start"
    assert parsed.item_id == "333"


def test_parse_progress_line() -> None:
    parsed = parse_line("Update state (0x61) downloading, progress: 42.50")
    assert parsed is not None
    assert parsed.kind == "progress"
    assert parsed.percent == 42.5


def test_parse_bracket_percent_line() -> None:
    parsed = parse_line("[ 73%] downloading")
    assert parsed is not None
    assert parsed.kind == "progress"
    assert parsed.percent == 73.0


def test_decode_utf8() -> None:
    assert decode_steamcmd("Загрузка завершена".encode()) == "Загрузка завершена"


def test_decode_cp1251() -> None:
    raw = "Загрузка завершена".encode("cp1251")
    assert decode_steamcmd(raw) == "Загрузка завершена"


def test_decode_mojibake() -> None:
    mojibake = "Загрузка завершена".encode().decode("cp1251")
    assert decode_steamcmd(mojibake.encode()) == "Загрузка завершена"


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
