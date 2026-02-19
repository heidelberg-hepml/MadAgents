import os
import uuid
from typing import TypedDict, List, Dict, Any, Optional, Literal, Callable
from typing import Annotated
import json

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage

from langgraph.checkpoint.base import BaseCheckpointSaver

from madagents.cli_bridge.bridge_handle import InstanceHandle
from madagents.cli_bridge.bridge_interface import CLISession

from madagents.agents.planner import (
    Planner, PlannerState,
    Plan, PlanMetaData,
    PlanUpdate, update_plan,
    PLAN_UPDATER_SYSTEM_PROMPT, get_plan_updater_developer_prompt
)
from madagents.agents.reviewer import Reviewer, ReviewerState
from madagents.agents.orchestrator import Orchestrator, OrchestratorState, OrchestratorDecision

from madagents.agents.workers.base import BaseWorker
from madagents.agents.workers.script_operator import ScriptOperator
from madagents.agents.workers.researcher import Researcher
from madagents.agents.workers.pdf_reader import PDFReader
from madagents.agents.workers.madgraph_operator import MadGraphOperator
from madagents.agents.workers.user_cli_operator import UserCLIOperator
from madagents.agents.workers.plotter import Plotter
from madagents.utils import invoke_with_validation_retry

from madagents.agents.summarizer import Summarizer

from madagents.utils import (
    response_to_text,
    extract_non_reasoning_output_tokens,
    extract_output_token_counts,
    make_summary_fingerprint,
    add_messages_with_token_imputation,
)
from madagents.config import MadAgentsConfig, default_config

#########################################################################
## Config ###############################################################
#########################################################################

DEFAULT_WORKFLOW_STEP_LIMIT = 1_000
DEFAULT_REASONING_EFFORT = "high"
SUMMARIZER_REASONING_EFFORT = "low"
ORCHESTRATOR_REASONING_EFFORT = "high"

#########################################################################
## Helper functions #####################################################
#########################################################################

def merge_agent_messages(
    existing: dict[str, dict[str, list[BaseMessage]]],
    incoming: dict[str, dict[str, list[BaseMessage]]],
) -> dict[str, dict[str, list[BaseMessage]]]:
    """Merge per-agent message batches for graph state updates."""
    # Merge per-agent batches, letting incoming keys overwrite existing batches.
    merged = dict(existing) if isinstance(existing, dict) else {}
    if isinstance(incoming, dict):
        for agent, batches in incoming.items():
            if not isinstance(batches, dict):
                continue
            existing_batches = merged.get(agent)
            if isinstance(existing_batches, dict):
                merged[agent] = {**existing_batches, **batches}
            else:
                merged[agent] = dict(batches)
    return merged

def merge_full_messages(
    existing: dict[str, BaseMessage],
    incoming: dict[str, BaseMessage],
) -> dict[str, BaseMessage]:
    """Merge full message payloads keyed by message_id."""
    # Keep latest payloads for identical message_ids.
    merged = dict(existing) if isinstance(existing, dict) else {}
    if isinstance(incoming, dict) and incoming:
        merged.update(incoming)
    return merged

#########################################################################
## State ################################################################
#########################################################################

class MadAgentsState(TypedDict, total=False):
    # Conversation-oriented fields
    messages: Annotated[list[BaseMessage], add_messages_with_token_imputation]
    
    orchestrator_full_messages: Annotated[dict[str, BaseMessage], merge_full_messages]
    planner_full_messages: Annotated[dict[str, BaseMessage], merge_full_messages]
    plan_updater_full_messages: Annotated[dict[str, BaseMessage], merge_full_messages]
    reviewer_full_messages: Annotated[dict[str, BaseMessage], merge_full_messages]

    message_summary: Optional[str]
    non_summary_start: int

    # Planning / execution state
    plan: List[Dict[str, Any]]
    plan_meta_data: List[Dict[str, Any]]
    
    # Orchestrator
    orchestrator_decision: Dict[str, Any]

    # agents' messages
    agents_messages: Annotated[
        dict[str, dict[str, list[BaseMessage]]],
        merge_agent_messages,
    ]
    agents_message_summary: Dict[str, Optional[str]]
    agents_non_summary_start: Dict[str, int]

#########################################################################
## Nodes ################################################################
#########################################################################

def get_planner_node(planner: Planner, summarizer: Summarizer) -> Callable[[MadAgentsState], dict]:
    """Create a state-graph node that runs the planner."""
    def planner_node(state: MadAgentsState) -> dict:
        """Run planning with summarized context and return graph updates."""
        orchestrator_decision: OrchestratorDecision = state["orchestrator_decision"]

        prev_msgs = [msg for msg in state["messages"]]
        message_summary = state.get("message_summary", None)
        non_summary_start = state.get("non_summary_start", 0)

        # Summarize older context so we only send the unsummarized tail.
        message_summary, non_summary_start = summarizer.summarize(message_summary, non_summary_start, prev_msgs)
        prev_msgs = prev_msgs[non_summary_start:]

        result: PlannerState = planner.graph.invoke({
            "reasoning_effort": orchestrator_decision["reasoning_effort"],
            "non_summary_start": non_summary_start,
            "prev_msg_summary": message_summary,
            "prev_msgs": prev_msgs,
            "messages": []
        })

        plan = result["plan"]
        plan_meta_data = result["plan_meta_data"]
        message_id = uuid.uuid4().hex
        summary_fingerprint = make_summary_fingerprint(message_summary, non_summary_start)
        non_reasoning_output_tokens = extract_non_reasoning_output_tokens(result["messages"][-1])
        # Emit a user-facing plan summary while keeping the full raw response.
        response = AIMessage(
            content=f"I have created the following plan:\n{json.dumps(plan, indent=2)}",
            name="planner",
            additional_kwargs={
                "plan": plan,
                "plan_meta_data": plan_meta_data,
                "message_id": message_id,
                "summary_fingerprint": summary_fingerprint,
                **(
                    {"non_reasoning_output_tokens": non_reasoning_output_tokens}
                    if non_reasoning_output_tokens is not None
                    else {}
                ),
            }
        )

        full_response = result["messages"][-1]
        full_response.name = "planner"
        full_additional = dict(full_response.additional_kwargs or {})
        full_additional["message_id"] = message_id
        full_additional["summary_fingerprint"] = summary_fingerprint
        if non_reasoning_output_tokens is not None:
            full_additional["non_reasoning_output_tokens"] = non_reasoning_output_tokens
        full_response.additional_kwargs = full_additional

        return {
            "messages": [response],
            "planner_full_messages": {message_id: full_response},
            "plan": plan,
            "plan_meta_data": plan_meta_data,
            "message_summary": message_summary,
            "non_summary_start": non_summary_start
        }
    return planner_node

def get_plan_updater_node(plan_updater_llm: BaseChatModel) -> Callable[[MadAgentsState], dict]:
    """Create a state-graph node that applies plan updates."""
    def plan_updater_node(state: MadAgentsState) -> dict:
        """Call the updater LLM and merge the resulting plan changes."""
        orchestrator_decision: OrchestratorDecision = state["orchestrator_decision"]
        reasoning_effort = orchestrator_decision["reasoning_effort"]

        # Use structured output so invalid updates are retried/validated.
        structured_plan_updater = plan_updater_llm.with_structured_output(
            PlanUpdate,
            include_raw=True,
        )

        messages = [
            SystemMessage(content=PLAN_UPDATER_SYSTEM_PROMPT),
            SystemMessage(content=get_plan_updater_developer_prompt(state["plan"])),
            HumanMessage(content=orchestrator_decision["message"])
        ]

        plan_update_response = invoke_with_validation_retry(
            structured_plan_updater,
            messages,
        )
        plan_update_raw: AIMessage = plan_update_response["raw"]
        plan_update_raw.name = "plan_updater"
        plan_update: PlanUpdate = plan_update_response["parsed"]

        # Apply the delta to the current plan + metadata.
        plan: Plan = Plan.model_validate(state["plan"])
        plan_meta_data: PlanMetaData = PlanMetaData.model_validate(state["plan_meta_data"])

        plan, plan_meta_data = update_plan(plan, plan_meta_data, plan_update)
        
        plan = plan.model_dump(mode="json")
        plan_meta_data = plan_meta_data.model_dump(mode="json")

        message_id = uuid.uuid4().hex
        response = AIMessage(
            content=f"The updated plan is:\n{json.dumps(plan, indent=2)}",
            name="plan_updater",
            additional_kwargs={
                "plan": plan,
                "plan_meta_data": plan_meta_data,
                "message_id": message_id,
            }
        )
        full_additional = dict(plan_update_raw.additional_kwargs or {})
        full_additional["message_id"] = message_id
        plan_update_raw.additional_kwargs = full_additional

        return {
            "messages": [response],
            "plan_updater_full_messages": {message_id: plan_update_raw},
            "plan": plan,
            "plan_meta_data": plan_meta_data
        }
    return plan_updater_node

def get_orchestrator_node(orchestrator: Orchestrator, summarizer: Summarizer) -> Callable[[MadAgentsState], dict]:
    """Create a state-graph node that runs the orchestrator."""
    def orchestrator_node(state: MadAgentsState) -> dict:
        """Run orchestration with summarized context and return graph updates."""
        prev_msgs = [msg for msg in state["messages"]]

        message_summary = state.get("message_summary", None)
        non_summary_start = state.get("non_summary_start", 0)

        # Summarize older conversation turns to reduce token usage.
        message_summary, non_summary_start = summarizer.summarize(message_summary, non_summary_start, prev_msgs)
        prev_msgs = prev_msgs[non_summary_start:]

        result: OrchestratorState = orchestrator.graph.invoke({
            "prev_msg_summary": message_summary,
            "non_summary_start": non_summary_start,
            "prev_msgs": prev_msgs,
            "messages": []
        })
        
        orchestrator_decision = result["orchestrator_decision"]
        message_id = uuid.uuid4().hex
        summary_fingerprint = make_summary_fingerprint(message_summary, non_summary_start)
        non_reasoning_output_tokens = extract_non_reasoning_output_tokens(result["messages"][-1])
        response = AIMessage(
            content=response_to_text(result["messages"][-1]),
            name="orchestrator",
            additional_kwargs={
                "orchestrator_decision": orchestrator_decision,
                "message_id": message_id,
                "summary_fingerprint": summary_fingerprint,
                **(
                    {"non_reasoning_output_tokens": non_reasoning_output_tokens}
                    if non_reasoning_output_tokens is not None
                    else {}
                ),
            }
        )

        full_response = result["messages"][-1]
        full_response.name = "orchestrator"
        full_additional = dict(full_response.additional_kwargs or {})
        full_additional["message_id"] = message_id
        full_additional["summary_fingerprint"] = summary_fingerprint
        if non_reasoning_output_tokens is not None:
            full_additional["non_reasoning_output_tokens"] = non_reasoning_output_tokens
        full_response.additional_kwargs = full_additional

        return {
            "messages": [response],
            "orchestrator_full_messages": {message_id: full_response},
            "orchestrator_decision": orchestrator_decision,
            "message_summary": message_summary,
            "non_summary_start": non_summary_start
        }
    return orchestrator_node

def get_reviewer_node(reviewer: Reviewer, summarizer: Summarizer) -> Callable[[MadAgentsState], dict]:
    """Create a state-graph node that runs the reviewer."""
    def reviewer_node(state: MadAgentsState) -> dict:
        """Run reviewer with summarized context and return graph updates."""
        orchestrator_decision: OrchestratorDecision = state["orchestrator_decision"]

        prev_msgs = [msg for msg in state["messages"]]

        message_summary = state.get("message_summary", None)
        non_summary_start = state.get("non_summary_start", 0)

        # Summarize older conversation turns to keep reviewer context compact.
        message_summary, non_summary_start = summarizer.summarize(message_summary, non_summary_start, prev_msgs)
        prev_msgs = prev_msgs[non_summary_start:]

        result: ReviewerState = reviewer.graph.invoke({
            "reasoning_effort": orchestrator_decision["reasoning_effort"],
            "non_summary_start": non_summary_start,
            "prev_msg_summary": message_summary,
            "prev_msgs": prev_msgs,
            "messages": []
        })

        message_id = uuid.uuid4().hex
        non_reasoning_output_tokens = extract_non_reasoning_output_tokens(result["messages"][-1])
        summary_fingerprint = make_summary_fingerprint(message_summary, non_summary_start)
        full_response = result["messages"][-1]
        full_response.name = "reviewer"
        full_additional = dict(full_response.additional_kwargs or {})
        full_additional["message_id"] = message_id
        full_additional["summary_fingerprint"] = summary_fingerprint
        if non_reasoning_output_tokens is not None:
            full_additional["non_reasoning_output_tokens"] = non_reasoning_output_tokens
        full_response.additional_kwargs = full_additional

        return {
            "messages": [
                AIMessage(
                    content=response_to_text(result["messages"][-1]),
                    name="reviewer",
                    additional_kwargs={
                        "message_id": message_id,
                        "summary_fingerprint": summary_fingerprint,
                        **(
                            {"non_reasoning_output_tokens": non_reasoning_output_tokens}
                            if non_reasoning_output_tokens is not None
                            else {}
                        ),
                    },
                )
            ],
            "reviewer_full_messages": {message_id: full_response},
            "agents_messages": {"reviewer": {message_id: [*result["messages"]]}},
            "message_summary": message_summary,
            "non_summary_start": non_summary_start
        }
    return reviewer_node

def get_base_worker_node(base_worker: BaseWorker, agent_name:str, summarizer: Summarizer) -> Callable[[MadAgentsState], dict]:
    """Create a state-graph node wrapper for a worker agent."""
    def base_worker_node(state: MadAgentsState) -> dict:
        """Run a worker with per-agent summarization and return graph updates."""
        orchestrator_decision: OrchestratorDecision = state["orchestrator_decision"]

        agents_message_summary = state.get("agents_message_summary", {})
        agent_message_summary = agents_message_summary.get(agent_name, None)
        agents_non_summary_start = state.get("agents_non_summary_start", {})
        agent_non_summary_start = agents_non_summary_start.get(agent_name, 0)

        # Pull per-agent history so we can summarize only this worker's thread.
        agents_messages = state.get("agents_messages", {})
        agent_messages = agents_messages.get(agent_name, {})
        prev_msgs = [
            msg
            for msg_list in agent_messages.values()
            for msg in msg_list
        ]

        agent_message_summary, agent_non_summary_start = summarizer.summarize(agent_message_summary, agent_non_summary_start, prev_msgs)
        prev_msgs = prev_msgs[agent_non_summary_start:]

        agents_message_summary[agent_name] = agent_message_summary
        agents_non_summary_start[agent_name] = agent_non_summary_start

        # Fingerprint lets downstream token imputation match adjacent messages.
        summary_fingerprint = make_summary_fingerprint(agent_message_summary, agent_non_summary_start)
        result = base_worker.graph.invoke({
            "reasoning_effort": orchestrator_decision["reasoning_effort"],
            "non_summary_start": agent_non_summary_start,
            "prev_msg_summary": agent_message_summary,
            "prev_msgs": prev_msgs,
            "messages": [],
            "user_msg": HumanMessage(content=orchestrator_decision["message"])
        })

        message_id = uuid.uuid4().hex
        # Capture token counts when available for downstream accounting.
        token_counts = extract_output_token_counts(result["messages"][-1]) or {}
        non_reasoning_output_tokens = token_counts.get("non_reasoning_output_tokens")
        reasoning_output_tokens = token_counts.get("reasoning_output_tokens")
        output_tokens = token_counts.get("output_tokens")
        token_kwargs: dict[str, int] = {}
        if isinstance(non_reasoning_output_tokens, int):
            token_kwargs["non_reasoning_output_tokens"] = non_reasoning_output_tokens
        if isinstance(reasoning_output_tokens, int):
            token_kwargs["reasoning_output_tokens"] = reasoning_output_tokens
        if isinstance(output_tokens, int):
            token_kwargs["output_tokens"] = output_tokens
        return {
            "agents_messages": {
                agent_name: {message_id: [result["user_msg"], *result["messages"]]}
            },
            "messages": [
                AIMessage(
                    content=response_to_text(result["messages"][-1]),
                    name=agent_name,
                    additional_kwargs={
                        "message_id": message_id,
                        "summary_fingerprint": summary_fingerprint,
                        **token_kwargs,
                    },
                )
            ],
            "agents_message_summary": agents_message_summary,
            "agents_non_summary_start": agents_non_summary_start
        }
    return base_worker_node

#########################################################################
## Routing ##############################################################
#########################################################################

def route_from_orchestrator(
    state: MadAgentsState,
) -> Literal["user", "planner", "plan_updater", "reviewer", "script_operator", "researcher", "madgraph_operator", "user_cli_operator", "plotter"]:
    """Map the orchestrator decision to the next graph edge."""
    # The orchestrator's decision drives the next graph edge.
    return state["orchestrator_decision"]["recipient"]

#########################################################################
## Agent ################################################################
#########################################################################

class MadAgents:
    """Main entry point that wires agents and runs the workflow graph."""
    def __init__(
        self,
        madgraph_handle: InstanceHandle,
        user_handle: InstanceHandle,
        checkpointer: BaseCheckpointSaver,
        config: Optional[MadAgentsConfig] = None,
    ):
        """Initialize LLM agents, workers, and the state graph."""
        if config is None:
            config = default_config()

        self.config = config
        planner_cfg = config.agents["planner"]
        orchestrator_cfg = config.agents["orchestrator"]

        self.orchestrator = Orchestrator(
            model=orchestrator_cfg.model,
            reasoning_effort=ORCHESTRATOR_REASONING_EFFORT,
            verbosity=orchestrator_cfg.verbosity,
            require_madgraph_evidence=config.require_madgraph_evidence,
        )
        
        self.planner = Planner(
            model=planner_cfg.model,
            reasoning_effort=DEFAULT_REASONING_EFFORT,
            verbosity=planner_cfg.verbosity
        )
        plan_updater_cfg = config.agents["plan_updater"]
        self.plan_updater_llm = ChatOpenAI(
            model=plan_updater_cfg.model,
            base_url='http://localhost:11434/v1',
            api_key='ollama',
            max_tokens=50_000
        )
        summarizer_cfg = config.agents["summarizer"]
        summarizer_effort = (
            summarizer_cfg.reasoning_effort
            if isinstance(summarizer_cfg.reasoning_effort, str)
            else SUMMARIZER_REASONING_EFFORT
        )
        self.summarizer = Summarizer(
            model=summarizer_cfg.model,
            reasoning_effort=summarizer_effort,
            verbosity=summarizer_cfg.verbosity,
            token_threshold=summarizer_cfg.token_threshold or 150_000,
            keep_last_messages=summarizer_cfg.keep_last_messages or 10,
            min_tail_tokens=summarizer_cfg.min_tail_tokens or 10_000,
        )
        reviewer_cfg = config.agents["reviewer"]
        self.reviewer = Reviewer(
            model=reviewer_cfg.model,
            reasoning_effort=DEFAULT_REASONING_EFFORT,
            verbosity=reviewer_cfg.verbosity,
            step_limit=reviewer_cfg.step_limit,
            summarizer=self.summarizer,
            require_madgraph_evidence=config.require_madgraph_evidence,
        )

        worker_model = planner_cfg.model
        worker_verbosity = planner_cfg.verbosity
        script_cfg = config.agents["script_operator"]
        self.script_operator = ScriptOperator(
            model=script_cfg.model or worker_model,
            reasoning_effort=DEFAULT_REASONING_EFFORT,
            verbosity=script_cfg.verbosity or worker_verbosity,
            step_limit=script_cfg.step_limit,
            summarizer=self.summarizer
        )
        researcher_cfg = config.agents["researcher"]
        self.researcher = Researcher(
            model=researcher_cfg.model or worker_model,
            reasoning_effort=DEFAULT_REASONING_EFFORT,
            verbosity=researcher_cfg.verbosity or worker_verbosity,
            step_limit=researcher_cfg.step_limit,
            summarizer=self.summarizer
        )
        pdf_cfg = config.agents["pdf_reader"]
        self.pdf_reader = PDFReader(
            model=pdf_cfg.model or worker_model,
            reasoning_effort=DEFAULT_REASONING_EFFORT,
            verbosity=pdf_cfg.verbosity or worker_verbosity,
            step_limit=pdf_cfg.step_limit,
            summarizer=self.summarizer
        )
        plotter_cfg = config.agents["plotter"]
        self.plotter = Plotter(
            model=plotter_cfg.model or worker_model,
            reasoning_effort=DEFAULT_REASONING_EFFORT,
            verbosity=plotter_cfg.verbosity or worker_verbosity,
            step_limit=plotter_cfg.step_limit,
            summarizer=self.summarizer
        )

        self.cli_session = CLISession(handle=madgraph_handle)
        madgraph_cfg = config.agents["madgraph_operator"]
        self.madgraph_operator = MadGraphOperator(
            session=self.cli_session,
            model=madgraph_cfg.model or worker_model,
            reasoning_effort=DEFAULT_REASONING_EFFORT,
            verbosity=madgraph_cfg.verbosity or worker_verbosity,
            step_limit=madgraph_cfg.step_limit,
            summarizer=self.summarizer
        )
        self.user_cli_session = CLISession(handle=user_handle)
        user_cli_cfg = config.agents["user_cli_operator"]
        self.user_cli_operator = UserCLIOperator(
            session=self.user_cli_session,
            model=user_cli_cfg.model or worker_model,
            reasoning_effort=DEFAULT_REASONING_EFFORT,
            verbosity=user_cli_cfg.verbosity or worker_verbosity,
            step_limit=user_cli_cfg.step_limit,
            summarizer=self.summarizer
        )

        self._closed = False

        graph = StateGraph(MadAgentsState)

        graph.add_node("orchestrator", get_orchestrator_node(self.orchestrator, self.summarizer))
        graph.add_node("planner", get_planner_node(self.planner, self.summarizer))
        graph.add_node("plan_updater", get_plan_updater_node(self.plan_updater_llm))
        graph.add_node("reviewer", get_reviewer_node(self.reviewer, self.summarizer))
        
        graph.add_node("script_operator", get_base_worker_node(self.script_operator, "script_operator", self.summarizer))
        graph.add_node("researcher", get_base_worker_node(self.researcher, "researcher", self.summarizer))
        graph.add_node("pdf_reader", get_base_worker_node(self.pdf_reader, "pdf_reader", self.summarizer))
        graph.add_node("plotter", get_base_worker_node(self.plotter, "plotter", self.summarizer))
        graph.add_node("madgraph_operator", get_base_worker_node(self.madgraph_operator, "madgraph_operator", self.summarizer))
        graph.add_node("user_cli_operator", get_base_worker_node(self.user_cli_operator, "user_cli_operator", self.summarizer))

        graph.add_edge(START, "orchestrator")
        graph.add_edge("planner", "orchestrator")
        graph.add_edge("plan_updater", "orchestrator")
        graph.add_edge("reviewer", "orchestrator")

        graph.add_edge("script_operator", "orchestrator")
        graph.add_edge("researcher", "orchestrator")
        graph.add_edge("pdf_reader", "orchestrator")
        graph.add_edge("plotter", "orchestrator")
        graph.add_edge("madgraph_operator", "orchestrator")
        graph.add_edge("user_cli_operator", "orchestrator")


        graph.add_conditional_edges(
            "orchestrator",
            route_from_orchestrator,
            {
                "planner": "planner",
                "plan_updater": "plan_updater",
                "reviewer": "reviewer",
                "script_operator": "script_operator",
                "researcher": "researcher",
                "pdf_reader": "pdf_reader",
                "plotter": "plotter",
                "madgraph_operator": "madgraph_operator",
                "user_cli_operator": "user_cli_operator",
                "user": END,
            },
        )

        workflow_limit = (
            config.workflow_step_limit
            if isinstance(config.workflow_step_limit, int) and config.workflow_step_limit > 0
            else DEFAULT_WORKFLOW_STEP_LIMIT
        )
        # Compile the graph with a recursion limit derived from config.
        self.graph = graph.compile(
            checkpointer=checkpointer
        ).with_config({"recursion_limit": workflow_limit})

    def close(self) -> None:
        """Attempt to terminate any active subprocesses and close resources."""
        if self._closed:
            return
        try:
            # Best-effort cleanup for any lingering subprocesses.
            from madagents.tools import terminate_processes_for_current_logs
            terminate_processes_for_current_logs()
        finally:
            self._closed = True

    def __del__(self) -> None:
        """Best-effort cleanup on garbage collection."""
        try:
            self.close()
        except Exception:
            pass
