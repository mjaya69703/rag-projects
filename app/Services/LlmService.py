"""LLM Service: multi-provider chat completion, retries, and streaming support."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_TEMPERATURE = 0.3
MAX_RETRIES = 2
RETRY_DELAYS = (1.0, 3.0)


class LLMError(RuntimeError):
    """Exception raised when LLM API call fails."""


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict | None = None


def _is_retryable_status(status_code: int) -> bool:
    return status_code in (429, 500, 502, 503, 504)


def _is_retryable_message(message: str) -> bool:
    m = message.lower()
    return any(
        k in m for k in ("internal_error", "overloaded", "rate limit", "temporarily", "try again")
    )


class LlmService:
    """Service handling interactions with LLM models (OpenAI, Groq, Anthropic, OpenRouter, Ollama)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        temperature: float = DEFAULT_TEMPERATURE,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        provider = os.getenv("LLM_PROVIDER", "").lower()
        if provider == "anthropic":
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY", "")
            self.base_url = (base_url or os.getenv("LLM_API_BASE") or "https://api.anthropic.com/v1").rstrip("/")
            self.model = model or os.getenv("LLM_MODEL") or "claude-3-5-sonnet-20241022"
        elif provider == "groq":
            self.api_key = api_key or os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY", "")
            self.base_url = (base_url or os.getenv("LLM_API_BASE") or "https://api.groq.com/openai/v1").rstrip("/")
            self.model = model or os.getenv("LLM_MODEL") or "llama-3.3-70b-versatile"
        elif provider == "openrouter":
            self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY", "")
            self.base_url = (base_url or os.getenv("LLM_API_BASE") or "https://openrouter.ai/api/v1").rstrip("/")
            self.model = model or os.getenv("LLM_MODEL") or "anthropic/claude-3.5-sonnet"
        elif provider == "ollama":
            self.api_key = api_key or os.getenv("LLM_API_KEY") or "ollama"
            self.base_url = (base_url or os.getenv("LLM_API_BASE") or "http://localhost:11434/v1").rstrip("/")
            self.model = model or os.getenv("LLM_MODEL") or "llama3.2"
        else:
            self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
            self.base_url = (base_url or os.getenv("LLM_API_BASE") or DEFAULT_BASE_URL).rstrip("/")
            self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

        self.timeout = timeout
        self.temperature = temperature
        self._transport = transport
        self.is_anthropic = "anthropic.com" in self.base_url or provider == "anthropic"

    def _validate(self) -> None:
        if not self.api_key:
            raise LLMError("API Key belum diisi di file .env (isi OPENAI_API_KEY / GROQ_API_KEY / ANTHROPIC_API_KEY / LLM_API_KEY)")
        if not self.model:
            raise LLMError("LLM_MODEL belum diisi di file .env")

    def _headers(self) -> dict:
        if self.is_anthropic:
            return {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _format_messages_for_anthropic(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        system_prompt = None
        user_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                user_messages.append({"role": msg.get("role"), "content": msg.get("content", "")})
        return system_prompt, user_messages

    def _payload(self, messages: list[dict], max_tokens: int, stream: bool = False) -> dict:
        if self.is_anthropic:
            system_prompt, formatted_msgs = self._format_messages_for_anthropic(messages)
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": formatted_msgs,
                "max_tokens": max_tokens,
                "temperature": self.temperature,
            }
            if system_prompt:
                payload["system"] = system_prompt
            if stream:
                payload["stream"] = True
            return payload

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        if stream:
            payload["stream"] = True
        return payload

    def _extract_error(self, data: dict) -> str | None:
        err = data.get("error") if isinstance(data, dict) else None
        if err is None:
            return None
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)

    def chat(self, messages: list[dict], max_tokens: int = 1024) -> LLMResponse:
        self._validate()
        url = f"{self.base_url}/messages" if self.is_anthropic else f"{self.base_url}/chat/completions"
        payload = self._payload(messages, max_tokens)
        headers = self._headers()

        last_error: LLMError | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                client_kwargs = {"timeout": self.timeout}
                if self._transport is not None:
                    client_kwargs["transport"] = self._transport
                with httpx.Client(**client_kwargs) as client:
                    start = time.perf_counter()
                    response = client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                last_error = LLMError(f"Timeout memanggil LLM API ({self.timeout}s)")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
                raise last_error from exc
            except httpx.HTTPError as exc:
                last_error = LLMError(f"Gagal terhubung ke LLM API: {exc}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
                raise last_error from exc

            if response.status_code >= 400:
                last_error = LLMError(
                    f"LLM API error {response.status_code}: {response.text[:300]}"
                )
                if _is_retryable_status(response.status_code) and attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
                raise last_error

            try:
                data = response.json()
            except ValueError:
                raise LLMError(f"Response LLM bukan JSON: {response.text[:300]}") from None

            error_msg = self._extract_error(data)
            if error_msg:
                last_error = LLMError(f"LLM API error: {error_msg}")
                if _is_retryable_message(error_msg) and attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
                raise last_error

            if self.is_anthropic:
                try:
                    text = "".join(block["text"] for block in data.get("content", []) if block.get("type") == "text").strip()
                except Exception as exc:
                    raise LLMError(f"Response Anthropic tidak sesuai format: {str(data)[:300]}") from exc
                usage = data.get("usage") or {}
                return LLMResponse(text=text, model=data.get("model", self.model), usage=usage)

            try:
                text = data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMError(f"Response LLM tidak sesuai format: {str(data)[:300]}") from exc

            usage = data.get("usage") or {}
            logger.info(
                "LLM call model=%s duration_ms=%.0f prompt_tokens=%s completion_tokens=%s",
                self.model,
                (time.perf_counter() - start) * 1000,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
            return LLMResponse(
                text=text,
                model=data.get("model", self.model),
                usage=usage,
            )

        raise last_error

    async def astream_chat(
        self, messages: list[dict], max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        self._validate()
        url = f"{self.base_url}/messages" if self.is_anthropic else f"{self.base_url}/chat/completions"
        payload = self._payload(messages, max_tokens, stream=True)
        headers = self._headers()

        for attempt in range(MAX_RETRIES + 1):
            last_error: LLMError | None = None
            started = False
            try:
                client_kwargs = {"timeout": self.timeout}
                if self._transport is not None:
                    client_kwargs["transport"] = self._transport
                async with httpx.AsyncClient(**client_kwargs) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code >= 400:
                            body = await response.aread()
                            last_error = LLMError(
                                f"LLM streaming error {response.status_code}: {body.decode('utf-8', 'replace')[:300]}"
                            )
                            if _is_retryable_status(response.status_code) and attempt < MAX_RETRIES:
                                await asyncio.sleep(RETRY_DELAYS[attempt])
                                continue
                            raise last_error

                        async for raw_line in response.aiter_lines():
                            line = raw_line.strip()
                            if not line or line.startswith(":"):
                                continue

                            if self.is_anthropic:
                                if line.startswith("data:"):
                                    data_str = line[5:].strip()
                                    try:
                                        data = json.loads(data_str)
                                        if data.get("type") == "content_block_delta":
                                            delta_text = data.get("delta", {}).get("text", "")
                                            if delta_text:
                                                started = True
                                                yield delta_text
                                    except ValueError:
                                        continue
                                continue

                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str == "[DONE]":
                                    return
                                try:
                                    data = json.loads(data_str)
                                except ValueError:
                                    continue

                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    started = True
                                    yield content
                        return
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                if started:
                    raise LLMError(f"Koneksi terputus saat streaming: {exc}") from exc
                last_error = LLMError(f"Gagal streaming LLM: {exc}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                raise last_error from exc
