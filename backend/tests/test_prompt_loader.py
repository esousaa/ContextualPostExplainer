import pytest

from app.adapters.openai.prompt_loader import load_prompt


def test_prompt_loader_reads_central_prompt_config() -> None:
    prompt = load_prompt("query_decomposition")

    assert "Return 2 to 4 distinct queries" in prompt


def test_prompt_loader_rejects_missing_prompt_key() -> None:
    with pytest.raises(KeyError):
        load_prompt("missing_prompt")
