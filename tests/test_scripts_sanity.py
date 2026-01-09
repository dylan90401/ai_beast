from pathlib import Path


def test_shell_scripts_have_shebang_if_executable():
    root = Path("scripts")
    assert root.exists()
    for path in root.rglob("*.sh"):
        mode = path.stat().st_mode
        if mode & 0o111:
            first = path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
            assert first and first[0].startswith("#!"), f"Missing shebang: {path}"


def test_shell_scripts_no_crlf():
    root = Path("scripts")
    assert root.exists()
    for path in root.rglob("*.sh"):
        data = path.read_bytes()
        assert b"\r\n" not in data, f"CRLF detected: {path}"
