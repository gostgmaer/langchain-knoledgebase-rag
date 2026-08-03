from decimal import Decimal

from packages.config.pricing import compute_cost


def test_known_model_computes_correct_cost():
    # gemini-3.1-flash-lite: $0.10/1M input, $0.40/1M output
    cost = compute_cost("google", "gemini-3.1-flash-lite", 5190, 27)

    expected = (Decimal(5190) * Decimal("0.10") + Decimal(27) * Decimal("0.40")) / Decimal("1000000")
    assert cost == expected.quantize(Decimal("0.000001"))


def test_provider_and_model_matching_is_case_insensitive():
    mixed_case = compute_cost("Google", "Gemini-3.1-Flash-Lite", 1000, 1000)
    lower_case = compute_cost("google", "gemini-3.1-flash-lite", 1000, 1000)

    assert mixed_case == lower_case
    assert mixed_case > 0


def test_unknown_model_costs_zero_not_a_crash():
    assert compute_cost("some-new-provider", "some-new-model", 1000, 1000) == Decimal("0")


def test_missing_provider_or_model_costs_zero():
    assert compute_cost(None, "gemini-3.1-flash-lite", 1000, 1000) == Decimal("0")
    assert compute_cost("google", None, 1000, 1000) == Decimal("0")
    assert compute_cost("", "", 1000, 1000) == Decimal("0")


def test_zero_tokens_costs_zero():
    assert compute_cost("google", "gemini-3.1-flash-lite", 0, 0) == Decimal("0")
