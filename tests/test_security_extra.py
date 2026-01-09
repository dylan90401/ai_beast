import os


def test_validate_file_permissions(tmp_path):
    from modules.security import validate_file_permissions

    target = tmp_path / "secret.txt"
    target.write_text("secret", encoding="utf-8")

    result = validate_file_permissions(target)
    assert result["valid"] is False

    os.chmod(target, 0o600)
    result = validate_file_permissions(target)
    assert result["valid"] is True


def test_verify_file_hash_missing(tmp_path):
    from modules.security import verify_file_hash

    missing = tmp_path / "missing.txt"
    assert verify_file_hash(missing, "deadbeef") is False
