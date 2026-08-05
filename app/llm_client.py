"""LLM Client: panggil API chat completion OpenAI-compatible via httpx.

Konfigurasi dari environment (file .env):
- LLM_API_KEY  : API key
- LLM_API_BASE : base URL, default https://api.openai.com/v1
- LLM_MODEL    : nama model (mis. deepseek-chat, gpt-4o-mini)

Contoh .env:
    LLM_API_KEY=sk-xxxx
    LLM_API_BASE=https://api.deepseek.com/v1
    LLM_MODEL=deepseek-chat
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_TEMPERATURE = 0.3

# Retry untuk error transient dari LLM API (internal_error/5xx/429/network).
MAX_RETRIES = 2
RETRY_DELAYS = (1.0, 3.0)


class LLMError(RuntimeError):
    """Error saat memanggil LLM API (auth, timeout, rate limit, format)."""


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


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        temperature: float = DEFAULT_TEMPERATURE,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.base_url = (base_url or os.getenv("LLM_API_BASE") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.getenv("LLM_MODEL", "")
        self.timeout = timeout
        self.temperature = temperature
        # transport hanya untuk test (httpx.MockTransport)
        self._transport = transport

    # ------------------------------------------------------------------
    def _validate(self) -> None:
        if not self.api_key:
            raise LLMError("LLM_API_KEY belum diisi di file .env")
        if not self.model:
            raise LLMError("LLM_MODEL belum diisi di file .env")

    def _payload(self, messages: list[dict], max_tokens: int, stream: bool = False) -> dict:
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
        """Ambil pesan error dari body respons yang bukan berbentuk chat."""
        err = data.get("error") if isinstance(data, dict) else None
        if err is None:
            return None
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)

    def chat(self, messages: list[dict], max_tokens: int = 1024) -> LLMResponse:
        """Kirim percakapan ke LLM API, kembalikan respons teks lengkap.

        Retry otomatis (maks MAX_RETRIES kali) untuk error transient
        (429/5xx/network/internal_error) supaya API yang flaky tidak
        menggagalkan permintaan.
        """
        self._validate()
        url = f"{self.base_url}/chat/completions"
        payload = self._payload(messages, max_tokens)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: LLMError | None = None
        for attempt in range(MAX_RETRIES + 1):
            # 1. Network / timeout
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

            # 2. HTTP status code
            if response.status_code >= 400:
                last_error = LLMError(
                    f"LLM API error {response.status_code}: {response.text[:300]}"
                )
                if _is_retryable_status(response.status_code) and attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
                raise last_error

            # 3. Body (beberapa provider mengembalikan HTTP 200 + {"error": ...})
            try:
                data = response.json()
            except ValueError:
                raise LLMError(
                    f"Response LLM bukan JSON: {response.text[:300]}"
                ) from None
            error_msg = self._extract_error(data)
            if error_msg:
                last_error = LLMError(f"LLM API error: {error_msg}")
                if _is_retryable_message(error_msg) and attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
                raise last_error

            # 4. Parse jawaban
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

        raise last_error  # pragma: no cover - unreachable (loop selalu raise)

    async def astream_chat(
        self, messages: list[dict], max_tokens: int = 1024
    ):
        """Streaming jawaban LLM: async generator yang me-yield teks per chunk.

        Retry hanya dilakukan jika error terjadi SEBELUM delta pertama keluar
        (kalau sudah ada delta, respons dianggap mulai valid dan tidak
        diulang supaya jawaban tidak ter-duplikasi).
        """
        self._validate()
        url = f"{self.base_url}/chat/completions"
        payload = self._payload(messages, max_tokens, stream=True)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(MAX_RETRIES + 1):
            last_error: LLMError | None = None
            started = False
            try:
                client_kwargs = {"timeout": self.timeout}
                if self._transport is not None:
                    client_kwargs["transport"] = self._transport
                async with httpx.AsyncClient(**client_kwargs) as client:
                    async with client.stream(
                        "POST", url, json=payload, headers=headers
                    ) as response:
                        if response.status_code >= 400:
                            body = (await response.aread()).decode("utf-8", "replace")
                            last_error = LLMError(
                                f"LLM API error {response.status_code}: {body[:300]}"
                            )
                        else:
                            async for line in response.aiter_lines():
                                if not line.startswith("data:"):
                                    continue
                                chunk = line[5:].strip()
                                if chunk == "[DONE]":
                                    break
                                try:
                                    obj = json.loads(chunk)
                                except json.JSONDecodeError:
                                    continue
                                error_msg = self._extract_error(obj)
                                if error_msg:
                                    last_error = LLMError(f"LLM API error: {error_msg}")
                                    break
                                choices = obj.get("choices") or []
                                if not choices:
                                    continue
                                delta = (choices[0].get("delta") or {}).get("content")
                                if delta:
                                    started = True
                                    yield delta
            except httpx.TimeoutException as exc:
                last_error = LLMError(f"Timeout memanggil LLM API ({self.timeout}s)")
                if started and attempt >= MAX_RETRIES:
                    raise last_error from exc
            except httpx.HTTPError as exc:
                last_error = LLMError(f"Gagal terhubung ke LLM API: {exc}")

            # Retry hanya jika belum ada delta yang terkirim
            if last_error is not None and not started and attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAYS[attempt])
                continue
            if last_error is not None:
                raise last_error
            return
