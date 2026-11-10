"""The order the nodes run in, the gate, the two branches and the checkpoint."""

import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from agentic.nodes import (
    analyse_installer_statements_node,
    assess_connection_requirements_node,
    await_engineer_decision_node,
    draft_household_notice_node,
    draft_installer_notice_node,
    interpret_model_predictions_node,
    load_application_context_node,
    plan_application_review_node,
    prepare_review_recommendation_node,
    record_connection_outcome_node,
    route_engineer_decision,
)
from agentic.state import ApplicationReviewState
from config import config


def build_workflow(checkpoint_path):
    """Assemble the ten nodes into a workflow that pauses at the gate and survives a restart."""
    folder = os.path.dirname(checkpoint_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    graph = StateGraph(ApplicationReviewState)
    graph.add_node("load_application_context", load_application_context_node)
    graph.add_node("plan_application_review", plan_application_review_node)
    graph.add_node("assess_connection_requirements", assess_connection_requirements_node)
    graph.add_node("analyse_installer_statements", analyse_installer_statements_node)
    graph.add_node("interpret_model_predictions", interpret_model_predictions_node)
    graph.add_node("prepare_review_recommendation", prepare_review_recommendation_node)
    graph.add_node("await_engineer_decision", await_engineer_decision_node)
    graph.add_node("draft_installer_notice", draft_installer_notice_node)
    graph.add_node("draft_household_notice", draft_household_notice_node)
    graph.add_node("record_connection_outcome", record_connection_outcome_node)

    graph.add_edge(START, "load_application_context")
    graph.add_edge("load_application_context", "plan_application_review")
    graph.add_edge("plan_application_review", "assess_connection_requirements")
    graph.add_edge("assess_connection_requirements", "analyse_installer_statements")
    graph.add_edge("analyse_installer_statements", "interpret_model_predictions")
    graph.add_edge("interpret_model_predictions", "prepare_review_recommendation")
    graph.add_edge("prepare_review_recommendation", "await_engineer_decision")
    graph.add_conditional_edges(
        "await_engineer_decision",
        route_engineer_decision,
        {
            config.DECISION_APPROVE: "draft_installer_notice",
            config.DECISION_RETURN: "draft_installer_notice",
            config.DECISION_REFER: "record_connection_outcome",
        },
    )
    graph.add_conditional_edges(
        "draft_installer_notice",
        route_engineer_decision,
        {
            config.DECISION_APPROVE: "draft_household_notice",
            config.DECISION_RETURN: "record_connection_outcome",
        },
    )
    graph.add_edge("draft_household_notice", "record_connection_outcome")
    graph.add_edge("record_connection_outcome", END)

    connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
    return graph.compile(checkpointer=SqliteSaver(connection))
