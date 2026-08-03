"""
packages/graph/state.py's merge_usage reducer — the exact mechanism
behind a real production regression (see docs/BUILD_STATUS.md's Token
Usage entry): update=None must reset to {} unconditionally, since
LangGraph's checkpointer persists `usage` across every invoke()/resume()
against the same thread_id, not just within one turn.
"""

from packages.graph.state import merge_usage


def test_first_call_with_no_prior_state():
    assert merge_usage(None, {"input_tokens": 10, "output_tokens": 5}) == {
        "input_tokens": 10,
        "output_tokens": 5,
    }


def test_accumulates_numeric_fields_across_calls_in_one_turn():
    current = {"input_tokens": 100, "output_tokens": 20}
    update = {"input_tokens": 50, "output_tokens": 10}

    merged = merge_usage(current, update)

    assert merged == {"input_tokens": 150, "output_tokens": 30}


def test_non_numeric_fields_take_the_latest_value_not_summed():
    current = {"input_tokens": 100, "input_token_details": {"cache_read": 10}}
    update = {"input_tokens": 50, "input_token_details": {"cache_read": 25}}

    merged = merge_usage(current, update)

    assert merged["input_tokens"] == 150
    assert merged["input_token_details"] == {"cache_read": 25}


def test_key_missing_from_update_keeps_current_value():
    current = {"input_tokens": 100, "output_tokens": 20}
    update = {"input_tokens": 50}

    merged = merge_usage(current, update)

    assert merged == {"input_tokens": 150, "output_tokens": 20}


def test_update_none_resets_unconditionally_even_against_poisoned_state():
    """
    The actual regression: update={} would merge as a no-op against
    whatever's already checkpointed (every key still comes from
    `current` since `update` contributes nothing), so a conversation's
    usage would accumulate forever across its entire lifetime instead
    of resetting per turn. update=None is the real reset signal
    packages/application/services/chat_service.py's _build_state()
    relies on at the start of every new turn.
    """
    poisoned_current = {"input_tokens": 2_400_000_000, "output_tokens": 900_000_000}

    assert merge_usage(poisoned_current, None) == {}


def test_empty_dict_update_is_not_a_reset_it_is_a_no_op_merge():
    """
    Documents the exact footgun the regression fix distinguishes
    against: {} is a legitimate "no new usage this call" update, not a
    reset, so it must still merge (not clear) against current state.
    """
    current = {"input_tokens": 100}

    assert merge_usage(current, {}) == {"input_tokens": 100}


def test_no_prior_state_and_no_update_returns_empty_dict():
    assert merge_usage(None, {}) == {}
