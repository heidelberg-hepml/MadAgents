from __future__ import annotations

from typing import Optional, Dict, List

from pydantic import BaseModel, Field, field_validator, model_validator

SUPPORTED_MODELS: List[str] = [
    "gpt-5-nano",
    "gpt-5-mini",
    "gpt-5",
    "gpt-5.1",
    "gpt-5.2",
]

VERBOSITY_LEVELS: List[str] = ["low", "medium", "high"]
REASONING_EFFORT_LEVELS: List[str] = ["minimal", "low", "medium", "high"]

# Worker-only agents that can be routed to by the orchestrator.
WORKER_AGENTS: List[str] = [
    "script_operator",
    "researcher",
    "pdf_reader",
    "madgraph_operator",
    "plotter",
    "user_cli_operator",
]

LOOP_AGENTS: List[str] = ["reviewer", *WORKER_AGENTS]

AGENT_ORDER: List[str] = [
    "orchestrator",
    "planner",
    "plan_updater",
    "summarizer",
    "reviewer",
    *WORKER_AGENTS,
]


class AgentConfig(BaseModel):
    model: str = Field(default="gpt-5.1")
    verbosity: str = Field(default="low")
    reasoning_effort: Optional[str] = Field(default=None)
    token_threshold: Optional[int] = Field(default=None)
    keep_last_messages: Optional[int] = Field(default=None)
    min_tail_tokens: Optional[int] = Field(default=None)
    step_limit: Optional[int] = Field(default=None)
    supports_step_limit: bool = Field(default=True)

    @field_validator("model")
    @classmethod
    def _validate_model(cls, value: str) -> str:
        """Ensure the model name is in the supported list."""
        if value not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {value}")
        return value

    @field_validator("verbosity")
    @classmethod
    def _validate_verbosity(cls, value: str) -> str:
        """Ensure verbosity is one of the supported levels."""
        if value not in VERBOSITY_LEVELS:
            raise ValueError(f"Unsupported verbosity: {value}")
        return value

    @field_validator("step_limit")
    @classmethod
    def _validate_step_limit(cls, value: Optional[int]) -> Optional[int]:
        """Validate that the step limit is a positive integer when provided."""
        if value is None:
            return value
        if not isinstance(value, int) or value <= 0:
            raise ValueError("step_limit must be a positive integer")
        return value

    @field_validator("reasoning_effort")
    @classmethod
    def _validate_reasoning_effort(cls, value: Optional[str]) -> Optional[str]:
        """Ensure reasoning effort is one of the supported levels."""
        if value is None:
            return value
        if value not in REASONING_EFFORT_LEVELS:
            raise ValueError(f"Unsupported reasoning effort: {value}")
        return value

    @field_validator("token_threshold", "keep_last_messages", "min_tail_tokens")
    @classmethod
    def _validate_positive_int(cls, value: Optional[int]) -> Optional[int]:
        """Validate optional positive integer fields."""
        if value is None:
            return value
        if not isinstance(value, int) or value <= 0:
            raise ValueError("Value must be a positive integer")
        return value

    @model_validator(mode="after")
    def _normalize_step_limit(self) -> "AgentConfig":
        """Clear step_limit for agents that do not support it."""
        if not self.supports_step_limit:
            self.step_limit = None
        return self


class MadAgentsConfig(BaseModel):
    workflow_step_limit: int = Field(default=1000)
    require_madgraph_evidence: bool = Field(default=True)
    agents: Dict[str, AgentConfig] = Field(default_factory=dict)

    @field_validator("workflow_step_limit")
    @classmethod
    def _validate_workflow_step_limit(cls, value: int) -> int:
        """Validate the workflow step limit is a positive integer."""
        if not isinstance(value, int) or value <= 0:
            raise ValueError("workflow_step_limit must be a positive integer")
        return value


def _default_agents() -> Dict[str, AgentConfig]:
    """Return the default AgentConfig set for all agents."""
    agents: Dict[str, AgentConfig] = {
        "orchestrator": AgentConfig(step_limit=None, supports_step_limit=False),
        "planner": AgentConfig(step_limit=None, supports_step_limit=False),
        "plan_updater": AgentConfig(
            model="gpt-5-mini",
            verbosity="low",
            step_limit=None,
            supports_step_limit=False,
        ),
        "summarizer": AgentConfig(
            step_limit=None,
            supports_step_limit=False,
            reasoning_effort="low",
            token_threshold=150_000,
            keep_last_messages=10,
            min_tail_tokens=10_000,
        ),
        "reviewer": AgentConfig(step_limit=200, supports_step_limit=True),
    }
    for worker in WORKER_AGENTS:
        agents[worker] = AgentConfig(step_limit=200, supports_step_limit=True)
    return agents


def default_config() -> MadAgentsConfig:
    """Build the default MadAgentsConfig."""
    return MadAgentsConfig(workflow_step_limit=1000, agents=_default_agents())


def apply_global_overrides(
    config: MadAgentsConfig,
    *,
    base_model: Optional[str] = None,
    orchestrator_model: Optional[str] = None,
    verbosity: Optional[str] = None,
) -> MadAgentsConfig:
    """Apply optional global overrides to a base config."""
    data = config.model_dump(mode="json")
    if base_model:
        # Override all agent models except the plan updater, which is smaller.
        for name, agent in data.get("agents", {}).items():
            if name == "plan_updater":
                continue
            agent["model"] = base_model
    if orchestrator_model and "orchestrator" in data.get("agents", {}):
        data["agents"]["orchestrator"]["model"] = orchestrator_model
    if verbosity:
        # Set verbosity uniformly across all agents.
        for agent in data.get("agents", {}).values():
            agent["verbosity"] = verbosity
    return MadAgentsConfig.model_validate(data)


def coerce_config(payload: Optional[dict]) -> MadAgentsConfig:
    """Coerce a loose dict payload into a validated MadAgentsConfig."""
    base = default_config()
    if not isinstance(payload, dict):
        return base

    data = base.model_dump(mode="json")

    if "workflow_step_limit" in payload:
        data["workflow_step_limit"] = payload.get("workflow_step_limit")
    if "require_madgraph_evidence" in payload:
        data["require_madgraph_evidence"] = bool(payload.get("require_madgraph_evidence"))

    agents_payload = payload.get("agents")
    if isinstance(agents_payload, dict):
        for name, agent_payload in agents_payload.items():
            if name not in data["agents"]:
                continue
            if not isinstance(agent_payload, dict):
                continue
            # Only apply known per-agent fields.
            for key in (
                "model",
                "verbosity",
                "step_limit",
                "reasoning_effort",
                "token_threshold",
                "keep_last_messages",
                "min_tail_tokens",
            ):
                if key in agent_payload:
                    data["agents"][name][key] = agent_payload.get(key)
            if not data["agents"][name].get("supports_step_limit"):
                # Ensure step_limit is cleared for unsupported agents.
                data["agents"][name]["step_limit"] = None

    return MadAgentsConfig.model_validate(data)
