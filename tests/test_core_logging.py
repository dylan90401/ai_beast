from modules.core.logging import get_logger


def test_get_logger():
    logger = get_logger("ai_beast_test")
    assert logger is not None
