import tomllib
from functools import lru_cache
from pathlib import Path

PROMPT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "prompts" / "prompts.toml"


@lru_cache
def load_prompt(name: str) -> str:
    prompts = _load_prompt_config()
    try:
        prompt = prompts[name]
    except KeyError as exc:
        raise KeyError(f"Prompt is not configured: {name}") from exc
    return prompt.strip()


@lru_cache
def _load_prompt_config() -> dict[str, str]:
    with PROMPT_CONFIG_PATH.open("rb") as file:
        payload = tomllib.load(file)

    prompts = payload.get("prompts")
    if not isinstance(prompts, dict):
        raise ValueError("Prompt config must contain a [prompts] table.")

    return {key: value for key, value in prompts.items() if isinstance(value, str)}
