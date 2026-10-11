"""
GraphRouter's routing decisions (packages/graph/router.py) — pure
functions over GraphState/ExecutionPlan, so these run fast and
deterministic with no real LLM call and no graph execution, while
still genuinely exercising "does the graph route correctly for
representative inputs," the Phase 15 acceptance bar for LangGraph
Workflow Tests.
"""

from langchain_core.messages import AIMessage
from langgraph.graph import END

from packages.graph.router import GraphRouter
from packages.planner.models import Capability, ExecutionPlan, ExecutionStep

router = GraphRouter()


def _plan(*capabilities: Capability) -> ExecutionPlan:
    return ExecutionPlan(steps=[ExecutionStep(capability=c, reason="test") for c in capabilities])


def test_route_sends_retrieval_plan_to_researcher_when_planner_found_multiple_parts():
    """
    Multi-part classification (Multi-Agent, docs/mvpRAG.md v2.0) is
    decided by `planner` itself, in the same START fan-out as
    load_memory (packages/graph/builder.py, docs/BUGS.md item 63), not
    as a separate routing hop — by the time route() runs,
    state["is_multi_part"] is already set.
    """
    state = {"execution_plan": _plan(Capability.RETRIEVAL), "is_multi_part": True}

    assert router.route(state) == "researcher"


def test_route_sends_retrieval_plan_to_retrieve_when_not_multi_part():
    """
    The unchanged, existing single-question path — this is where a
    decomposition failure or a genuine "no" decision lands,
    byte-identical to the graph's behavior before Multi-Agent existed.
    """
    state = {"execution_plan": _plan(Capability.RETRIEVAL), "is_multi_part": False}

    assert router.route(state) == "retrieve"


def test_route_treats_missing_is_multi_part_key_as_non_multi_part():
    state = {"execution_plan": _plan(Capability.RETRIEVAL)}

    assert router.route(state) == "retrieve"


def test_route_sends_plain_llm_plan_to_llm_node():
    state = {"execution_plan": _plan(Capability.LLM)}

    assert router.route(state) == "llm"


def test_route_with_no_capabilities_falls_through_to_llm():
    state = {"execution_plan": _plan()}

    assert router.route(state) == "llm"


def test_route_prefers_retrieval_path_when_plan_has_both():
    state = {
        "execution_plan": _plan(Capability.MEMORY, Capability.RETRIEVAL, Capability.LLM),
        "is_multi_part": False,
    }

    assert router.route(state) == "retrieve"


def test_after_llm_routes_to_tool_when_the_last_message_has_tool_calls():
    message = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": "calculator", "args": {"expression": "2+2"}}],
    )
    state = {"messages": [message]}

    assert router.after_llm(state) == "tool"


def test_after_llm_ends_when_the_last_message_has_no_tool_calls():
    message = AIMessage(content="The answer is 4.")
    state = {"messages": [message]}

    assert router.after_llm(state) == END


def test_after_llm_ends_when_tool_calls_is_an_empty_list():
    message = AIMessage(content="Final answer.", tool_calls=[])
    state = {"messages": [message]}

    assert router.after_llm(state) == END


def test_after_llm_only_looks_at_the_most_recent_message():
    tool_call_message = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": "calculator", "args": {}}],
    )
    final_message = AIMessage(content="Done.")
    state = {"messages": [tool_call_message, final_message]}

    assert router.after_llm(state) == END
