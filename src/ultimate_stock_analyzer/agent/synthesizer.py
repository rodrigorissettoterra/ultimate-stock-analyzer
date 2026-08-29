from __future__ import annotations

from dataclasses import dataclass
from json import dumps
from typing import Protocol

import httpx

from ultimate_stock_analyzer.agent.models import AgentContext, AgentIntent


class AgentSynthesizer(Protocol):
    uses_llm: bool

    def synthesize(self, question: str, context: AgentContext) -> str: ...


@dataclass(slots=True)
class DeterministicAgentSynthesizer:
    uses_llm: bool = False

    def synthesize(self, question: str, context: AgentContext) -> str:
        del question
        if context.intent == AgentIntent.STOCK_ANALYSIS:
            stocks = context.payload.get("stocks", [])
            missing = context.payload.get("missing_tickers", [])
            if not stocks:
                target = ", ".join(missing) or "o ativo solicitado"
                return f"Não há análise publicada suficiente para {target}."
            row = stocks[0]
            scores = row["scores"]
            return (
                f"{row['ticker']} ({row['company_name']}): qualidade {scores['company_quality']:.1f}/100, "
                f"atratividade {scores['investment_attractiveness']:.1f}/100, entrada "
                f"{scores['entry_timing']:.1f}/100 e confiança {scores['data_confidence']:.1f}/100. "
                f"Status: {scores['status']}. O momento de entrada é separado da atratividade do investimento."
            )
        if context.intent == AgentIntent.COMPARE:
            stocks = context.payload.get("stocks", [])
            if not stocks:
                return "Não há análises publicadas suficientes para realizar a comparação."
            lines = []
            for row in stocks:
                scores = row["scores"]
                lines.append(
                    f"{row['ticker']}: atratividade {scores['investment_attractiveness']:.1f}, "
                    f"qualidade {scores['company_quality']:.1f}, entrada {scores['entry_timing']:.1f}, "
                    f"confiança {scores['data_confidence']:.1f}, status {scores['status']}"
                )
            return "Comparação baseada nos scores publicados: " + "; ".join(lines) + "."
        if context.intent == AgentIntent.RANKING:
            rows = context.payload.get("ranking", [])
            if not rows:
                return "Ainda não há análises ranqueáveis publicadas."
            parts = [
                f"{row['rank']}º {row['ticker']} ({row['investment_attractiveness']:.1f}/100)"
                for row in rows
            ]
            return "Ranking atual por atratividade do investimento: " + "; ".join(parts) + "."
        if context.intent == AgentIntent.BACKTEST:
            rows = context.payload.get("backtests", [])
            if not rows:
                return "Ainda não há resultados de backtest publicados."
            row = rows[0]
            return (
                f"Backtest {row['backtest_id']} ({row['start_date']} a {row['end_date']}): "
                f"CAGR {row['cagr']:.2%}, benchmark {row['benchmark_cagr']:.2%}, "
                f"drawdown máximo {row['max_drawdown']:.2%}."
            )
        return (
            "Não consegui determinar com segurança a intenção. Informe um ticker, compare dois "
            "tickers, peça o ranking ou pergunte pelos backtests."
        )


_SYSTEM_PROMPT = """You are the explanation layer of an auditable Brazilian equity research system.
Use ONLY the supplied context. Never change, recalculate or invent a financial score, price, date,
status, source or ranking. Do not issue imperative buy/sell recommendations. Clearly distinguish
Company Quality, Investment Attractiveness and Entry Timing. When evidence is missing, say so.
Answer in Brazilian Portuguese, concise but explanatory. Source references may be mentioned by
source name; do not fabricate URLs. The output must be plain text only.
"""


@dataclass(slots=True)
class OpenAICompatibleAgentSynthesizer:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 30.0
    uses_llm: bool = True

    def synthesize(self, question: str, context: AgentContext) -> str:
        if not self.api_key or not self.model:
            raise ValueError("LLM api_key and model are required")
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question[:2000]}\n\nVerified context:\n"
                        f"{dumps(context.payload, ensure_ascii=False)[:30000]}"
                    ),
                },
            ],
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM returned an empty answer")
        return content.strip()
