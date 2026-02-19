import os
from enum import Enum
from typing import TypedDict, List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import json

from pydantic import BaseModel, Field
from typing import Annotated, Callable

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, BaseMessage, AIMessage
from langgraph.graph.message import add_messages

from langgraph.graph import StateGraph, END

from madagents.tools import web_search_tool, WEB_SEARCH_DESC

from madagents.agents.workers.user_cli_operator import USER_CLI_OPERATOR_DESC
from madagents.agents.workers.madgraph_operator import MADGRAPH_OPERATOR_DESC
from madagents.agents.workers.script_operator import SCRIPT_OPERATOR_DESC
from madagents.agents.workers.pdf_reader import PDF_READER_DESC
from madagents.agents.workers.researcher import RESEARCHER_DESC
from madagents.agents.workers.plotter import PLOTTER_DESC
from madagents.utils import invoke_with_validation_retry

#########################################################################
## DESCRIPTION ##########################################################
#########################################################################

PLANNER_DESC = """planner
- This agent breaks a complex task into multiple steps and produces an execution plan.
- If a plan already exists and the planner is invoked to generate a changed or new plan, the existing plan is overwritten by the newly generated one. When revising a plan, clearly state which steps should remain with which status and outcome.
- The plan consists of a list of plan steps. Each plan step contains:
  - `id`: a unique identifier
  - `title`: a concise title
  - `description`: what should be done in this step
  - `rationale`: why this step exists
  - `depends_on`: a list of step IDs this step depends on
  - `status`: one of
    - `pending` (can be started)
    - `in_progress` (currently in progress)
    - `done` (was successfully accomplished)
    - `failed` (was not successfully accomplished)
    - `skipped` (was skipped)
    - `blocked` (cannot be started: one or more dependencies are neither `done` nor `skipped`)
  - `outcome`: populated once the step is finished
    - if `done`: a brief summary/result of the step
    - if `failed`: error/failure details
    - if `skipped`: reason for skipping
- Do not call planner if you cannot state a minimum viable brief for the task, or if the request contains high-stakes ambiguity that would cause the plan to commit to an irreversible path.
  - Minimum viable brief = you can state at least:
    1) the objective / desired end state,
    2) the deliverable type (what will be produced),
    3) the primary constraints or explicitly note that constraints are not provided.
  - High-stakes ambiguity includes: expensive or irreversible actions or multiple plausible deliverables with materially different workflows.
- When missing details are low-stakes and you can provide the minimum viable brief, it is appropriate to call planner even if details are incomplete.
  In this case, planner may include early clarification/discovery steps and should:
  - state key assumptions,
  - ask targeted questions,
  - and schedule preparatory work that is safe under multiple possible answers.
- If unsure whether to ask first or call planner, prefer asking the user 1-3 targeted questions only when the answers would materially change the deliverables, scope, or risk. Otherwise, call planner and let it embed a clarification step.
- When calling planner:
  - State the task to be planned.
  - Provide (or reference) the objective, desired end state, constraints, and expected deliverables.
  - Avoid re-listing the full conversation. The planner sees the same conversation as you; instead, cite or summarize only the key details it must optimize around (e.g., "use the requirements from the user's message above" + any critical constraints).
  - Do not instruct the planner how it should split the task into a plan. The planner will decide this. Instead, focus on what task it should plan.
  - By default, the planner sets each step's `status` to `pending` or `blocked` accordingly and leaves `outcome` empty. If you want specific steps to have different `status`/`outcome` (e.g., when revising an existing plan), explicitly instruct it.
  - Do not instruct planner to create steps that plan_updater or reviewer should perform. The planner must output steps that the workers accomplish. You are responsible for managing workflow, in particular for invoking plan_updater and reviewer when needed.
- planner will:
  - Generate a plan.
  - Automatically update steps in `pending` or `blocked` from dependencies (other statuses are unchanged).
  - Output the plan."""

PLAN_UPDATER_DESC = """plan_updater
- This agent updates the plan by changing the status and outcome of plan steps.
- You do not need to manually change `blocked` steps to `pending` as plan_updater will handle this automatically.
- Instead of instructing it to update the plan, you may ask it to output the current state of the plan. Internally, this will be treated as "no updates".
- When calling plan_updater:
  - Specify exactly which steps should be updated.
  - For those steps, specify the updated `status` and if applicable, the `outcome`.
  - ONLY request step status/outcome updates. In particular, do not ask it to output the full plan or restate plan steps.
- plan_updater will:
  - Create the requested plan updates.
    The system will apply the plan updates to the current plan; steps in `pending` or `blocked` are automatically updated from dependencies (other statuses are unchanged).
    The system will show you the updated plan (in the name of plan_updater)."""

#########################################################################
## Plan objects #########################################################
#########################################################################

class StepStatus(str, Enum):
    """Allowed status values for plan steps."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"

class PlanStep(BaseModel):
    """Single plan step with dependencies, status, and outcome."""
    id: int = Field(..., description="Short unique id for the step (e.g. 1, 2).")
    title: str = Field("", description="Concise title of the plan step.")
    description: str = Field(..., description="What should be done in this step.")
    rationale: str = Field(..., description="Brief description why this step is necessary or this approach has been chosen. Use 1-3 sentences.")
    depends_on: List[int] = Field(
        default_factory=list,
        description="IDs of steps that must be completed before this one can start.",
    )
    status: StepStatus = Field(
        StepStatus.BLOCKED,
        description=(
            "Status of the step:\n"
            "- `pending` (can be started)\n"
            "- `in_progress` (currently in progress)\n"
            "- `done` (was successfully accomplished)\n"
            "- `failed` (was not successfully accomplished)\n"
            "- `skipped` (was skipped)\n"
            "- `blocked` (cannot be started: one or more dependencies are neither `done` or `skipped`)"
        )
    )
    outcome: Optional[str] = Field(
        default=None,
        description=(
            "Outcome of the step:\n"
            "- If the step succeeded this contains a brief summary of what happened.\n"
            "- If the step failed, this contains the error or reason for failure.\n"
            "- If the step was skipped, explain the reason why it was skipped."
        )
    )

class PlanStepMetaData(BaseModel):
    """Metadata for a plan step, including last-updated timestamp."""
    id: int
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlanStepUpdate(BaseModel):
    """Update payload for a single plan step."""
    id: int = Field(..., description="Id of the step to be updated.")
    status: StepStatus = Field(
        ...,
        description=(
            "Updated status of the step:\n"
            "- `pending` (can be started)\n"
            "- `in_progress` (currently in progress)\n"
            "- `done` (was successfully accomplished)\n"
            "- `failed` (was not successfully accomplished)\n"
            "- `skipped` (was skipped)\n"
            "- `blocked` (cannot be started: one or more dependencies are neither `done` or `skipped`)"
        )
    )
    outcome: Optional[str] = Field(
        default=None,
        description=(
            "Updated outcome of the step:\n"
            "- If the step succeeded this contains a brief summary of what happened.\n"
            "- If the step failed, this contains the error or reason for failure.\n"
            "- If the step was skipped, explain the reason why it was skipped."
        )
    )

class Plan(BaseModel):
    """Plan containing an ordered list of steps."""
    steps: List[PlanStep]

class PlanMetaData(BaseModel):
    """Metadata collection aligned to plan steps."""
    steps: List[PlanStepMetaData]

class PlanUpdate(BaseModel):
    """Batch of step updates to apply to a plan."""
    step_updates: List[PlanStepUpdate]

def get_plan_step(plan: Plan | PlanMetaData, id: int) -> PlanStep | PlanStepMetaData | None:
    """Return the plan step or metadata entry with the given id."""
    for plan_step in plan.steps:
        if plan_step.id == id:
            return plan_step
    return None

def sort_plan(plan: Plan, plan_meta_data: PlanMetaData) -> Plan:
    """Sort plan steps by status, recency, then id."""
    status_order = {
        StepStatus.IN_PROGRESS.value: 0,
        StepStatus.DONE.value: 1,
        StepStatus.SKIPPED.value: 2,
        StepStatus.PENDING.value: 3,
        StepStatus.FAILED.value: 4,
        StepStatus.BLOCKED.value: 5,
    }

    meta_by_id = {meta_step.id: meta_step for meta_step in plan_meta_data.steps}

    def status_key(step: PlanStep) -> int:
        # Normalize enum values to strings for sorting.
        status = step.status
        if isinstance(status, Enum):
            status = status.value
        if not isinstance(status, str):
            return len(status_order)
        return status_order.get(status, len(status_order))

    def last_updated_key(step: PlanStep) -> float:
        # Prefer more recently updated steps within a status bucket.
        meta_step = meta_by_id.get(step.id)
        if meta_step is None or not isinstance(meta_step.last_updated, datetime):
            return float("-inf")
        last_updated = meta_step.last_updated
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        return last_updated.timestamp()

    plan.steps = sorted(
        plan.steps,
        key=lambda step: (status_key(step), last_updated_key(step), step.id),
    )
    return plan

def update_blocked(plan: Plan, plan_meta_data) -> Tuple[Plan, PlanMetaData]:
    """Recompute blocked/pending statuses based on dependencies."""
    last_updated = datetime.now(timezone.utc)
    for plan_step in plan.steps:
        # Reset any pending steps to blocked before dependency checks.
        if plan_step.status == StepStatus.PENDING:
            plan_step.status = StepStatus.BLOCKED
            plan_step_meta_data: PlanStepMetaData = get_plan_step(plan_meta_data, plan_step.id)
            plan_step_meta_data.last_updated = last_updated
    for plan_step in plan.steps:
        if plan_step.status == StepStatus.BLOCKED:
            blocked = False
            for depends_on_step_id in plan_step.depends_on:
                depends_on_step: PlanStep = get_plan_step(plan, depends_on_step_id)
                if depends_on_step is not None:
                    if depends_on_step.status not in [StepStatus.DONE, StepStatus.SKIPPED]:
                        blocked = True
                        break
            if not blocked:
                # Promote to pending once all dependencies are done or skipped.
                plan_step.status = StepStatus.PENDING
                plan_step_meta_data: PlanStepMetaData = get_plan_step(plan_meta_data, plan_step.id)
                plan_step_meta_data.last_updated = last_updated
    plan = sort_plan(plan, plan_meta_data)
    return plan, plan_meta_data

def update_plan(plan: Plan, plan_meta_data: PlanMetaData, plan_update: PlanUpdate) -> Tuple[Plan, PlanMetaData]:
    """Apply step updates, then refresh blocked/pending status and ordering."""
    last_updated = datetime.now(timezone.utc)
    for plan_step_update in plan_update.step_updates:
        plan_step: PlanStep | None = get_plan_step(plan, plan_step_update.id)
        if plan_step is None:
            continue
        plan_step_meta_data: PlanStepMetaData = get_plan_step(plan_meta_data, plan_step_update.id)
        plan_step.status = plan_step_update.status
        plan_step.outcome = plan_step_update.outcome
        plan_step_meta_data.last_updated = last_updated
    plan, plan_meta_data = update_blocked(plan, plan_meta_data)
    plan = sort_plan(plan, plan_meta_data)
    return plan, plan_meta_data

def init_plan_meta_data(plan: Plan) -> PlanMetaData:
    """Initialize metadata for each plan step."""
    last_updated = datetime.now(timezone.utc)
    plan_meta_data_steps: List[PlanStepMetaData] = []
    for plan_step in plan.steps:
        meta_data = PlanStepMetaData(id=plan_step.id, last_updated=last_updated)
        plan_meta_data_steps.append(meta_data)
    plan_meta_data = PlanMetaData(steps=plan_meta_data_steps)
    return plan_meta_data

#########################################################################
## State ################################################################
#########################################################################

class PlannerState(TypedDict, total=False):
    reasoning_effort: Optional[str]

    non_summary_start: Optional[int]
    prev_msg_summary: Optional[str]

    prev_msgs: list[BaseMessage]

    messages: Annotated[list[BaseMessage], add_messages]

    plan: List[Dict[str, Any]]
    plan_meta_data: List[Dict[str, Any]]

#########################################################################
## Prompts ##############################################################
#########################################################################

PLANNER_SYSTEM_PROMPT = """You are an AI assistant who creates plans to solve complex tasks.

When creating a plan, keep in mind:
- Modifications of `/output` and `/opt` must be clearly requested or implied by the request. If you are unsure, include clarifications to the plan.
- Destructive or irreversible actions (delete/overwrite, uninstall, change system configs) outside the directory `/workspace` require explicit confirmation.
  Exception: if the user has explicitly requested the exact destructive action and scope (what/where).
- Do not guess:
  - missing critical information or critical facts.
  - unclear, missing, or ambiguous details that are essential for solving the task.
  - specific choices/decisions that cannot easily be changed later on.
  Instead, include clarification instructions in the plan.
  Let the specialized agents make the remaining choices/decisions and specify the remaining configurations.
- Commands can ONLY be executed via the user's CLI session if the user explicitly requested it."""

PLANNER_DEVELOPER_PROMPT = f"""<role>
You are a planning agent called planner.

Your task is to break a complex task into multiple steps and produce an execution plan.
</role>

<environment>
<environment_description>
- You run inside a container whose filesystem persists between sessions. However, `/workspace` is reinitialized at the start of each session and begins empty.
- Key directories:
  - `/output`: This is the user's directory. Write final deliverables to `/output` when the user request implies a deliverable (reports, datasets, images, exported files, scripts).
  - `/workspace`: This is your directory. Write intermediate/temporary files to `/workspace`. This directory is newly created for each session. Do not store final or reproducible outputs in `/workspace`.
  - `/opt`: This directory is used for installations outside the OS package manager. The directory `/opt/envs` is dedicated to Python environments and contains the Python environment `/opt/envs/MAD`.
  - `/pdf_files`: This directory is read-only and contains user-provided PDF files.
- You are part of an agent system, consisting of
  - an orchestrator: It interacts with the user and manages the workflow between the different agents.
  - a planner (you): It creates a multi-step plan for accomplishing a complex task.
  - a plan_updater: It updates the status of plan steps.
  - a reviewer: It reviews plans, executions and outcomes.
  - a set of specialized workers: They perform the work.
- The user shares a CLI session with the user_cli_operator worker.
- After you create the plan:
  - The reviewer will
    - judge your plan.
    - judge the success of key step outcomes.
    - judge the final result.
  - The orchestrator will
    - manage the state of the plan: It sets the `status` and `outcome` according to the progress.
    - work one plan step at a time. It delegates work to the specialized agents and interacts with the user. In particular, it will report any unresolved issues to the user and is able to clarify missing details.
    - instruct you to revise or change the plan if necessary.
</environment_description>

<environment_guidance>
- Avoid writing outside `/output`, `/workspace`, and `/opt` unless explicitly required and clearly necessary.
  Example: Installing OS packages with `apt-get` will write to system locations (e.g., `/usr`, `/etc`, `/var`) and is allowed when needed.
- You and the orchestrator manage the `/workspace` directory entirely. You decide where to create folders, files, ... and what to delete and what to overwrite.
- Manage the directories `/output` and `/opt` with care:
  - Avoid destructive actions if possible unless the user explicitly requested them.
  - When creating directories and files, keep in mind that the same directories are visible in other sessions. Manage them accordingly.
  - Final user-facing deliverables must be placed inside `/output`. Persistent installations (e.g., system tools, Python environments, dependencies) may be placed in `/opt`. Reference all reported file paths using absolute paths.
  - Use `/workspace` for non-persistent installations; otherwise prefer `/opt` or a project-local environment under `/output` for portability/reproducibility.
  - If you are unsure where to place something and it would be hard to change later, ask the user by stating a proposal. Otherwise, follow the defaults (`/workspace` for temporary work, `/output` for deliverables, `/opt` for persistent installations) and state what you chose.
- Always use absolute paths when proposing paths.
- Prefer creating dedicated subdirectories for projects or tasks (e.g., "/workspace/<task>", "/workspace/<task>/scripts").
- Prefer to reuse and extend existing files when it makes sense, rather than duplicating functionality unnecessarily.
- Use clear, descriptive filenames (e.g., "train_model.py", "setup_env.sh").
- Use `/opt/envs/MAD` for shared baseline tools; create per-project envs under `/opt/envs/<project>` when dependency sets differ or reproducibility matters.
- The user's CLI session can always be inspected. However, execute commands via the user's CLI session only if explicitly requested by the user.
</environment_guidance>

<workers>
# {USER_CLI_OPERATOR_DESC}

# {SCRIPT_OPERATOR_DESC}

# {MADGRAPH_OPERATOR_DESC}

# {PDF_READER_DESC}

# {RESEARCHER_DESC}

# {PLOTTER_DESC}
</workers>

<context>
- The user is most likely a particle physicist.
- You can see the full conversation history, including:
  - Messages from the human user.
  - Messages from other agents and you.
  - Possibly a summary of the previous conversation (used to reduce the context length).
- The user mainly works in the directory `/output` via an interactive CLI session. This session can be inspected with the user_cli_operator worker.
- The user can see all messages.
- The orchestrator messages are structured as:
  - `recipient`: The recipient who you message/invoke next.
  - `reasoning`: A brief explanation/motivation why you message/invoke next.
  - `message`: The message you sent to the recipient.
  - `reasoning_effort`: The reasoning effort with which the recipient agent is invoked.
  - `future_note`: Short scratchpad for near-future orchestration.
- The orchestrator and reviewer see the same conversation history as you.
- The plan_updater sees only the orchestrator instructions (the message field).
- The workers see only the instructions from the orchestrator (the message field), their execution traces and final replies. You cannot see the agent's execution trace; they only return their final replies.
</context>

<allowed_assumptions>
Assume the following unless the conversation implies otherwise:
- The user works in the CLI environment that user_cli_operator has access to.
- The user wants event generation and simulations to be performed using MadGraph.
- The user wants the latest versions of the software.
</allowed_assumptions>
</environment>

<tools>
# {WEB_SEARCH_DESC}
</tools>

<instructions>
Your job is to create an execution plan for a task.
You do not need to solve the task yourself. Instead, you should break it into well-defined subtasks that the workers can solve.

<plan>
The plan consists of a list of plan steps. Each plan step contains:
  - `id`: a unique identifier
  - `title`: a concise title
  - `description`: what should be done in this step
  - `rationale`: why this step exists
  - `depends_on`: a list of step IDs this step depends on
  - `status`: one of
    - `pending` (can be started)
    - `in_progress` (currently in progress)
    - `done` (was successfully accomplished)
    - `failed` (was not successfully accomplished)
    - `skipped` (was skipped)
    - `blocked` (cannot be started: one or more dependencies are neither `done` or `skipped`)
  - `outcome`: populated once the step is finished
    - if `done`: a brief summary/result of the step
    - if `failed`: error/failure details
    - if `skipped`: reason for skipping
</plan>

<planning_guidelines>
- Rationale:
  - Clearly motivate this step: What is its purpose? Why is it necessary? Why have you included it?
- Description:
  - Include the objective, desired end state, constraints, and deliverables.
  - Keep it concise. If possible, let the worker agents figure out the details.
  - Unless absolutely required, do not mention which worker(s) should accomplish the plan step. Let the orchestrator decide this.
- Dependencies:
  - Prefer simple, mostly linear dependencies.
  - Keep the dependencies as little as possible (only true prerequisites). A step should depend on prior steps only if it needs their outputs; otherwise keep depends_on empty.
  - The first step must have depends_on = [].
  - Circular dependencies are forbidden.
  - Later steps should only depend on earlier steps.
  - depends_on must reference existing IDs.
- Status and outcome:
  - Do not set those fields unless you have been instructed to do so.
- When creating steps, keep in mind the available workers: Each plan step should be a well-defined subtask that the workers can accomplish.
- A single plan step may require multiple workers.
- Do not mention the workflow between the orchestrator and the planner, plan_updater, reviewer agents. The orchestrator agent handles that.
  In particular, do not include meta-steps about planning itself (e.g. "Review the plan") unless explicitly requested.
- You are allowed to include clarification questions; the orchestrator will ask the user.
- Keep the plan concise, usually between 3 and 7 steps:
  - Use fewer steps only if the goal is very simple.
  - Avoid over-fragmenting into tiny, trivial steps.
  - For very complex tasks, you may use more steps.
</planning_guidelines>

<plan_preferences>
- Prefer educational plans. Ideally, the user should be able to handle similar situations in the future.
- Prefer plan steps that are reproducible, idempotent when reasonable and easy for a human to understand.
</plan_preferences>
</instructions>

<style>
- Tone: Be technically precise.
- Be concise by default. Use short paragraphs and clear structure.
- Use Markdown formatting.
- Format all mathematical content using LaTeX math mode. Avoid Unicode Greek letters in math and prefer LaTeX commands such as \\alpha.
- In non-mathematical context, use plain text words instead of LaTeX.
- When creating LaTeX content, ALWAYS use $...$ for inline math and $$...$$ for displaying equations. This applies to your replies and any content (e.g. files) that you create.
- If it's reasonable, present each plan step in an educational way: Clearly motivate it and include enough explanation for the user to recreate an analogous step for a similar task in the future.
</style>"""

#########################################################################
## Nodes ################################################################
#########################################################################

def get_planner_node(llm: BaseChatModel, tools: list) -> Callable[[PlannerState], dict]:
    """Create a state-graph node that runs the planner LLM."""
    def planner_node(state: PlannerState) -> dict:
        """Assemble prompts, invoke the planner, and return graph updates."""
        # Structured output enforces the Plan schema.
        _llm = llm.with_structured_output(
            Plan,
            include_raw=True,
        )

        _developer_prompt = PLANNER_DEVELOPER_PROMPT
        prev_msgs_summary = state.get("prev_msg_summary", None)
        if prev_msgs_summary is not None and prev_msgs_summary.strip() != "":
            # Inject prior summary to keep the prompt compact.
            _developer_prompt = f"""{PLANNER_DEVELOPER_PROMPT}

<previous_conversation_summary>
{prev_msgs_summary}
</previous_conversation_summary>"""

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            SystemMessage(content=_developer_prompt),
            *state["prev_msgs"],
            *state["messages"],
        ]
        response = invoke_with_validation_retry(
            _llm,
            messages,
        )
        
        response_raw: AIMessage = response["raw"]
        response_raw.name = "planner"

        plan: Plan = response["parsed"]
        plan_meta_data: PlanMetaData = init_plan_meta_data(plan)
        plan, plan_meta_data = update_blocked(plan, plan_meta_data)
        plan = sort_plan(plan, plan_meta_data)

        return {
            "messages": [response_raw],
            "plan": plan.model_dump(mode="json"),
            "plan_meta_data": plan_meta_data.model_dump(mode="json")
        }
    return planner_node

#########################################################################
## Agent ################################################################
#########################################################################

class Planner:
    """Planner agent that produces a structured multi-step plan."""
    def __init__(
        self,
        model: str="glm-5:cloud",
        reasoning_effort: str="high",
        verbosity: str="low"
    ):
        """Initialize planner LLM and compile its state graph."""
        self.llm = ChatOpenAI(
            model=model,
            base_url='http://localhost:11434/v1',
            api_key='ollama',
            max_tokens=1_000_000
        )

        self.tools = [web_search_tool]

        graph = StateGraph(PlannerState)

        graph.add_node("agent", get_planner_node(self.llm, self.tools))

        graph.set_entry_point("agent")
        graph.add_edge("agent", END)

        self.graph = graph.compile().with_config({"recursion_limit": 200})

#########################################################################
## Plan updater prompts ##################################################
#########################################################################

PLAN_UPDATER_SYSTEM_PROMPT = """You are an AI assistant who updates a plan.

- You are only allowed to translate the user request into the step updates.
- Do not fabricate results or outcomes.
- Do not split updates for a single step into multiple step updates: Each step of the plan can have at most a single step update.
- The IDs of the plan step and the step update must match.
- Do not create step updates for nonexistent step IDs.
- When creating the updates for a step, do not omit information the user provided for that step.
- If the user instruction does not contain any information about updating the plan, return an empty list of step updates.
- If the user mentions a step but no update information, do not update this step.
- If the user mentions an outcome of a step, but no status, keep the previous status.
- You must ONLY generate actual plan updates. Do not copy unchanged plan steps."""

def get_plan_updater_developer_prompt(plan: dict) -> str:
    """Build the developer prompt containing the current plan snapshot."""
    return f"""<role>
You are an AI assistant called plan_updater.

Your task is to update steps of a plan.
</role>

<instructions>
The user instructs you to update certain steps of a plan. You return updates for those steps.
The user might ask you to state the current state/status of the plan. Treat this instruction as "no updates" and return an empty list of step updates.

<plan>
The plan consists of a list of plan steps. Each plan step contains:
- `id`: a unique identifier
- `title`: a concise title
- `description`: what should be done in this step
- `rationale`: why this step exists
- `depends_on`: a list of step IDs this step depends on
- `status`: one of
  - `pending` (can be started)
  - `in_progress` (currently in progress)
  - `done` (was successfully accomplished)
  - `failed` (was not successfully accomplished)
  - `skipped` (was skipped)
  - `blocked` (cannot be started: one or more dependencies are neither `done` or `skipped`)
- `outcome`: populated once the step is finished
  - if `done`: a brief summary/result of the step
  - if `failed`: error/failure details
  - if `skipped`: reason for skipping
</plan>

<output>
You return a list of step updates. Each step update contains:
- `id`: the ID of the step to update
- `status`: the updated status of that step
- `outcome`: the outcome of that step if it is finished. You can keep it empty.
The `status` and `outcome` fields of the plan step will be replaced by the update's values.
You are allowed to rephrase text. If you rephrase, preserve all update-relevant facts.
You do not need to update the `blocked` status to `pending`. This will be handled automatically according to the dependencies.

After you create the step updates, the plan will be automatically updated and the full, updated plan is shown to the user.
</output>
</instructions>

<style>
- Tone: Be technically precise.
- Be concise by default. Use short paragraphs and clear structure.
- Use Markdown formatting.
- Format all mathematical content using LaTeX math mode. Avoid Unicode Greek letters in math and prefer LaTeX commands such as \\alpha.
- In non-mathematical context, use plain text words instead of LaTeX.
- When creating LaTeX content, ALWAYS use $...$ for inline math and $$...$$ for displaying equations. This applies to your replies and any content (e.g. files) that you create.
</style>

<current_plan>
{json.dumps(plan, indent=2)}
</current_plan>"""
