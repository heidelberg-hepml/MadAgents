import json
import sqlite3
from typing import Optional

import msgpack
from langchain_core.messages import BaseMessage, HumanMessage

from madagents.utils import response_to_text
from madagents.backend.messages import get_add_content, get_exec_trace_messages

#########################################################################
## Checkpoint history helpers ###########################################
#########################################################################

def _checkpoint_message_length(payload: bytes) -> Optional[int]:
    try:
        state = msgpack.unpackb(payload, raw=False)
    except Exception:
        return None
    if not isinstance(state, dict):
        return None
    channel_values = state.get("channel_values")
    if not isinstance(channel_values, dict):
        return None
    messages = channel_values.get("messages")
    if not isinstance(messages, list):
        return None
    return len(messages)


def _get_checkpoint_length_map(db_path: str, thread_id: str) -> dict[int, str]:
    length_map: dict[int, str] = {}
    if not db_path:
        return length_map
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            rows = conn.execute(
                "SELECT rowid, checkpoint_id, type, checkpoint "
                "FROM checkpoints "
                "WHERE thread_id=? AND checkpoint_ns='' "
                "ORDER BY rowid",
                (thread_id,),
            ).fetchall()
    except sqlite3.Error:
        return length_map
    for _, checkpoint_id, checkpoint_type, payload in rows:
        if checkpoint_type != "msgpack" or payload is None:
            continue
        length = _checkpoint_message_length(payload)
        if length is None:
            continue
        length_map[length] = checkpoint_id
    return length_map


def _find_initial_checkpoint_id(db_path: str, thread_id: str) -> Optional[str]:
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            rows = conn.execute(
                "SELECT checkpoint_id, metadata "
                "FROM checkpoints "
                "WHERE thread_id=? AND checkpoint_ns='' "
                "ORDER BY rowid",
                (thread_id,),
            ).fetchall()
    except sqlite3.Error:
        return None

    for checkpoint_id, metadata in rows:
        if not metadata:
            continue
        try:
            meta = json.loads(metadata.decode("utf-8"))
        except Exception:
            continue
        if meta.get("source") == "input" and meta.get("step") == -1:
            return checkpoint_id
    return None


def _get_rewindable_message_indices(db_path: str, thread_id: str) -> set[int]:
    length_map = _get_checkpoint_length_map(db_path, thread_id)
    indices = set(length_map.keys())
    if _find_initial_checkpoint_id(db_path, thread_id) is not None:
        indices.add(0)
    return indices


def _get_checkpoint_before_message(
    db_path: str,
    thread_id: str,
    message_index: int,
) -> Optional[str]:
    if message_index < 0:
        return None
    length_map = _get_checkpoint_length_map(db_path, thread_id)
    if message_index == 0 and 0 not in length_map:
        return _find_initial_checkpoint_id(db_path, thread_id)
    return length_map.get(message_index)


async def extract_message_history(
    thread_id: str,
    agent,
    checkpoint_db: Optional[str] = None,
    checkpoint_id: Optional[str] = None,
    include_rewindable: bool = True,
) -> tuple[list[dict], int]:
    """Build UI message history from checkpoint state."""
    config = {"configurable": {"thread_id": thread_id}}
    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id
    try:
        checkpoint = await agent.graph.aget_state(config)
        values = checkpoint.values if checkpoint else {}
    except Exception as exc:
        print(f"Could not load checkpoint for thread {thread_id}: {exc}")
        return [], 0

    messages = values.get("messages", [])
    agents_messages = values.get("agents_messages", {})

    history: list[dict] = []
    rewindable_indices: set[int] = set()
    if include_rewindable and checkpoint_db and checkpoint_id is None:
        rewindable_indices = _get_rewindable_message_indices(checkpoint_db, thread_id)

    for idx, msg in enumerate(messages):
        agent_name = getattr(msg, "name", None)
        if agent_name in agents_messages:
            agent_batches = agents_messages.get(agent_name)
            additional_kwargs = getattr(msg, "additional_kwargs", None)
            message_id = None
            if isinstance(additional_kwargs, dict):
                message_id = additional_kwargs.get("message_id")
            if isinstance(agent_batches, dict) and message_id:
                batch = agent_batches.get(message_id)
                if batch:
                    for sub_msg in batch:
                        if isinstance(sub_msg, HumanMessage):
                            continue
                        history.extend(get_exec_trace_messages(agent_name, sub_msg))

        payload = {
            "content": response_to_text(msg),
            "name": "user" if isinstance(msg, HumanMessage) else msg.name,
            "add_content": get_add_content(msg),
            "message_index": idx,
        }
        if isinstance(msg, HumanMessage) and rewindable_indices:
            payload["can_rewind_before"] = idx in rewindable_indices
        history.append(payload)

    return history, len(messages)
