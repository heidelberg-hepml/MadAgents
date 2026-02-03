from typing import Any, Dict, List, Optional

from pydantic import BaseModel

#########################################################################
## Pydantic models ######################################################
#########################################################################

class RunInfo(BaseModel):
    thread_id: str
    created_at: str
    last_updated_at: str
    workdir: str
    name: Optional[str] = None


class CostBreakdown(BaseModel):
    cached_input_cost_usd: Optional[float] = None
    input_cost_usd: Optional[float] = None
    output_cost_usd: Optional[float] = None
    output_reasoning_cost_usd: Optional[float] = None
    output_actual_cost_usd: Optional[float] = None
    web_search_cost_usd: Optional[float] = None


class RunDetails(RunInfo):
    estimated_cost_usd: Optional[float] = None
    estimated_cost_note: Optional[str] = None
    estimated_cost_breakdown: Optional[CostBreakdown] = None
    estimated_cost_by_agent: Optional[Dict[str, CostBreakdown]] = None


class RunsResponse(BaseModel):
    runs: List[RunInfo]


class ActiveRunResponse(BaseModel):
    active_thread_id: Optional[str] = None
    active_run_name: Optional[str] = None


class ConfigResponse(BaseModel):
    config: Dict[str, Any]


class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]


class ImportRunResponse(BaseModel):
    status: str
    thread_id: str


class RenameRunRequest(BaseModel):
    thread_id: str
    name: Optional[str] = None


class DeleteRunRequest(BaseModel):
    thread_id: str


class InterruptRunRequest(BaseModel):
    thread_id: str


class RunRequest(BaseModel):
    thread_id: str


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class HistoryMessage(BaseModel):
    name: str
    content: str
    add_content: Optional[dict]
    message_index: Optional[int] = None
    can_rewind_before: Optional[bool] = None


class HistoryResponse(BaseModel):
    messages: list[HistoryMessage]
    event_cursor: Optional[int] = None
    rewind_status: Optional[str] = None


class ChatResponse(BaseModel):
    thread_id: str


class RewindRequest(BaseModel):
    thread_id: str
    message_index: int
    new_message: str
