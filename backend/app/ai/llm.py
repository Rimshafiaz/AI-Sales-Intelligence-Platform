from crewai import LLM

from app.core.config import settings


_DEFAULT_MAX_TOKENS = 4096


def get_llm(
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLM:
    effective_max_tokens = max_tokens if max_tokens is not None else _DEFAULT_MAX_TOKENS

    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise ValueError(
                "Groq is selected but GROQ_API_KEY is not configured."
            )

        return LLM(
            model=f"groq/{settings.groq_model}",
            api_key=settings.groq_api_key,
            temperature=0.2 if temperature is None else temperature,
            max_tokens=effective_max_tokens,
        )

    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "Gemini is selected but GEMINI_API_KEY is not configured."
            )

        llm_kwargs = {
            "model": f"gemini/{settings.gemini_model}",
            "api_key": settings.gemini_api_key,
            "max_tokens": effective_max_tokens,
        }
        if temperature is not None:
            llm_kwargs["temperature"] = temperature

        return LLM(**llm_kwargs)

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
