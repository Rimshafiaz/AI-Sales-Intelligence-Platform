import logging
from typing import Any

from crewai import LLM
from crewai.llms.providers.gemini.completion import GeminiCompletion
from google.genai import types

from app.core.config import settings


_DEFAULT_MAX_TOKENS = 4096


class SalesLensGeminiCompletion(GeminiCompletion):
    """Adapt CrewAI's text tool loop to Gemini's final wire format."""

    def _prepare_generation_config(self, *args: Any, **kwargs: Any) -> Any:
        config = super()._prepare_generation_config(*args, **kwargs)
        return config.model_copy(
            update={
                "automatic_function_calling": types.AutomaticFunctionCallingConfig(
                    disable=True
                )
            }
        )

    def _handle_completion(
        self, contents: list[types.Content], *args: Any, **kwargs: Any
    ) -> Any:
        normalized = list(contents)
        if normalized and normalized[-1].role == "model":
            normalized.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="Continue using the tool result above.")],
                )
            )
        logging.getLogger(__name__).debug(
            "Gemini request role sequence: %s", [item.role for item in normalized]
        )
        return super()._handle_completion(normalized, *args, **kwargs)


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
            timeout=180,
            num_retries=1,
        )

    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "Gemini is selected but GEMINI_API_KEY is not configured."
            )

        llm_kwargs = {
            "model": settings.gemini_model,
            "api_key": settings.gemini_api_key,
            "max_output_tokens": effective_max_tokens,
            "num_retries": 1,
            "timeout": 180,
        }
        if temperature is not None:
            llm_kwargs["temperature"] = temperature

        return SalesLensGeminiCompletion(**llm_kwargs)

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
