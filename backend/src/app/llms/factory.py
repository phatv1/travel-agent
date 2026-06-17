import os
from typing import Literal, cast

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

ThinkingLevel = Literal["off", "auto", "on", "low", "medium", "high"]


def get_llm(
    temperature: float | None = None,
    thinking: ThinkingLevel | None = None,
) -> ChatOllama:
    if temperature is None:
        temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))

    if thinking is None:
        thinking = cast(ThinkingLevel, os.getenv("OLLAMA_THINKING", "off"))

    model = os.getenv("OLLAMA_MODEL", "gemma4:12b-it-qat")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    kwargs = {}

    if thinking == "off":
        kwargs["reasoning"] = False
    elif thinking == "on":
        kwargs["reasoning"] = True
    elif thinking in {"low", "medium", "high"}:
        kwargs["reasoning"] = thinking

    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature,
        **kwargs,
    )
