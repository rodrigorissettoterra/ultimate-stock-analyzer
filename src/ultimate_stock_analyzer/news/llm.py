from __future__ import annotations

from dataclasses import dataclass
from json import loads

import httpx

from ultimate_stock_analyzer.domain.models import NewsSignal

_SYSTEM_PROMPT = """You are a conservative financial event classifier for Brazilian listed companies.
Return ONLY valid JSON. Use only facts present in the supplied text and metadata. Do not invent facts.
If evidence is weak or ambiguous, reduce confidence. Classify material relevance to the company or
investment thesis. impact must be between -1 and 1; severity is integer 1..5; confidence is 0..1.
Required JSON keys: ticker, relevant, event_type, impact, severity, confidence, rationale.
The binary relevant field decides whether the event enters the news score. impact controls direction.
Do not calculate stock scores, target prices or recommendations. Do not infer missing financial data.
"""


@dataclass(slots=True)
class OpenAICompatibleNewsClassifier:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 30.0

    def classify(
        self,
        ticker: str,
        headline: str,
        text: str,
        source_url: str | None = None,
        source_name: str | None = None,
    ) -> NewsSignal:
        if not self.api_key or not self.model:
            raise ValueError("LLM api_key and model are required")
        source_label = source_name or "unknown"
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Ticker: {ticker}\nSource: {source_label}\nHeadline: {headline}\n"
                        f"Source URL: {source_url or 'unknown'}\nText:\n{text[:12000]}"
                    ),
                },
            ],
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        parsed = loads(content)
        parsed["ticker"] = ticker
        parsed["source_url"] = source_url
        return NewsSignal.model_validate(parsed)
