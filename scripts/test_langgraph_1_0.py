"""LangGraph 1.0+ core functionality verification script

Verifies:
1. MemorySaver (formerly InMemorySaver) works correctly
2. interrupt / Command(resume=...) HITL mechanism
3. StateGraph compilation and execution
4. checkpoint persistence
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from typing_extensions import TypedDict


# === Test 1: MemorySaver (formerly InMemorySaver) ===
def test_memory_saver():
    """Verify MemorySaver works correctly"""
    print("\n=== Test 1: MemorySaver ===")

    checkpointer = MemorySaver()
    print(f"MemorySaver created: {checkpointer}")
    print(f"Type: {type(checkpointer).__name__}")

    assert hasattr(checkpointer, "get"), "MemorySaver should have 'get' method"
    assert hasattr(checkpointer, "put"), "MemorySaver should have 'put' method"
    print("PASS: MemorySaver core methods exist")


# === Test 2: Basic StateGraph + MemorySaver ===
def test_stategraph_compile():
    """Verify StateGraph compiles correctly"""
    print("\n=== Test 2: StateGraph Compile ===")

    class TestState(TypedDict):
        messages: list[str]
        value: str

    def node_a(state: TestState) -> dict:
        return {"messages": ["node_a"], "value": "done"}

    builder = StateGraph(TestState)
    builder.add_node("a", node_a)
    builder.add_edge(START, "a")
    builder.add_edge("a", END)

    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    assert graph is not None, "Graph should compile"
    print(f"Graph compiled: {type(graph).__name__}")
    print("PASS: StateGraph compiles successfully")


# === Shared state types ===
class InterruptState(TypedDict):
    approved: bool
    step: str


class PersistState(TypedDict):
    count: int
    history: Annotated[list[str], operator.add]


class RouteState(TypedDict):
    path: str


# === Test 3: interrupt / Command HITL ===
def test_interrupt_resume():
    """Verify interrupt / Command(resume=...) mechanism"""
    print("\n=== Test 3: interrupt / Command HITL ===")

    checkpointer = MemorySaver()

    def approval_node(state: InterruptState):
        choice = interrupt({"message": "please confirm", "options": ["accept", "reject"]})
        # choice is the raw value from Command(resume=...)
        is_accepted = choice == "accept"
        return {"approved": is_accepted, "step": "done"}

    builder = StateGraph(InterruptState)
    builder.add_node("approval", approval_node)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "test-thread-1"}}

    # First invoke - should hit interrupt and pause
    result = graph.invoke({"approved": False, "step": "start"}, config)

    has_interrupt = result.get("__interrupt__") is not None
    print(f"First invoke hit interrupt: {has_interrupt}")
    assert has_interrupt, "Should hit interrupt"
    print("PASS: interrupt mechanism works")

    interrupt_val = result["__interrupt__"]
    assert len(interrupt_val) == 1
    assert interrupt_val[0].value.get("message") == "please confirm"
    print(f"Interrupt payload: {interrupt_val[0].value}")
    print("PASS: interrupt payload correct")

    # Resume using Command(resume=...)
    # interrupt() returns the value passed to Command(resume=...)
    resume_result = graph.invoke(
        Command(resume="accept"),
        config,
    )

    assert resume_result.get("approved") == True, "Should be approved after resume"
    print(f"Resume result approved: {resume_result.get('approved')}")
    print("PASS: Command(resume=...) resumes correctly")


# === Test 4: checkpoint persistence ===
def test_checkpoint_persistence():
    """Verify checkpoint correctly saves and restores state"""
    print("\n=== Test 4: Checkpoint Persistence ===")

    checkpointer = MemorySaver()

    def counter_node(state: PersistState) -> dict:
        new_count = state["count"] + 1
        return {"count": new_count, "history": [f"step_{new_count}"]}

    builder = StateGraph(PersistState)
    builder.add_node("counter", counter_node)
    builder.add_edge(START, "counter")
    builder.add_edge("counter", END)
    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "persist-test"}}

    result1 = graph.invoke({"count": 0, "history": []}, config)
    print(f"After invoke 1: count={result1['count']}, history={result1['history']}")

    # With checkpointer, state is restored from checkpoint on each invoke.
    # Just pass a minimal update - the checkpointer restores previous state.
    result2 = graph.invoke({"count": result1["count"]}, config)
    print(f"After invoke 2: count={result2['count']}, history={result2['history']}")

    assert result2["count"] == 2, "Count should accumulate"
    assert len(result2["history"]) == 2, "History should have 2 entries"
    print("PASS: checkpoint state accumulation works")


# === Test 5: conditional routing ===
def test_conditional_routing():
    """Verify conditional routing using path_map dict"""
    print("\n=== Test 5: Conditional Routing ===")

    def router(state: RouteState) -> str:
        """Routing function - returns string keys from path_map."""
        if state["path"] == "a":
            return "node_a"
        elif state["path"] == "b":
            return "node_b"
        return "__end__"

    def node_a(state: RouteState) -> dict:
        return {"path": "done_a"}

    def node_b(state: RouteState) -> dict:
        return {"path": "done_b"}

    builder = StateGraph(RouteState)
    builder.add_node("node_a", node_a)
    builder.add_node("node_b", node_b)
    builder.add_conditional_edges(
        START,
        router,
        {"node_a": "node_a", "node_b": "node_b", "__end__": END},
    )
    builder.add_edge("node_a", END)
    builder.add_edge("node_b", END)

    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "route-test"}}

    result_a = graph.invoke({"path": "a"}, config)
    assert result_a["path"] == "done_a"
    print(f"Route A result: {result_a['path']}")

    result_b = graph.invoke({"path": "b"}, config)
    assert result_b["path"] == "done_b"
    print(f"Route B result: {result_b['path']}")

    print("PASS: conditional routing works")


# === Main entry ===
if __name__ == "__main__":
    print("=" * 60)
    print("LangGraph 1.0+ Core Functionality Verification")
    print("=" * 60)

    test_memory_saver()
    test_stategraph_compile()
    test_interrupt_resume()
    test_checkpoint_persistence()
    test_conditional_routing()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED - LangGraph 1.0+ compatibility verified")
    print("=" * 60)
