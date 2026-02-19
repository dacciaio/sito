"""Wrapper around the Anthropic Claude SDK."""

from __future__ import annotations

from typing import Generator

from anthropic import APIStatusError, Anthropic, AuthenticationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from daccia.config import Settings


def _is_retryable(exc: BaseException) -> bool:
    """Return True only for transient API errors (rate-limits, server errors).

    Authentication errors (401) and bad-request errors (400) should NOT be
    retried — they will never succeed without a config change.
    """
    if isinstance(exc, AuthenticationError):
        return False
    if isinstance(exc, APIStatusError) and exc.status_code < 500:
        # 4xx errors other than 429 (rate limit) are not retryable
        return exc.status_code == 429
    return True


class ClaudeClient:
    """Thin wrapper providing retry logic and token tracking."""

    def __init__(self, settings: Settings) -> None:
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model
        self._max_tokens = settings.max_tokens
        self._temperature = settings.temperature
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def generate(
        self,
        system: str,
        messages: list[dict],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send a message to Claude and return the text response."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens or self._max_tokens,
            temperature=temperature if temperature is not None else self._temperature,
            system=system,
            messages=messages,
        )
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        return response.content[0].text

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def generate_streaming(
        self,
        system: str,
        messages: list[dict],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        """Stream a response from Claude, yielding text chunks."""
        with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens or self._max_tokens,
            temperature=temperature if temperature is not None else self._temperature,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    @property
    def usage_summary(self) -> dict:
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
        }
