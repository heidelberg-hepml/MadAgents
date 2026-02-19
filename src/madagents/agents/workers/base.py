import os
from typing import Optional, TYPE_CHECKING

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage
from langgraph.graph.message import add_messages

from typing import Annotated, Callable
from typing_extensions import TypedDict

from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

if TYPE_CHECKING:
    from madagents.agents.summarizer import Summarizer
from madagents.utils import annotate_output_token_counts

#########################################################################
## State ################################################################
#########################################################################

class BaseWorkerState(TypedDict):
    """State carried through a worker subgraph."""
    reasoning_effort: Optional[str]

    non_summary_start: Optional[int]
    prev_msg_summary: Optional[str]

    prev_msgs: list[BaseMessage]
    user_msg: HumanMessage

    messages: Annotated[list[BaseMessage], add_messages]

#########################################################################
## Nodes ################################################################
#########################################################################

def get_worker_node(
    llm: BaseChatModel,
    system_prompt: str,
    developer_prompt: str,
    name: str,
    summarizer: Optional["Summarizer"] = None,
) -> Callable[[BaseWorkerState], dict]:
    """Create a state-graph node that runs a worker LLM."""
    def worker_node(state: BaseWorkerState) -> dict:
        """Assemble prompts, invoke the worker, and return graph updates."""
        _llm = llm

        prev_msgs_summary = state.get("prev_msg_summary", None)
        non_summary_start = state.get("non_summary_start", 0) or 0

        # On first pass, worker state may already be trimmed by the caller.
        # Reset local index so we don't double-skip messages.
        if not state.get("messages"):
            # Avoid double-skipping when the caller already trimmed messages.
            non_summary_start = 0

        context_msgs = [
            *state["prev_msgs"],
            state["user_msg"],
            *state["messages"],
        ]

        if summarizer is not None:
            # Summarize older context to stay within token limits.
            prev_msgs_summary, non_summary_start = summarizer.summarize(
                prev_msgs_summary,
                non_summary_start,
                context_msgs,
            )
            context_msgs = context_msgs[non_summary_start:]

        _developer_prompt = developer_prompt
        if prev_msgs_summary is not None and prev_msgs_summary.strip() != "":
            _developer_prompt = f"""{developer_prompt}

<previous_conversation_summary>
{prev_msgs_summary}
</previous_conversation_summary>"""

        messages = [
            SystemMessage(content=system_prompt),
            SystemMessage(content=_developer_prompt),
            *context_msgs,
        ]
        response = _llm.invoke(messages)
        response.name = name
        # Persist token counts for downstream accounting.
        annotate_output_token_counts(response, include_reasoning=True, include_total=True)
        
        return {
            "messages": [response],
            "prev_msg_summary": prev_msgs_summary,
            "non_summary_start": non_summary_start,
        }
    return worker_node

#########################################################################
## Agent ################################################################
#########################################################################

class BaseWorker:
    """Base class for workers that run tools under a state graph."""
    def __init__(
        self,
        name: str,
        system_prompt: str,
        developer_prompt: str,
        tools: list,
        state_class: type[BaseWorkerState] = BaseWorkerState,
        model: str="glm-5:cloud",
        reasoning_effort: str="high",
        verbosity: str="low",
        step_limit: Optional[int] = 200,
        summarizer: Optional["Summarizer"] = None,
        worker_node_const: Callable[[BaseWorkerState], dict] = get_worker_node,
        **kwargs
    ):
        """Initialize the worker LLM, tools, and state graph."""
        self.name = name
        self.system_prompt = system_prompt
        self.developer_prompt = developer_prompt
        self.tools = tools
        self.state_class = state_class
        self.summarizer = summarizer

        self.llm = ChatOpenAI(
            model=model,
            base_url='http://localhost:11434/v1',
            api_key='ollama',
            max_tokens=1_000_000
        )

        _tools_for_node = [tool for tool in self.tools if not isinstance(tool, dict)]

        # Bind tools to the LLM.
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        graph = StateGraph(self.state_class)

        graph.add_node(
            "agent",
            worker_node_const(
                self.llm_with_tools,
                self.system_prompt,
                self.developer_prompt,
                self.name,
                summarizer=self.summarizer,
            ),
        )
        graph.add_node("tools", ToolNode(_tools_for_node))

        graph.set_entry_point("agent")

        graph.add_conditional_edges(
            "agent",
            tools_condition,
            {
                "tools": "tools",
                "__end__": "__end__" 
            }
        )

        graph.add_edge("tools", "agent")

        limit = step_limit if isinstance(step_limit, int) and step_limit > 0 else 200
        # Cap the recursion limit to avoid runaway tool loops.
        self.graph = graph.compile().with_config({"recursion_limit": limit})
