import re

from hypothesis import given
from hypothesis import strategies as st

from modules.llm.manager import _extract_quant, _human_size


@given(st.text(min_size=1, max_size=50))
def test_extract_quant_no_crash(name: str):
    result = _extract_quant(name)
    assert isinstance(result, str)


@given(st.integers(min_value=0, max_value=10**9))
def test_human_size_format(size: int):
    result = _human_size(size)
    assert re.search(r"[0-9]+\.[0-9] [A-Z]{1,2}", result)
