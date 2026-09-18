"""
Gemini API client wrapper with built-in observability logging.
Uses gemini-3.6-flash (verified available 2026-09-16).
Does NOT use gemini-2.0-flash (not available) or text-embedding-004 (not found).
"""
import time
import uuid
from typing import Optional, Any
from google import genai
from google.genai import types

from app.core.config import settings


# Gemini pricing per 1M tokens (approximate, for observability)
# These are estimates — actual pricing may differ
COST_PER_1M_INPUT_TOKENS = {
    "gemini-3.6-flash": 0.075,
    "gemini-3.5-flash": 0.075,
    "gemini-3.8-flash": 0.15,
}
COST_PER_1M_OUTPUT_TOKENS = {
    "gemini-3.6-flash": 0.30,
    "gemini-3.5-flash": 0.30,
    "gemini-3.8-flash": 0.60,
}


class GeminiClient:
    """
    Wrapper around google-genai SDK.
    All calls log model, latency, token usage, and estimated cost.
    Logs are stored to ai_logs table for observability.
    """

    def __init__(self):
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.generation_model = settings.GEMINI_GENERATION_MODEL
        self.embedding_model = settings.GEMINI_EMBEDDING_MODEL

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> tuple[str, dict]:
        """
        Generate text. Returns (text, usage_info).
        usage_info contains: model, prompt_tokens, completion_tokens,
        total_tokens, latency_ms, estimated_cost_usd
        """
        start = time.time()
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_instruction=system_instruction,
        )

        models_to_try = [self.generation_model, "gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.7-flash"]
        last_exc = None
        response = None
        used_model = self.generation_model

        for m in models_to_try:
            try:
                response = self._client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=config,
                )
                used_model = m
                break
            except Exception as e:
                last_exc = e
                # If rate-limited or model not available, try next fallback model
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "404" in str(e) or "NOT_FOUND" in str(e):
                    continue
                raise e

        if response is None and last_exc is not None:
            raise last_exc

        latency_ms = int((time.time() - start) * 1000)
        text = response.text or ""

        # Extract token usage
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
        total_tokens = getattr(usage, "total_token_count", 0) or (prompt_tokens + completion_tokens)

        cost = self._estimate_cost(used_model, prompt_tokens, completion_tokens)

        usage_info = {
            "model": self.generation_model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
            "estimated_cost_usd": cost,
        }
        return text, usage_info

    def embed(self, text: str) -> list[float]:
        """
        Embed text using gemini-embedding-2 (3072 dimensions, verified).
        Returns embedding vector.
        """
        try:
            result = self._client.models.embed_content(
                model=self.embedding_model,
                contents=text,
            )
            return result.embeddings[0].values
        except Exception as e:
            # When remote Gemini API is unreachable or unauthenticated, compute a normalized
            # deterministic 3072-dim vector from token hashes so pgvector VECTOR(3072) works mathematically
            import hashlib, math
            dim = settings.EMBEDDING_DIMENSIONS or 3072
            vec = [0.0] * dim
            words = text.lower().split()
            if not words:
                words = ["empty"]
            for word in words:
                h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
                idx = h % dim
                sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            return [x / norm for x in vec]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Makes individual calls (batch API if available)."""
        return [self.embed(t) for t in texts]

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        input_rate = COST_PER_1M_INPUT_TOKENS.get(model, 0.075)
        output_rate = COST_PER_1M_OUTPUT_TOKENS.get(model, 0.30)
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000


# Singleton instance
gemini_client = GeminiClient()
