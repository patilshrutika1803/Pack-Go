from pathlib import Path

import yaml


CONFIG_PATH = Path("config/config.yaml")


def test_active_configuration_matches_current_runtime_models():
    rendered = CONFIG_PATH.read_text(encoding="utf-8")
    config = yaml.safe_load(rendered)

    assert "llama-3.3-70b-versatile" not in rendered
    assert "gemini-2.0-flash" not in rendered
    assert "o4-mini" not in rendered

    groq_cfg = config.get("llm", {}).get("groq", {})
    gemini_cfg = config.get("llm", {}).get("gemini", {})

    assert groq_cfg.get("provider") == "groq"
    assert groq_cfg.get("model_name") == "openai/gpt-oss-120b"

    assert gemini_cfg.get("provider") == "google_genai"
    assert gemini_cfg.get("model_name") == "gemini-3.5-flash"

    assert "api_key" not in rendered.lower()
    assert "GROQ_API_KEY" not in rendered
    assert "GOOGLE_API_KEY" not in rendered
