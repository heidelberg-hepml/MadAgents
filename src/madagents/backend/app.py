import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
import traceback
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from madagents.madagents import MadAgents
from madagents.config import coerce_config
from madagents.cli_bridge.bridge_handle import InstanceHandle, start_bridge, stop_bridge
from madagents.utils import response_to_text, save_state_atomic

from madagents.backend.constants import (
    BASE_WORKER_AGENTS,
    CHECKPOINTS_DB_PATH,
    INTERRUPT_USER_MESSAGE,
    KNOWN_AGENT_NAMES,
    REVIEWER_AGENT,
    RUNS_DB_PATH,
)
from madagents.backend.db import (
    add_run,
    delete_run_records,
    ensure_app_config_table,
    ensure_runs_table,
    get_run_info,
    get_run_checkpoint_db,
    list_runs,
    load_global_config,
    save_global_config,
    set_run_checkpoint_db,
    set_run_name,
    update_run_last_updated,
)
from madagents.backend.history import (
    _get_checkpoint_before_message,
    _get_rewindable_message_indices,
    extract_message_history,
)
from madagents.backend.messages import (
    _build_interrupt_ai_message,
    _extract_subgraph_summary_fields,
    _format_tool_interrupt_reason,
    _merge_mapping,
    _message_to_ui,
    _update_pending_tool_calls,
    get_add_content,
    get_exec_trace_messages,
)
from madagents.backend.models import (
    ActiveRunResponse,
    ChatRequest,
    ChatResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    DeleteRunRequest,
    HistoryMessage,
    HistoryResponse,
    ImportRunResponse,
    InterruptRunRequest,
    RenameRunRequest,
    RewindRequest,
    RunDetails,
    RunsResponse,
)
from madagents.backend.pricing import _estimate_cost_from_state
from madagents.backend.runs import (
    _add_directory_to_zip,
    _create_run_subset_db,
    _iter_file,
    _resolve_image_overlay_paths,
    _safe_extract_zip,
    _select_import_run_id,
    delete_run_checkpoints,
    merge_run_checkpoints,
    merge_run_metadata,
    set_sys_link,
)

#########################################################################
## FastAPI app ##########################################################
#########################################################################


def _normalize_agent_name(agent_name: Optional[str]) -> Optional[str]:
    if not agent_name or ":" not in agent_name:
        return agent_name
    prefix = agent_name.split(":", 1)[0]
    if prefix in KNOWN_AGENT_NAMES:
        return prefix
    return agent_name


def create_app(
    user_handle: InstanceHandle,
    origin_port: int,
    checkpointer,
    legacy_checkpointer,
) -> FastAPI:
    """
    Build the backend FastAPI app with stateful SSE buffers and run management.

    The app keeps in-memory buffers for events and messages per run, while
    persisting run state to SQLite and workdirs on disk.
    """
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.user_handle = user_handle
    app.state.checkpointer = checkpointer
    app.state.legacy_checkpointer = legacy_checkpointer

    app.state.runs_db = RUNS_DB_PATH
    app.state.checkpoints_db = CHECKPOINTS_DB_PATH
    app.state.legacy_checkpoints_db = RUNS_DB_PATH
    ensure_runs_table(app.state.runs_db)
    ensure_app_config_table(app.state.runs_db)
    app.state.global_config = load_global_config(app.state.runs_db)

    app.state.thread_id = None
    app.state.workdir = None
    app.state.madgraph_handle = None
    app.state.agent = None
    app.state.active_checkpointer = None
    app.state.active_checkpoint_db = None

    app.state.messages = None
    app.state.last_msg_index = None
    app.state.event_buffers = {}  # dict[str, list[dict]]
    app.state.event_waiters = {}  # dict[str, asyncio.Condition]
    app.state.chat_queue = asyncio.Queue()  # asyncio.Queue
    app.state.chat_worker_task = None  # Optional[asyncio.Task]
    app.state.active_run_task = None  # Optional[asyncio.Task]
    app.state.active_thread_id = None  # Optional[str]
    app.state.active_cancel_event = None  # Optional[asyncio.Event]
    app.state.rewind_tasks = {}  # dict[str, asyncio.Task]
    app.state.rewind_status = {}  # dict[str, str]
    app.state.rewind_cache = {}  # dict[str, set[int]]
    app.state.viewed_thread_id = None  # Optional[str]

    ACTIVE_EVENT_KEY = "__active__"

    def resolve_checkpoint_db(thread_id: str) -> str:
        checkpoint_db = get_run_checkpoint_db(app.state.runs_db, thread_id)
        return checkpoint_db or app.state.legacy_checkpoints_db

    def select_checkpointer(checkpoint_db: str):
        if checkpoint_db == app.state.checkpoints_db:
            return app.state.checkpointer
        return app.state.legacy_checkpointer

    def ensure_checkpoint_migrated(thread_id: str) -> str:
        checkpoint_db = get_run_checkpoint_db(app.state.runs_db, thread_id)
        if checkpoint_db:
            return checkpoint_db
        if app.state.checkpoints_db == app.state.legacy_checkpoints_db:
            return app.state.checkpoints_db
        try:
            merge_run_checkpoints(
                app.state.legacy_checkpoints_db,
                app.state.checkpoints_db,
                thread_id,
                thread_id,
                exclude_tables={"runs", "app_config"},
            )
            set_run_checkpoint_db(app.state.runs_db, thread_id, app.state.checkpoints_db)
            return app.state.checkpoints_db
        except Exception as exc:
            print(f"Failed to migrate checkpoints for {thread_id}: {exc}")
            return app.state.legacy_checkpoints_db

    def ensure_event_state(thread_id: str) -> None:
        if thread_id not in app.state.event_buffers:
            app.state.event_buffers[thread_id] = []
        if thread_id not in app.state.event_waiters:
            app.state.event_waiters[thread_id] = asyncio.Condition()

    def get_event_cursor(thread_id: str) -> int:
        buffer = app.state.event_buffers.get(thread_id)
        return len(buffer) if buffer is not None else 0

    async def append_event(thread_id: str, payload: dict) -> int:
        ensure_event_state(thread_id)
        buffer = app.state.event_buffers[thread_id]
        buffer.append(payload)
        event_id = len(buffer) - 1
        condition = app.state.event_waiters[thread_id]
        async with condition:
            condition.notify_all()
        return event_id

    def _get_rewind_status(thread_id: str) -> Optional[str]:
        return app.state.rewind_status.get(thread_id)

    async def _set_rewind_status(thread_id: str, status: str, detail: Optional[str] = None) -> None:
        app.state.rewind_status[thread_id] = status
        payload = {"event": "rewind_status", "status": status}
        if detail:
            payload["detail"] = detail
        await append_event(thread_id, payload)

    async def _run_rewind_scan(thread_id: str) -> None:
        try:
            checkpoint_db = resolve_checkpoint_db(thread_id)
            indices = await asyncio.to_thread(
                _get_rewindable_message_indices,
                checkpoint_db,
                thread_id,
            )
        except asyncio.CancelledError:
            return
        except Exception as exc:
            await _set_rewind_status(thread_id, "error", str(exc))
            return

        if asyncio.current_task() and asyncio.current_task().cancelled():
            return

        app.state.rewind_cache[thread_id] = indices
        await append_event(
            thread_id,
            {
                "event": "rewind_update",
                "rewindable_indices": sorted(indices),
            },
        )
        await _set_rewind_status(thread_id, "ready")

    async def _start_rewind_scan(thread_id: str, force: bool = False) -> None:
        task = app.state.rewind_tasks.get(thread_id)
        if task is not None and not task.done():
            return
        if not force:
            cached = app.state.rewind_cache.get(thread_id)
            status = _get_rewind_status(thread_id)
            if cached and status == "ready":
                return
        await _set_rewind_status(thread_id, "pending")
        scan_task = asyncio.create_task(_run_rewind_scan(thread_id))
        app.state.rewind_tasks[thread_id] = scan_task

        def _cleanup(_task: asyncio.Task) -> None:
            current = app.state.rewind_tasks.get(thread_id)
            if current is _task:
                app.state.rewind_tasks.pop(thread_id, None)

        scan_task.add_done_callback(_cleanup)

    async def _refresh_rewind_scans() -> None:
        desired: set[str] = set()
        if app.state.active_thread_id:
            desired.add(app.state.active_thread_id)
        if app.state.viewed_thread_id:
            desired.add(app.state.viewed_thread_id)

        for thread_id, task in list(app.state.rewind_tasks.items()):
            if thread_id not in desired:
                task.cancel()
                app.state.rewind_tasks.pop(thread_id, None)

        for thread_id in desired:
            status = _get_rewind_status(thread_id)
            await _start_rewind_scan(thread_id, force=status == "error")

    def _apply_rewind_indices(messages: list[dict], indices: Optional[set[int]]) -> list[dict]:
        if not indices:
            return messages
        indexed = set(indices)
        updated = []
        for msg in messages:
            if msg.get("name") == "user" and isinstance(msg.get("message_index"), int):
                updated.append({**msg, "can_rewind_before": msg["message_index"] in indexed})
            else:
                updated.append(msg)
        return updated

    def build_active_state_payload() -> dict:
        active_thread_id = app.state.active_thread_id
        active_name = None
        if active_thread_id:
            run_info = get_run_info(app.state.runs_db, active_thread_id)
            active_name = run_info.name if run_info else None
        return {
            "event": "active_state",
            "active_thread_id": active_thread_id,
            "active_run_name": active_name,
        }

    async def emit_active_state_if_changed() -> None:
        ensure_event_state(ACTIVE_EVENT_KEY)
        buffer = app.state.event_buffers[ACTIVE_EVENT_KEY]
        payload = build_active_state_payload()
        if buffer and buffer[-1] == payload:
            return
        await append_event(ACTIVE_EVENT_KEY, payload)

    async def load_run(thread_id: str, new_run: bool) -> None:
        run_info = get_run_info(app.state.runs_db, thread_id)
        if run_info is None:
            raise HTTPException(status_code=404, detail="Run not found")

        if app.state.madgraph_handle is not None:
            stop_bridge(app.state.madgraph_handle)
        if app.state.agent is not None:
            app.state.agent.close()
            app.state.agent = None
        app.state.thread_id = thread_id
        app.state.workdir = run_info.workdir

        workdir = os.path.join("/runs/workdirs", run_info.workdir)
        os.environ["WORKDIR"] = workdir
        workspace = os.path.join(workdir, "workspace")
        try:
            set_sys_link(workspace, "/workspace")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        log_dir = os.path.join(workdir, "logs")
        try:
            set_sys_link(log_dir, "/logs")
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        app.state.madgraph_handle = start_bridge(
            name="madgraph_cli",
            dir=os.path.join(workdir, "madgraph_bridge"),
            cli_cmd="bash",
        )

        checkpoint_db = ensure_checkpoint_migrated(thread_id)
        app.state.active_checkpoint_db = checkpoint_db
        app.state.active_checkpointer = select_checkpointer(checkpoint_db)
        app.state.agent = MadAgents(
            madgraph_handle=app.state.madgraph_handle,
            user_handle=app.state.user_handle,
            checkpointer=app.state.active_checkpointer,
            config=app.state.global_config,
        )

        app.state.messages = []
        app.state.last_msg_index = 0

        if not new_run:
            cached_indices = app.state.rewind_cache.get(thread_id)
            include_rewindable = bool(cached_indices)
            app.state.messages, app.state.last_msg_index = await extract_message_history(
                thread_id,
                app.state.agent,
                checkpoint_db=app.state.active_checkpoint_db,
                include_rewindable=include_rewindable,
                rewindable_indices=cached_indices,
            )
            if not cached_indices:
                await _start_rewind_scan(thread_id)
        if new_run:
            try:
                with open("/logs/agent.png", "wb") as f:
                    f.write(app.state.agent.graph.get_graph().draw_mermaid_png())
            except Exception as ex:
                print(f"Could not create agent.png. Error: {ex}")

    async def get_checkpoint_values(thread_id: str) -> Optional[dict]:
        if app.state.agent is None:
            await load_run(thread_id, new_run=False)
        agent = app.state.agent
        if agent is None:
            return None
        config = {"configurable": {"thread_id": thread_id}}
        try:
            checkpoint = await agent.graph.aget_state(config)
        except Exception as exc:
            print(f"Could not load checkpoint for thread {thread_id}: {exc}")
            return None
        return checkpoint.values if checkpoint else None

    async def run_chat_message(
        thread_id: str,
        message: str,
        new_run: bool,
        cancel_event: Optional[asyncio.Event] = None,
        checkpoint_id: Optional[str] = None,
    ) -> None:
        """Stream a user message through the graph and append SSE events."""
        if app.state.thread_id is None or thread_id != app.state.thread_id:
            await load_run(thread_id, new_run=new_run)

        agent: MadAgents = app.state.agent
        config = {"configurable": {"thread_id": thread_id}}
        run_config = dict(config)
        if checkpoint_id:
            run_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                }
            }
            app.state.messages, app.state.last_msg_index = await extract_message_history(
                thread_id,
                agent,
                checkpoint_db=app.state.active_checkpoint_db,
                checkpoint_id=checkpoint_id,
                include_rewindable=False,
            )
        interrupted = False
        interrupt_reason: Optional[tuple[str, Optional[str]]] = None
        current_namespace: tuple = ()
        last_subgraph_agent: Optional[str] = None
        last_subgraph_messages: list[BaseMessage] = []
        last_subgraph_summary: Optional[str] = None
        last_subgraph_summary_set = False
        last_subgraph_non_summary_start: Optional[int] = None
        last_subgraph_non_summary_start_set = False
        pending_tool_calls: dict[str, dict] = {}
        pending_apply_patch_calls: dict[str, dict] = {}
        pending_recipient: Optional[str] = None

        if new_run:
            run_info = get_run_info(app.state.runs_db, thread_id)
            await append_event(
                thread_id,
                {
                    "event": "update_run_info",
                    "run_info": run_info.model_dump() if run_info else None,
                },
            )

        human_message = HumanMessage(content=message)
        state = {"messages": [human_message]}
        app.state.messages.append(
            {
                "content": message,
                "name": "user",
                "add_content": get_add_content(human_message),
            }
        )
        app.state.last_msg_index = app.state.last_msg_index + 1

        async def apply_interrupt_updates() -> None:
            if interrupt_reason is None:
                return

            reason_type, reason_detail = interrupt_reason
            tool_reason = _format_tool_interrupt_reason(reason_type, reason_detail)
            synthetic_agent_messages: dict[str, list[BaseMessage]] = {}
            synthetic_root_messages: list[BaseMessage] = []
            synthetic_ui_messages: list[dict] = []

            def resolve_interrupt_fallback_agent() -> Optional[str]:
                for call in pending_tool_calls.values():
                    agent = _normalize_agent_name(call.get("agent"))
                    if agent in BASE_WORKER_AGENTS or agent == REVIEWER_AGENT:
                        return agent
                for call in pending_apply_patch_calls.values():
                    agent = _normalize_agent_name(call.get("agent"))
                    if agent in BASE_WORKER_AGENTS or agent == REVIEWER_AGENT:
                        return agent
                normalized_last_subgraph_agent = _normalize_agent_name(last_subgraph_agent)
                if normalized_last_subgraph_agent in BASE_WORKER_AGENTS or normalized_last_subgraph_agent == REVIEWER_AGENT:
                    return normalized_last_subgraph_agent
                return None

            fallback_agent = resolve_interrupt_fallback_agent()
            if fallback_agent is None:
                fallback_agent = _normalize_agent_name(pending_recipient)

            def add_synthetic_tool_message(
                agent_name: Optional[str],
                tool_msg: ToolMessage,
            ) -> None:
                resolved_agent = agent_name or (last_subgraph_agent if current_namespace != () else None)
                resolved_agent = _normalize_agent_name(resolved_agent)
                if resolved_agent is None:
                    resolved_agent = fallback_agent
                if resolved_agent in BASE_WORKER_AGENTS or resolved_agent == REVIEWER_AGENT:
                    synthetic_agent_messages.setdefault(resolved_agent, []).append(tool_msg)
                    ui_agent = resolved_agent
                else:
                    synthetic_root_messages.append(tool_msg)
                    ui_agent = resolved_agent or "tool"
                synthetic_ui_messages.extend(get_exec_trace_messages(ui_agent, tool_msg))

            # Synthesize tool outputs so the UI receives a clear interrupt.
            if pending_tool_calls:
                for call_id, call in pending_tool_calls.items():
                    tool_name = call.get("name") or "tool"
                    agent_name = call.get("agent")
                    content = {"status": "failed", "error": tool_reason}
                    artifact = None
                    if tool_name in {"bash"}:
                        artifact = {
                            "exit_code": None,
                            "stdout": "",
                            "stderr": tool_reason,
                            "timeout": False,
                        }
                    elif tool_name in {
                        "read_int_cli_output",
                        "run_int_cli_command",
                        "int_cli_status",
                        "read_int_cli_transcript",
                        "read_pdf",
                        "read_image",
                    }:
                        artifact = {"error": tool_reason}

                    tool_msg = ToolMessage(
                        name=tool_name,
                        tool_call_id=call_id,
                        content=content,
                        artifact=artifact,
                    )
                    add_synthetic_tool_message(agent_name, tool_msg)

            if pending_apply_patch_calls:
                grouped_calls: dict[Optional[str], list[dict]] = {}
                for call in pending_apply_patch_calls.values():
                    agent_name = call.get("agent")
                    grouped_calls.setdefault(agent_name, []).append(call)

                for agent_name, calls in grouped_calls.items():
                    outputs: list[dict] = []
                    results: list[dict] = []
                    for call in calls:
                        call_id = call.get("call_id") or ""
                        op = call.get("operation") or {}
                        op_type = op.get("type")
                        op_path = op.get("path")
                        outputs.append(
                            {
                                "type": "apply_patch_call_output",
                                "call_id": call_id,
                                "status": "failed",
                                "output": tool_reason,
                            }
                        )
                        results.append(
                            {
                                "type": op_type,
                                "path": op_path,
                                "status": "failed",
                                "output": tool_reason,
                            }
                        )

                    tool_msg = ToolMessage(
                        name="apply_patch",
                        tool_call_id="apply_patch_batch",
                        content=outputs,
                        artifact={"status": "failed", "results": results},
                    )
                    add_synthetic_tool_message(agent_name, tool_msg)

            checkpoint = None
            values: dict = {}
            try:
                checkpoint = await agent.graph.aget_state(config)
                values = checkpoint.values if checkpoint else {}
            except Exception as exc:
                print(f"Could not load checkpoint for thread {thread_id}: {exc}")

            agent_name = last_subgraph_agent if current_namespace != () else None
            if agent_name is None:
                agent_name = fallback_agent
            interrupt_messages: list[BaseMessage] = []
            update: dict[str, Any] = {}

            # Orchestrator interrupts should not emit a synthetic AIMessage; UI still gets the user interrupt/tool traces.
            skip_interrupt_ai = agent_name == "orchestrator"
            if agent_name and not skip_interrupt_ai:
                additional_kwargs: dict[str, Any] = {}
                message_id: Optional[str] = None
                if agent_name in BASE_WORKER_AGENTS or agent_name in {"planner", REVIEWER_AGENT, "orchestrator"}:
                    message_id = uuid.uuid4().hex
                    additional_kwargs["message_id"] = message_id
                if agent_name in {"planner", "plan_updater"}:
                    plan = values.get("plan") or []
                    additional_kwargs["plan"] = plan
                    plan_meta_data = values.get("plan_meta_data")
                    if plan_meta_data is not None:
                        additional_kwargs["plan_meta_data"] = plan_meta_data
                elif agent_name == "orchestrator":
                    # Avoid reusing a stale orchestrator decision on interrupt.
                    additional_kwargs["orchestrator_decision"] = {}

                interrupt_ai = _build_interrupt_ai_message(
                    agent_name=agent_name,
                    reason_type=reason_type,
                    detail=reason_detail,
                    additional_kwargs=additional_kwargs,
                )
                interrupt_messages.append(interrupt_ai)

                if agent_name in BASE_WORKER_AGENTS or agent_name == REVIEWER_AGENT:
                    batch: list[BaseMessage] = []
                    agent_synthetic = synthetic_agent_messages.pop(agent_name, [])
                    user_msg = None
                    orchestrator_decision = values.get("orchestrator_decision")
                    if isinstance(orchestrator_decision, dict):
                        user_text = orchestrator_decision.get("message")
                        if isinstance(user_text, str) and user_text:
                            user_msg = HumanMessage(content=user_text)
                    if user_msg is not None:
                        batch.append(user_msg)
                    if last_subgraph_messages:
                        batch.extend(last_subgraph_messages)
                    if agent_synthetic:
                        batch.extend(agent_synthetic)
                    batch.append(interrupt_ai)
                    if message_id:
                        update["agents_messages"] = {agent_name: {message_id: batch}}

                if agent_name in BASE_WORKER_AGENTS:
                    if last_subgraph_summary_set:
                        update["agents_message_summary"] = _merge_mapping(
                            values.get("agents_message_summary"),
                            {agent_name: last_subgraph_summary},
                        )
                    if last_subgraph_non_summary_start_set:
                        update["agents_non_summary_start"] = _merge_mapping(
                            values.get("agents_non_summary_start"),
                            {agent_name: last_subgraph_non_summary_start},
                        )

                if message_id:
                    if agent_name == "planner":
                        update["planner_full_messages"] = {message_id: interrupt_ai}
                    elif agent_name == REVIEWER_AGENT:
                        update["reviewer_full_messages"] = {message_id: interrupt_ai}
                    elif agent_name == "orchestrator":
                        update["orchestrator_full_messages"] = {message_id: interrupt_ai}

                if agent_name in {"planner", REVIEWER_AGENT, "orchestrator"}:
                    if last_subgraph_summary_set:
                        update["message_summary"] = last_subgraph_summary
                    if last_subgraph_non_summary_start_set:
                        update["non_summary_start"] = last_subgraph_non_summary_start

            if agent_name and skip_interrupt_ai:
                if last_subgraph_summary_set:
                    update["message_summary"] = last_subgraph_summary
                if last_subgraph_non_summary_start_set:
                    update["non_summary_start"] = last_subgraph_non_summary_start

            interrupt_messages.append(HumanMessage(content=INTERRUPT_USER_MESSAGE))
            if synthetic_root_messages:
                update["messages"] = synthetic_root_messages + interrupt_messages
            else:
                update["messages"] = interrupt_messages

            await _update_graph_state(agent.graph, config, update)

            if app.state.messages is not None:
                ui_messages: list[dict] = []
                if synthetic_ui_messages:
                    ui_messages.extend(synthetic_ui_messages)
                ui_messages.extend(_message_to_ui(msg) for msg in interrupt_messages)
                app.state.messages += ui_messages
                if app.state.last_msg_index is None:
                    app.state.last_msg_index = 0
                app.state.last_msg_index += len(update.get("messages", []))
                await append_event(
                    thread_id,
                    {"event": "message_update", "messages": ui_messages},
                )

        async_gen = None
        try:
            subgraph_last_msg_index = 0

            async_gen = agent.graph.astream(
                state, config=run_config, stream_mode="values", subgraphs=True
            )
            async for namespace, update in async_gen:
                current_namespace = namespace
                if cancel_event is not None and cancel_event.is_set():
                    interrupted = True
                    interrupt_reason = ("user", None)
                    break

                if namespace == ():
                    messages = update["messages"]
                    new_messages = messages[app.state.last_msg_index:]
                    start_index = app.state.last_msg_index or 0
                    rewindable_indices: set[int] = set()
                    if any(isinstance(msg, HumanMessage) for msg in new_messages):
                        cached = app.state.rewind_cache.get(thread_id)
                        if cached:
                            rewindable_indices = cached
                            if _get_rewind_status(thread_id) == "ready":
                                await _start_rewind_scan(thread_id, force=True)
                        else:
                            await _start_rewind_scan(thread_id)
                    if new_messages:
                        _update_pending_tool_calls(
                            new_messages,
                            None,
                            pending_tool_calls,
                            pending_apply_patch_calls,
                        )
                        for msg in new_messages:
                            if getattr(msg, "name", None) == "orchestrator":
                                additional_kwargs = getattr(msg, "additional_kwargs", None)
                                if isinstance(additional_kwargs, dict):
                                    decision = additional_kwargs.get("orchestrator_decision")
                                    if isinstance(decision, dict):
                                        recipient = decision.get("recipient")
                                        if recipient in BASE_WORKER_AGENTS or recipient in {"planner", "plan_updater", REVIEWER_AGENT}:
                                            pending_recipient = recipient
                            elif pending_recipient and getattr(msg, "name", None) == pending_recipient:
                                pending_recipient = None
                    new_messages = [
                        {
                            "content": response_to_text(msg),
                            "name": msg.name,
                            "add_content": get_add_content(msg),
                            "message_index": start_index + i,
                            **(
                                {
                                    "can_rewind_before": (start_index + i)
                                    in rewindable_indices
                                }
                                if isinstance(msg, HumanMessage)
                                else {}
                            ),
                        }
                        for i, msg in enumerate(new_messages)
                    ]
                    app.state.messages += new_messages
                    app.state.last_msg_index = len(messages)

                    payload = {
                        "event": "message_update",
                        "messages": new_messages,
                    }
                    state = await agent.graph.aget_state(config)
                    save_state_atomic(
                        state.values,
                        os.path.join("/runs/workdirs", app.state.workdir, "logs/state.json"),
                    )
                else:
                    last_subgraph_agent = _normalize_agent_name(namespace[0])
                    if pending_recipient == last_subgraph_agent:
                        pending_recipient = None
                    messages = update["messages"]
                    last_subgraph_messages = messages
                    raw_new_messages = messages[subgraph_last_msg_index:]
                    if raw_new_messages:
                        _update_pending_tool_calls(
                            raw_new_messages,
                            last_subgraph_agent,
                            pending_tool_calls,
                            pending_apply_patch_calls,
                        )
                    summary, summary_set, non_summary_start, non_summary_set = _extract_subgraph_summary_fields(update)
                    if summary_set:
                        last_subgraph_summary = summary
                        last_subgraph_summary_set = True
                    if non_summary_set:
                        last_subgraph_non_summary_start = non_summary_start
                        last_subgraph_non_summary_start_set = True
                    new_messages = messages[subgraph_last_msg_index:]
                    new_messages = [
                        msg
                        for msg in new_messages
                        if not isinstance(msg, HumanMessage)
                    ]
                    new_messages = [
                        exec_trace
                        for msg in new_messages
                        for exec_trace in get_exec_trace_messages(namespace[0], msg)
                    ]
                    app.state.messages += new_messages
                    subgraph_last_msg_index = len(messages)
                    payload = {
                        "event": "message_update",
                        "messages": new_messages,
                    }

                await append_event(thread_id, payload)
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            interrupted = True
            if interrupt_reason is None:
                interrupt_reason = ("user", None)
            task = asyncio.current_task()
            if task is not None and hasattr(task, "uncancel"):
                task.uncancel()
        except Exception as e:
            traceback.print_exc()
            interrupted = True
            if interrupt_reason is None:
                interrupt_reason = ("error", str(e))
            err_payload = {
                "event": "error",
                "error": "Error in the backend:\n" + str(e),
            }
            await append_event(thread_id, err_payload)
        finally:
            if async_gen is not None:
                try:
                    await async_gen.aclose()
                except Exception:
                    pass
            if interrupt_reason is not None:
                try:
                    await apply_interrupt_updates()
                except Exception:
                    traceback.print_exc()
            try:
                state = await agent.graph.aget_state(config)
                save_state_atomic(
                    state.values,
                    os.path.join("/runs/workdirs", app.state.workdir, "logs/state.json"),
                )
            except Exception:
                traceback.print_exc()

        if interrupted:
            await append_event(thread_id, {"event": "interrupted"})

        update_run_last_updated(app.state.runs_db, thread_id)
        await append_event(thread_id, {"event": "done"})

    async def chat_worker() -> None:
        while True:
            item = await app.state.chat_queue.get()
            thread_id = item.get("thread_id")
            message = item.get("message")
            new_run = item.get("new_run", False)
            checkpoint_id = item.get("checkpoint_id")
            cancel_event = asyncio.Event()
            app.state.active_thread_id = thread_id
            app.state.active_cancel_event = cancel_event
            await _refresh_rewind_scans()
            await emit_active_state_if_changed()
            app.state.active_run_task = asyncio.create_task(
                run_chat_message(
                    thread_id,
                    message,
                    new_run,
                    cancel_event,
                    checkpoint_id=checkpoint_id,
                )
            )

            try:
                await app.state.active_run_task
            except HTTPException as exc:
                await append_event(
                    thread_id,
                    {"event": "error", "error": exc.detail},
                )
            except Exception as exc:
                traceback.print_exc()
                await append_event(
                    thread_id,
                    {"event": "error", "error": f"Unhandled error:\n{exc}"},
                )
            finally:
                app.state.active_run_task = None
                app.state.active_thread_id = None
                app.state.active_cancel_event = None
                await _refresh_rewind_scans()
                await emit_active_state_if_changed()
                app.state.chat_queue.task_done()

    @app.get("/runs", response_model=RunsResponse)
    async def get_runs(request: Request):
        return RunsResponse(runs=list_runs(request.app.state.runs_db))

    @app.get("/runs/active", response_model=ActiveRunResponse)
    async def get_active_run(request: Request):
        task = request.app.state.active_run_task
        thread_id = request.app.state.active_thread_id
        if task is None or task.done() or not thread_id:
            return ActiveRunResponse(active_thread_id=None, active_run_name=None)

        run_info = get_run_info(request.app.state.runs_db, thread_id)
        active_name = run_info.name if run_info else None
        return ActiveRunResponse(
            active_thread_id=thread_id,
            active_run_name=active_name,
        )

    @app.get("/config", response_model=ConfigResponse)
    async def get_config(request: Request):
        config = request.app.state.global_config
        if config is None:
            config = load_global_config(request.app.state.runs_db)
            request.app.state.global_config = config
        return ConfigResponse(config=config.model_dump(mode="json"))

    @app.post("/config", response_model=ConfigResponse)
    async def update_config(req: ConfigUpdateRequest, request: Request):
        active_task = request.app.state.active_run_task
        if active_task is not None and not active_task.done():
            active_thread_id = request.app.state.active_thread_id
            active_name = None
            if active_thread_id:
                run_info = get_run_info(
                    request.app.state.runs_db,
                    active_thread_id,
                )
                active_name = run_info.name if run_info else None
            return JSONResponse(
                status_code=409,
                content={
                    "status": "busy",
                    "active_thread_id": active_thread_id,
                    "active_run_name": active_name,
                },
            )

        try:
            config = coerce_config(req.config)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        save_global_config(request.app.state.runs_db, config)
        request.app.state.global_config = config

        if request.app.state.agent is not None:
            try:
                request.app.state.agent.close()
            except Exception:
                pass
            request.app.state.agent = MadAgents(
                madgraph_handle=request.app.state.madgraph_handle,
                user_handle=request.app.state.user_handle,
                checkpointer=request.app.state.active_checkpointer
                or request.app.state.checkpointer,
                config=config,
            )

        return ConfigResponse(config=config.model_dump(mode="json"))

    @app.get("/runs/info", response_model=RunDetails)
    async def get_run_info_endpoint(thread_id: str, request: Request):
        run_info = get_run_info(request.app.state.runs_db, thread_id)
        if run_info is None:
            raise HTTPException(status_code=404, detail="Run not found")
        values = await get_checkpoint_values(thread_id)
        estimated_cost, cost_note, cost_breakdown, cost_by_agent = (
            _estimate_cost_from_state(values) if values is not None else (None, None, None, None)
        )
        payload = run_info.model_dump()
        payload["estimated_cost_usd"] = estimated_cost
        payload["estimated_cost_note"] = cost_note
        payload["estimated_cost_breakdown"] = cost_breakdown
        payload["estimated_cost_by_agent"] = cost_by_agent
        return RunDetails(**payload)

    @app.post("/runs/rename")
    async def rename_run(req: RenameRunRequest, request: Request):
        name = req.name.strip() if isinstance(req.name, str) else req.name
        if name == "":
            name = None
        set_run_name(request.app.state.runs_db, req.thread_id, name)
        if request.app.state.active_thread_id == req.thread_id:
            await emit_active_state_if_changed()
        return {"status": "ok"}

    @app.post("/runs/delete")
    async def delete_run(req: DeleteRunRequest, request: Request):
        run_info = get_run_info(request.app.state.runs_db, req.thread_id)
        if run_info is None:
            raise HTTPException(status_code=404, detail="Run not found")

        active_task = request.app.state.active_run_task
        if (
            active_task is not None
            and not active_task.done()
            and request.app.state.active_thread_id == req.thread_id
        ):
            raise HTTPException(
                status_code=409,
                detail="You cannot delete an active run",
            )

        if request.app.state.thread_id == req.thread_id:
            if request.app.state.madgraph_handle is not None:
                stop_bridge(request.app.state.madgraph_handle)
            if request.app.state.agent is not None:
                request.app.state.agent.close()
            request.app.state.thread_id = None
            request.app.state.workdir = None
            request.app.state.madgraph_handle = None
            request.app.state.agent = None
            request.app.state.active_checkpointer = None
            request.app.state.active_checkpoint_db = None
            request.app.state.messages = []
            request.app.state.last_msg_index = None

        workdir_path = os.path.join("/runs/workdirs", run_info.workdir)
        if os.path.exists(workdir_path):
            try:
                shutil.rmtree(workdir_path)
            except Exception as exc:
                raise HTTPException(
                    status_code=409,
                    detail=f"Failed to delete run directory: {exc}",
                )

        checkpoint_db = resolve_checkpoint_db(req.thread_id)
        if checkpoint_db != request.app.state.runs_db:
            delete_run_checkpoints(checkpoint_db, req.thread_id)
        delete_run_records(request.app.state.runs_db, req.thread_id)
        request.app.state.event_buffers.pop(req.thread_id, None)
        request.app.state.event_waiters.pop(req.thread_id, None)
        rewind_task = request.app.state.rewind_tasks.pop(req.thread_id, None)
        if rewind_task is not None:
            rewind_task.cancel()
        request.app.state.rewind_cache.pop(req.thread_id, None)
        request.app.state.rewind_status.pop(req.thread_id, None)

        return {"status": "ok"}

    @app.get("/runs/export/run")
    async def export_run_bundle(
        thread_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
    ):
        run_info = get_run_info(request.app.state.runs_db, thread_id)
        if run_info is None:
            raise HTTPException(status_code=404, detail="Run not found")

        workdir_path = os.path.join("/runs/workdirs", run_info.workdir)
        if not os.path.isdir(workdir_path):
            raise HTTPException(status_code=404, detail="Run workdir not found")

        temp_run_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        temp_run_db.close()
        temp_bundle = tempfile.NamedTemporaryFile(delete=False, suffix=".madrun")
        temp_bundle.close()

        try:
            _create_run_subset_db(
                request.app.state.runs_db,
                temp_run_db.name,
                thread_id,
            )
            checkpoint_db = resolve_checkpoint_db(thread_id)
            if checkpoint_db != request.app.state.runs_db:
                merge_run_checkpoints(
                    checkpoint_db,
                    temp_run_db.name,
                    thread_id,
                    thread_id,
                    exclude_tables={"runs", "app_config"},
                )
            manifest = {
                "version": 1,
                "thread_id": run_info.thread_id,
                "name": run_info.name,
                "created_at": run_info.created_at,
                "last_updated_at": run_info.last_updated_at,
                "workdir": run_info.workdir,
                "run_db": "run.sqlite",
                "workdir_dir": "workdir",
            }
            with zipfile.ZipFile(
                temp_bundle.name,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, indent=2),
                )
                archive.write(temp_run_db.name, "run.sqlite")
                _add_directory_to_zip(archive, workdir_path, "workdir")
        except Exception:
            if os.path.exists(temp_bundle.name):
                os.unlink(temp_bundle.name)
            raise
        finally:
            if os.path.exists(temp_run_db.name):
                os.unlink(temp_run_db.name)

        background_tasks.add_task(os.unlink, temp_bundle.name)
        filename = f"run_{thread_id}.madrun"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(
            _iter_file(temp_bundle.name),
            media_type="application/octet-stream",
            headers=headers,
        )

    @app.get("/runs/export/image")
    async def export_image_bundle(background_tasks: BackgroundTasks):
        image_path, overlay_path = _resolve_image_overlay_paths()
        temp_bundle = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_bundle.close()
        try:
            with zipfile.ZipFile(
                temp_bundle.name,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.write(image_path, os.path.basename(image_path))
                archive.write(overlay_path, os.path.basename(overlay_path))
        except Exception:
            if os.path.exists(temp_bundle.name):
                os.unlink(temp_bundle.name)
            raise
        background_tasks.add_task(os.unlink, temp_bundle.name)
        headers = {
            "Content-Disposition": 'attachment; filename="madagents_image_overlay.zip"'
        }
        return StreamingResponse(
            _iter_file(temp_bundle.name),
            media_type="application/zip",
            headers=headers,
        )

    @app.get("/runs/export/output")
    async def export_output_bundle(background_tasks: BackgroundTasks):
        output_dir = "/output"
        if not os.path.isdir(output_dir):
            raise HTTPException(status_code=404, detail="Output folder not found")

        temp_bundle = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_bundle.close()
        try:
            with zipfile.ZipFile(
                temp_bundle.name,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                _add_directory_to_zip(archive, output_dir, "output")
        except Exception:
            if os.path.exists(temp_bundle.name):
                os.unlink(temp_bundle.name)
            raise
        background_tasks.add_task(os.unlink, temp_bundle.name)
        headers = {"Content-Disposition": 'attachment; filename="madagents_output.zip"'}
        return StreamingResponse(
            _iter_file(temp_bundle.name),
            media_type="application/zip",
            headers=headers,
        )

    @app.post("/runs/import", response_model=ImportRunResponse)
    async def import_run_bundle(
        request: Request,
        file: UploadFile = File(...),
    ):
        if file is None:
            raise HTTPException(status_code=400, detail="No file provided")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                upload_path = os.path.join(temp_dir, "upload.madrun")
                with open(upload_path, "wb") as out_file:
                    shutil.copyfileobj(file.file, out_file)

                with zipfile.ZipFile(upload_path, "r") as archive:
                    _safe_extract_zip(archive, temp_dir)

                run_db_path = os.path.join(temp_dir, "run.sqlite")
                workdir_path = os.path.join(temp_dir, "workdir")
                if not os.path.isfile(run_db_path) or not os.path.isdir(workdir_path):
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid .madrun archive",
                    )

                with sqlite3.connect(f"file:{run_db_path}?mode=ro", uri=True) as conn:
                    row = conn.execute(
                        "SELECT thread_id FROM runs LIMIT 1"
                    ).fetchone()
                if row is None or not row[0]:
                    raise HTTPException(
                        status_code=400,
                        detail="Missing run metadata in archive",
                    )

                old_thread_id = row[0]
                base_dir = "/runs/workdirs"
                os.makedirs(base_dir, exist_ok=True)
                new_thread_id, _ = _select_import_run_id(
                    request.app.state.runs_db,
                    base_dir,
                    old_thread_id,
                )
                target_workdir = os.path.join(base_dir, new_thread_id)
                if os.path.exists(target_workdir):
                    raise HTTPException(
                        status_code=409,
                        detail="Target workdir already exists",
                    )

                shutil.copytree(workdir_path, target_workdir)
                try:
                    merge_run_metadata(
                        run_db_path,
                        request.app.state.runs_db,
                        old_thread_id,
                        new_thread_id,
                        new_thread_id,
                        request.app.state.checkpoints_db,
                    )
                    merge_run_checkpoints(
                        run_db_path,
                        request.app.state.checkpoints_db,
                        old_thread_id,
                        new_thread_id,
                        exclude_tables={"runs", "app_config"},
                    )
                except Exception as exc:
                    shutil.rmtree(target_workdir, ignore_errors=True)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to import run data: {exc}",
                    )
        finally:
            await file.close()

        return ImportRunResponse(status="ok", thread_id=new_thread_id)

    @app.post("/interrupt")
    async def interrupt_run(req: InterruptRunRequest, request: Request):
        thread_id = req.thread_id
        if not thread_id or thread_id == "-1":
            raise HTTPException(status_code=400, detail="Invalid thread id")

        active_thread_id = request.app.state.active_thread_id
        if active_thread_id != thread_id:
            return {"status": "noop", "detail": "No active run for this thread"}

        cancel_event = request.app.state.active_cancel_event
        if cancel_event is not None:
            cancel_event.set()

        task = request.app.state.active_run_task
        if task is not None and not task.done():
            task.cancel()

        return {"status": "ok"}

    @app.get("/history", response_model=HistoryResponse)
    async def get_history(
        thread_id: str,
        request: Request,
        force_refresh: bool = False,
    ):
        if thread_id == "-1":
            app.state.viewed_thread_id = None
            await _refresh_rewind_scans()
            return HistoryResponse(messages=[], event_cursor=0)

        run_info = get_run_info(request.app.state.runs_db, thread_id)
        if run_info is None:
            raise HTTPException(status_code=404, detail="Run not found")

        if app.state.agent is None or app.state.thread_id != thread_id:
            await load_run(thread_id, new_run=False)

        app.state.viewed_thread_id = thread_id
        await _refresh_rewind_scans()

        if force_refresh:
            cached_indices = app.state.rewind_cache.get(thread_id)
            include_rewindable = bool(cached_indices)
            messages, last_idx = await extract_message_history(
                thread_id,
                app.state.agent,
                checkpoint_db=request.app.state.active_checkpoint_db,
                include_rewindable=include_rewindable,
                rewindable_indices=cached_indices,
            )
            app.state.messages = messages
            app.state.last_msg_index = last_idx
        else:
            messages = request.app.state.messages

        cached_indices = app.state.rewind_cache.get(thread_id)
        if cached_indices:
            messages = _apply_rewind_indices(messages or [], cached_indices)
            app.state.messages = messages

        rewind_status = _get_rewind_status(thread_id)
        if rewind_status is None:
            rewind_status = "ready" if cached_indices else "pending"

        return HistoryResponse(
            messages=[HistoryMessage(**msg) for msg in messages],
            event_cursor=get_event_cursor(thread_id),
            rewind_status=rewind_status,
        )

    @app.get("/events/active")
    async def active_events(
        request: Request,
        from_idx: Optional[int] = None,
    ):
        await emit_active_state_if_changed()

        start_idx = from_idx
        last_event_id = request.headers.get("Last-Event-ID")
        if last_event_id:
            try:
                start_idx = int(last_event_id) + 1
            except ValueError:
                start_idx = 0
        if start_idx is None:
            buffer = app.state.event_buffers.get(ACTIVE_EVENT_KEY, [])
            start_idx = max(len(buffer) - 1, 0)

        async def event_stream():
            idx = max(start_idx, 0)
            while True:
                buffer = app.state.event_buffers.get(ACTIVE_EVENT_KEY, [])
                if idx > len(buffer):
                    idx = len(buffer)
                while idx < len(buffer):
                    payload = buffer[idx]
                    yield f"id: {idx}\n"
                    yield f"data: {json.dumps(payload)}\n\n"
                    idx += 1
                if await request.is_disconnected():
                    break
                condition = app.state.event_waiters.get(ACTIVE_EVENT_KEY)
                if condition is None:
                    await asyncio.sleep(0.1)
                    continue
                async with condition:
                    buffer = app.state.event_buffers.get(ACTIVE_EVENT_KEY, [])
                    if idx >= len(buffer):
                        await condition.wait()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get("/events")
    async def events(
        thread_id: str,
        request: Request,
        from_idx: Optional[int] = None,
    ):
        if thread_id == "-1":
            raise HTTPException(status_code=404, detail="Run not found")

        run_info = get_run_info(request.app.state.runs_db, thread_id)
        if run_info is None:
            raise HTTPException(status_code=404, detail="Run not found")

        ensure_event_state(thread_id)

        start_idx = from_idx
        last_event_id = request.headers.get("Last-Event-ID")
        if last_event_id:
            try:
                start_idx = int(last_event_id) + 1
            except ValueError:
                start_idx = 0
        if start_idx is None:
            start_idx = 0

        async def event_stream():
            idx = max(start_idx, 0)
            while True:
                buffer = app.state.event_buffers.get(thread_id, [])
                if idx > len(buffer):
                    idx = len(buffer)
                while idx < len(buffer):
                    payload = buffer[idx]
                    yield f"id: {idx}\n"
                    yield f"data: {json.dumps(payload)}\n\n"
                    idx += 1
                if await request.is_disconnected():
                    break
                condition = app.state.event_waiters.get(thread_id)
                if condition is None:
                    await asyncio.sleep(0.1)
                    continue
                async with condition:
                    buffer = app.state.event_buffers.get(thread_id, [])
                    if idx >= len(buffer):
                        await condition.wait()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/rewind")
    async def rewind(req: RewindRequest, request: Request):
        thread_id = req.thread_id
        message_index = req.message_index
        new_message = req.new_message.strip() if isinstance(req.new_message, str) else ""

        if not thread_id or thread_id == "-1":
            raise HTTPException(status_code=400, detail="Invalid thread id")
        if new_message == "":
            raise HTTPException(status_code=400, detail="New message cannot be empty")

        active_task = request.app.state.active_run_task
        if active_task is not None and not active_task.done():
            active_thread_id = request.app.state.active_thread_id
            active_name = None
            if active_thread_id:
                run_info = get_run_info(
                    request.app.state.runs_db,
                    active_thread_id,
                )
                active_name = run_info.name if run_info else None
            return JSONResponse(
                status_code=409,
                content={
                    "status": "busy",
                    "active_thread_id": active_thread_id,
                    "active_run_name": active_name,
                },
            )

        run_info = get_run_info(request.app.state.runs_db, thread_id)
        if run_info is None:
            raise HTTPException(status_code=404, detail="Run not found")

        if app.state.thread_id is None or app.state.thread_id != thread_id:
            await load_run(thread_id, new_run=False)

        agent = app.state.agent
        if agent is None:
            raise HTTPException(status_code=500, detail="Agent not initialized")

        config = {"configurable": {"thread_id": thread_id}}
        try:
            checkpoint = await agent.graph.aget_state(config)
            values = checkpoint.values if checkpoint else {}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to load state: {exc}")

        messages = values.get("messages", [])
        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="No messages in state")
        if message_index < 0 or message_index >= len(messages):
            raise HTTPException(status_code=400, detail="Message index out of range")
        if not isinstance(messages[message_index], HumanMessage):
            raise HTTPException(status_code=400, detail="Target message is not a user message")

        checkpoint_id = _get_checkpoint_before_message(
            request.app.state.active_checkpoint_db,
            thread_id,
            message_index,
        )
        if checkpoint_id is None:
            raise HTTPException(status_code=409, detail="No checkpoint before that message")

        app.state.messages, app.state.last_msg_index = await extract_message_history(
            thread_id,
            agent,
            checkpoint_db=request.app.state.active_checkpoint_db,
            checkpoint_id=checkpoint_id,
            include_rewindable=False,
        )

        ensure_event_state(thread_id)
        await append_event(
            thread_id,
            {
                "event": "history_reset",
                "messages": app.state.messages,
            },
        )
        if app.state.chat_worker_task is None or app.state.chat_worker_task.done():
            app.state.chat_worker_task = asyncio.create_task(chat_worker())
        await app.state.chat_queue.put(
            {
                "thread_id": thread_id,
                "message": new_message,
                "new_run": False,
                "checkpoint_id": checkpoint_id,
            }
        )

        return {"status": "ok", "checkpoint_id": checkpoint_id}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(
        req: ChatRequest,
        request: Request,
    ):
        active_task = request.app.state.active_run_task
        if active_task is not None and not active_task.done():
            active_thread_id = request.app.state.active_thread_id
            active_name = None
            if active_thread_id:
                run_info = get_run_info(
                    request.app.state.runs_db,
                    active_thread_id,
                )
                active_name = run_info.name if run_info else None
            return JSONResponse(
                status_code=409,
                content={
                    "status": "busy",
                    "active_thread_id": active_thread_id,
                    "active_run_name": active_name,
                },
            )

        new_run = False

        if req.thread_id == "-1":
            base_runs_dir = "/runs/workdirs"
            os.makedirs(base_runs_dir, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S_%f")
            run_id = stamp
            workdir = os.path.join(base_runs_dir, run_id)
            suffix = 0
            while os.path.exists(workdir):
                suffix += 1
                run_id = f"{stamp}_{suffix}"
                workdir = os.path.join(base_runs_dir, run_id)
            os.makedirs(os.path.join(workdir, "workspace"), exist_ok=True)
            os.makedirs(os.path.join(workdir, "logs"), exist_ok=True)
            workdir_rel = os.path.relpath(workdir, "/runs/workdirs")
            add_run(
                request.app.state.runs_db,
                run_id,
                workdir_rel,
                checkpoint_db=request.app.state.checkpoints_db,
            )
            req.thread_id = run_id

            new_run = True

        ensure_event_state(req.thread_id)
        if app.state.chat_worker_task is None or app.state.chat_worker_task.done():
            app.state.chat_worker_task = asyncio.create_task(chat_worker())
        await app.state.chat_queue.put(
            {"thread_id": req.thread_id, "message": req.message, "new_run": new_run}
        )

        return ChatResponse(thread_id=req.thread_id)

    return app


async def _update_graph_state(graph, config: dict, values: dict) -> None:
    update_fn = getattr(graph, "aupdate_state", None)
    if update_fn is not None:
        try:
            await update_fn(config, values)
        except TypeError:
            await update_fn(config, values, as_node="interrupt")
        return
    update_fn = getattr(graph, "update_state", None)
    if update_fn is not None:
        try:
            update_fn(config, values)
        except TypeError:
            update_fn(config, values, as_node="interrupt")
        return
    print("Graph state update not supported; interrupt message not persisted.")
