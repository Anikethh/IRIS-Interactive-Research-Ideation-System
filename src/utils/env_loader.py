import os
from pathlib import Path


def load_local_env(env_path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE pairs from a local .env file without overwriting env."""
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def configure_openai_compat() -> None:
    """Map local Azure AI OpenAI-compatible env vars to common OpenAI names."""
    azureai_key = os.environ.get("AZUREAI_OPENAI_API_KEY")
    azureai_base = os.environ.get("AZUREAI_OPENAI_BASE_URL")

    if azureai_key and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = azureai_key

    if azureai_base:
        os.environ.setdefault("OPENAI_BASE_URL", azureai_base)
        os.environ.setdefault("OPENAI_API_BASE", azureai_base)

    if os.environ.get("HF_TOKEN") and not os.environ.get("HF_API_TOKEN"):
        os.environ["HF_API_TOKEN"] = os.environ["HF_TOKEN"]
    if os.environ.get("HF_TOKEN") and not os.environ.get("HUGGINGFACE_API_KEY"):
        os.environ["HUGGINGFACE_API_KEY"] = os.environ["HF_TOKEN"]


def select_llm_model(config_model: str) -> str:
    """Prefer explicit local demo model settings, then GPT endpoint, then config."""
    override = (
        os.environ.get("IRIS_LLM_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or os.environ.get("AZUREAI_OPENAI_MODEL")
    )
    if override:
        return override

    if os.environ.get("AZUREAI_OPENAI_API_KEY") and os.environ.get("AZUREAI_OPENAI_BASE_URL"):
        return "gpt-5.4"

    return config_model
