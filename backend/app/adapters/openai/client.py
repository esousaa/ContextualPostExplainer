from openai import AsyncOpenAI
from pydantic import SecretStr


def build_openai_client(api_key: SecretStr) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key.get_secret_value())
