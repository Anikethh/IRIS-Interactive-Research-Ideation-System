import os
from types import SimpleNamespace
from typing import Any, Dict, List

import litellm
from openai import OpenAI

from src.utils.env_loader import configure_openai_compat, load_local_env


load_local_env()
configure_openai_compat()


def _message_content(message: Dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    return str(content)


def _should_use_responses_api(model: str) -> bool:
    if os.environ.get("IRIS_USE_RESPONSES_API", "").lower() in {"1", "true", "yes"}:
        return True
    if os.environ.get("IRIS_USE_RESPONSES_API", "").lower() in {"0", "false", "no"}:
        return False
    return bool(os.environ.get("AZUREAI_OPENAI_API_KEY") and model.startswith("gpt-5"))


def _responses_completion(messages: List[Dict[str, str]], model: str, **kwargs):
    client = OpenAI(
        api_key=os.environ["AZUREAI_OPENAI_API_KEY"],
        base_url=os.environ["AZUREAI_OPENAI_BASE_URL"],
    )

    instructions = "\n\n".join(
        _message_content(message)
        for message in messages
        if message.get("role") == "system"
    ) or None
    if kwargs.get("response_format"):
        json_instruction = "Return only valid JSON. Do not wrap it in Markdown fences."
        instructions = f"{instructions}\n\n{json_instruction}" if instructions else json_instruction
    user_input = "\n\n".join(
        f"{message.get('role', 'user').upper()}: {_message_content(message)}"
        for message in messages
        if message.get("role") != "system"
    )

    response_kwargs: Dict[str, Any] = {}
    if kwargs.get("max_tokens"):
        response_kwargs["max_output_tokens"] = max(int(kwargs["max_tokens"]), 512)

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=user_input,
        **response_kwargs,
    )

    usage = response.usage
    prompt_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "output_tokens", 0) if usage else 0
    total_tokens = getattr(usage, "total_tokens", prompt_tokens + completion_tokens) if usage else 0

    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=(response.output_text or "").strip())
            )
        ],
        model=getattr(response, "model", model),
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
    )


def completion(messages: List[Dict[str, str]], model: str, **kwargs):
    """Completion helper that supports the local Azure AI Responses API setup."""
    if _should_use_responses_api(model):
        return _responses_completion(messages=messages, model=model, **kwargs)
    return litellm.completion(messages=messages, model=model, **kwargs)
