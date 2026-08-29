from crewai import LLM

from app.core.config import settings


def get_llm(
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLM:
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise ValueError(
                "Groq is selected but GROQ_API_KEY is not configured."
            )

        llm_kwargs = {
            "model": f"groq/{settings.groq_model}",
            "api_key": settings.groq_api_key,
            "temperature": 0.2 if temperature is None else temperature,
        }
        if max_tokens is not None:
            llm_kwargs["max_tokens"] = max_tokens

        return LLM(**llm_kwargs)

    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "Gemini is selected but GEMINI_API_KEY is not configured."
            )

        llm_kwargs = {
            "model": f"gemini/{settings.gemini_model}",
            "api_key": settings.gemini_api_key,
        }
        if temperature is not None:
            llm_kwargs["temperature"] = temperature
        if max_tokens is not None:
            llm_kwargs["max_tokens"] = max_tokens

        return LLM(**llm_kwargs)

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
