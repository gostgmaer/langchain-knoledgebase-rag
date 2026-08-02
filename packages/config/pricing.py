from __future__ import annotations

from decimal import Decimal

from packages.shared.logging import get_logger

logger = get_logger(__name__)

# $ per 1,000,000 tokens. Keyed on the LOWERCASE (provider, model)
# strings this app actually stores on Message/AIResponse/Agent
# (packages/config/ai.py's AISettings.default_provider/.model,
# packages/conversation/bootstrap.py) — NOT the differently-cased
# ModelProvider enum used elsewhere only for ModelProfile.provider.
#
# Prices are illustrative public list prices for the models this
# project's providers actually support, current as of when this table
# was written — not fetched live from anywhere. An unknown (provider,
# model) pair costs $0 with a logged warning rather than crashing a
# chat turn over a pricing gap.
_PRICING_PER_1M_TOKENS: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
    # provider, model -> (input $/1M, output $/1M)
    ("google", "gemini-3.1-flash-lite"): (Decimal("0.10"), Decimal("0.40")),
    ("google", "gemini-2.5-flash"): (Decimal("0.30"), Decimal("2.50")),
    ("google", "gemini-2.5-pro"): (Decimal("1.25"), Decimal("10.00")),
    ("openai", "gpt-4o"): (Decimal("2.50"), Decimal("10.00")),
    ("openai", "gpt-4o-mini"): (Decimal("0.15"), Decimal("0.60")),
    ("anthropic", "claude-sonnet-5"): (Decimal("3.00"), Decimal("15.00")),
    ("anthropic", "claude-haiku-4-5-20251001"): (Decimal("0.80"), Decimal("4.00")),
    ("groq", "llama-3.3-70b-versatile"): (Decimal("0.59"), Decimal("0.79")),
}

_UNKNOWN_LOGGED: set[tuple[str, str]] = set()


def compute_cost(
    provider: str | None,
    model: str | None,
    prompt_tokens: int,
    completion_tokens: int,
) -> Decimal:
    if not provider or not model:
        return Decimal("0")

    key = (provider.strip().lower(), model.strip().lower())
    prices = _PRICING_PER_1M_TOKENS.get(key)

    if prices is None:
        if key not in _UNKNOWN_LOGGED:
            logger.warning("No pricing entry for model, cost will be $0", provider=key[0], model=key[1])
            _UNKNOWN_LOGGED.add(key)
        return Decimal("0")

    input_price, output_price = prices

    cost = (Decimal(prompt_tokens) * input_price + Decimal(completion_tokens) * output_price) / Decimal("1000000")

    return cost.quantize(Decimal("0.000001"))
