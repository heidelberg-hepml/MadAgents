import React, { useEffect, useMemo, useRef, useState } from "react";
import "katex/dist/katex.min.css";
import {
  BACKEND_URL,
  SELECTED_THREAD_ID_KEY,
  darkTheme,
  lightTheme,
  WORKER_AGENTS,
} from "./lib/constants";
import { stripControlChars } from "./lib/formatters";
import { getUpdatedPlanSteps } from "./lib/plan";
import MessageComposer from "./components/MessageComposer";
import MessageList from "./components/MessageList";
import SettingsModal from "./components/modals/SettingsModal";
import RunDetailsModal from "./components/modals/RunDetailsModal";
import ExportRunModal from "./components/modals/ExportRunModal";
import CostDetailsModal from "./components/modals/CostDetailsModal";

function App() {
  const [messages, setMessages] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selectedThreadId, setSelectedThreadId] = useState(() => {
    try {
      const raw = window.localStorage.getItem(SELECTED_THREAD_ID_KEY);
      if (!raw || raw === "null" || raw === "undefined") {
        return null;
      }
      return raw;
    } catch (e) {
      console.warn("Failed to read selected thread id", e);
      return null;
    }
  });
  const [runMenu, setRunMenu] = useState({
    open: false,
    x: 0,
    y: 0,
    run: null,
  });
  const [runDetailsOpen, setRunDetailsOpen] = useState(false);
  const [runDetails, setRunDetails] = useState(null);
  const [runDetailsLoading, setRunDetailsLoading] = useState(false);
  const [runDetailsError, setRunDetailsError] = useState("");
  const [configOpen, setConfigOpen] = useState(false);
  const [configDraft, setConfigDraft] = useState(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [configError, setConfigError] = useState("");
  const [configHelpKey, setConfigHelpKey] = useState(null);
  const [workerGroup, setWorkerGroup] = useState({
    model: "",
    verbosity: "",
    step_limit: "",
  });
  const [exportRunOpen, setExportRunOpen] = useState(false);
  const [exportRun, setExportRun] = useState(null);
  const [exportOptions, setExportOptions] = useState({
    image: false,
    output: false,
  });
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [costDetailsOpen, setCostDetailsOpen] = useState(false);
  const [editingRunId, setEditingRunId] = useState(null);
  const [editingRunName, setEditingRunName] = useState("");
  const [rewindEditIndex, setRewindEditIndex] = useState(null);
  const [rewindError, setRewindError] = useState("");
  const [isRewinding, setIsRewinding] = useState(false);
  const [rewindStatusByThread, setRewindStatusByThread] = useState({});
  const rewindTextRef = useRef(null);
  const importInputRef = useRef(null);
  const [loadingByThreadId, setLoadingByThreadId] = useState({});
  const [pendingRunId, setPendingRunId] = useState(null);
  const [activeRun, setActiveRun] = useState({ threadId: null, name: null });
  const [error, setError] = useState("");
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [darkMode, setDarkMode] = useState(
    window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
  );

  const theme = darkMode ? darkTheme : lightTheme;
  const currentThreadKey = selectedThreadId ?? "-1";
  const activeThreadId = activeRun.threadId;
  const isActiveHere = Boolean(activeThreadId && activeThreadId === currentThreadKey);
  const isAnyRunActive = Boolean(activeThreadId);
  const isLoading = Boolean(loadingByThreadId[currentThreadKey]) || isActiveHere;
  const canInterrupt = isLoading && currentThreadKey !== "-1";
  const blockNewMessages = Boolean(activeThreadId && activeThreadId !== currentThreadKey);
  const rewindDisabled = isLoading || blockNewMessages;
  const currentRewindStatus =
    selectedThreadId && selectedThreadId !== "-1"
      ? rewindStatusByThread[selectedThreadId] || "pending"
      : null;

  const scrollContainerRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const eventSourceRef = useRef(null);
  const activeEventSourceRef = useRef(null);
  const eventCursorRef = useRef(0);
  const skipHistoryRef = useRef(false);
  const shouldRecalcAutoScrollRef = useRef(false);
  const streamErrorRef = useRef(false);

  useEffect(() => {
    document.title = "MadAgents";
  }, []);

  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    const prev = {
      htmlOverflow: html.style.overflow,
      bodyOverflow: body.style.overflow,
      htmlHeight: html.style.height,
      bodyHeight: body.style.height,
      bodyMargin: body.style.margin,
    };

    html.style.overflow = "hidden";
    html.style.height = "100%";
    body.style.overflow = "hidden";
    body.style.height = "100%";
    body.style.margin = "0";

    return () => {
      html.style.overflow = prev.htmlOverflow;
      html.style.height = prev.htmlHeight;
      body.style.overflow = prev.bodyOverflow;
      body.style.height = prev.bodyHeight;
      body.style.margin = prev.bodyMargin;
    };
  }, []);

  const getEventCursorKey = (threadId) => `madagents_event_cursor_${threadId}`;

  const loadStoredCursor = (threadId) => {
    if (!threadId) return 0;
    try {
      const raw = window.localStorage.getItem(getEventCursorKey(threadId));
      const parsed = Number(raw);
      return Number.isFinite(parsed) ? parsed : 0;
    } catch (e) {
      console.warn("Failed to read event cursor", e);
      return 0;
    }
  };

  const storeCursor = (threadId, cursor) => {
    if (!threadId) return;
    try {
      window.localStorage.setItem(getEventCursorKey(threadId), String(cursor));
    } catch (e) {
      console.warn("Failed to store event cursor", e);
    }
  };

  const setThreadLoading = (threadId, value) => {
    if (!threadId) return;
    setLoadingByThreadId((prev) => {
      const next = { ...prev };
      if (value) {
        next[threadId] = true;
      } else {
        delete next[threadId];
      }
      return next;
    });
  };

  const closeActiveEventSource = () => {
    if (activeEventSourceRef.current) {
      activeEventSourceRef.current.close();
      activeEventSourceRef.current = null;
    }
  };

  const connectActiveEventSource = () => {
    closeActiveEventSource();
    const url = new URL(`${BACKEND_URL}/events/active`);
    const es = new EventSource(url.toString());
    activeEventSourceRef.current = es;

    es.onmessage = (event) => {
      if (!event?.data) return;
      let eventData;
      try {
        eventData = JSON.parse(event.data);
      } catch (e) {
        console.error("Failed to parse active SSE JSON:", e, event.data);
        return;
      }

      const threadId = eventData?.active_thread_id ?? null;
      const name = eventData?.active_run_name ?? null;
      setActiveRun((prev) => {
        if (prev.threadId === threadId && prev.name === name) {
          return prev;
        }
        return { threadId, name };
      });
    };

    es.onerror = (err) => {
      console.error("Active SSE error", err);
    };
  };

  const moveThreadLoading = (fromThreadId, toThreadId) => {
    if (!fromThreadId || !toThreadId || fromThreadId === toThreadId) {
      return;
    }
    setLoadingByThreadId((prev) => {
      if (!prev[fromThreadId]) {
        return prev;
      }
      const next = { ...prev };
      delete next[fromThreadId];
      next[toThreadId] = true;
      return next;
    });
  };

  useEffect(() => {
    try {
      if (!selectedThreadId) {
        window.localStorage.removeItem(SELECTED_THREAD_ID_KEY);
        return;
      }
      window.localStorage.setItem(SELECTED_THREAD_ID_KEY, selectedThreadId);
    } catch (e) {
      console.warn("Failed to store selected thread id", e);
    }
  }, [selectedThreadId]);

  useEffect(() => {
    connectActiveEventSource();
    return () => {
      closeActiveEventSource();
    };
  }, []);

  const closeEventSource = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  const handleEventData = (eventData, threadId) => {
    if (!eventData || !threadId) return;

    if (eventData.event === "message_update") {
      const newMessages =
        (eventData.messages ?? []).map((m) => ({
          name: m.name || "assistant",
          content: m.content,
          add_content: m.add_content,
          message_index: m.message_index,
          can_rewind_before: m.can_rewind_before,
        })) || [];

      setMessages((prev) => [...prev, ...newMessages]);
    } else if (eventData.event === "history_reset") {
      const newMessages =
        (eventData.messages ?? []).map((m) => ({
          name: m.name || "assistant",
          content: m.content,
          add_content: m.add_content,
          message_index: m.message_index,
          can_rewind_before: m.can_rewind_before,
        })) || [];
      setMessages(newMessages);
      shouldRecalcAutoScrollRef.current = true;
    } else if (eventData.event === "rewind_status") {
      const status = typeof eventData.status === "string" ? eventData.status : "pending";
      setRewindStatusByThread((prev) => ({ ...prev, [threadId]: status }));
    } else if (eventData.event === "rewind_update") {
      const indices = new Set(eventData.rewindable_indices || []);
      setMessages((prev) =>
        prev.map((m) => {
          if (
            m.name === "user" &&
            typeof m.message_index === "number"
          ) {
            return { ...m, can_rewind_before: indices.has(m.message_index) };
          }
          return m;
        })
      );
      setRewindStatusByThread((prev) => ({ ...prev, [threadId]: "ready" }));
    } else if (eventData.event === "error") {
      streamErrorRef.current = true;
      setError(eventData.error || "Unknown error from server");
      setThreadLoading(threadId, false);
    } else if (eventData.event === "interrupted") {
      setThreadLoading(threadId, false);
      setActiveRun((prev) =>
        prev.threadId === threadId ? { threadId: null, name: null } : prev
      );
    } else if (eventData.event === "done") {
      setThreadLoading(threadId, false);
      setActiveRun((prev) =>
        prev.threadId === threadId ? { threadId: null, name: null } : prev
      );
      fetchRuns();
      if (threadId === selectedThreadId) {
        reloadHistory(threadId);
      }
      if (!streamErrorRef.current) {
        setError("");
      }
      streamErrorRef.current = false;
    }
  };

  const connectEventSource = (threadId, fromCursor) => {
    if (!threadId || threadId === "-1") return;
    closeEventSource();

    const url = new URL(`${BACKEND_URL}/events`);
    url.searchParams.set("thread_id", threadId);
    url.searchParams.set("from_idx", String(Math.max(0, fromCursor)));

    const es = new EventSource(url.toString());
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      if (!event?.data) return;
      let eventData;
      try {
        eventData = JSON.parse(event.data);
      } catch (e) {
        console.error("Failed to parse SSE JSON:", e, event.data);
        return;
      }

      // Keep cursor in sync so we can resume after a refresh.
      if (event.lastEventId) {
        const parsedId = Number(event.lastEventId);
        if (Number.isFinite(parsedId)) {
          eventCursorRef.current = parsedId + 1;
          storeCursor(threadId, eventCursorRef.current);
        }
      } else {
        eventCursorRef.current += 1;
        storeCursor(threadId, eventCursorRef.current);
      }

      handleEventData(eventData, threadId);
    };

    es.onerror = (err) => {
      console.error("SSE error", err);
    };
  };

  const reloadHistory = async (threadId) => {
    if (!threadId || threadId === "-1") return;
    closeEventSource();
    setIsHistoryLoading(true);
    skipHistoryRef.current = false;
    try {
      const res = await fetch(
        `${BACKEND_URL}/history?thread_id=${encodeURIComponent(threadId)}&force_refresh=1`
      );
      if (!res.ok) {
        await reportResponseError(res, "Failed to load history");
        return;
      }
      const data = await res.json();
      setMessages(data.messages ?? []);
      setRewindStatusByThread((prev) => ({
        ...prev,
        [threadId]: data.rewind_status || "pending",
      }));
      shouldRecalcAutoScrollRef.current = true;
      const cursor = Number(data.event_cursor);
      const storedCursor = loadStoredCursor(threadId);
      const nextCursor = Number.isFinite(cursor) ? cursor : storedCursor;
      eventCursorRef.current = nextCursor;
      storeCursor(threadId, nextCursor);
      connectEventSource(threadId, nextCursor);
    } catch (e) {
      console.error("Failed to load history", e);
      setError(e instanceof Error ? e.message : "Failed to load history");
    } finally {
      setIsHistoryLoading(false);
    }
  };

  const formatRunLabel = (run) => {
    if (run?.name && run.name.trim() !== "") return stripControlChars(run.name);
    const createdAt = run?.created_at;
    if (!createdAt) return "Unnamed run";
    const date = new Date(createdAt);
    if (Number.isNaN(date.getTime())) return createdAt;
    return date.toLocaleString();
  };

  const formatActiveRunLabel = (threadId, name) => {
    if (name && String(name).trim() !== "") return name;
    const run = runs.find((item) => item.thread_id === threadId);
    if (run) return formatRunLabel(run);
    return threadId || "another run";
  };

  const activeRunLabel = useMemo(() => {
    if (!activeThreadId) return "";
    return formatActiveRunLabel(activeThreadId, activeRun.name);
  }, [activeThreadId, activeRun.name, runs]);

  const openCostDetails = () => {
    setCostDetailsOpen(true);
    setRunDetailsOpen(false);
  };

  const closeCostDetails = () => {
    setCostDetailsOpen(false);
  };

  const reportResponseError = async (res, fallbackMessage) => {
    let detail = "";
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      } else if (typeof data?.error === "string") {
        detail = data.error;
      }
    } catch (e) {
      detail = "";
    }
    const message = detail ? `${fallbackMessage}: ${detail}` : `${fallbackMessage} (${res.status})`;
    setError(message);
  };

  const normalizeConfigPayload = (payload) => {
    if (!payload) return null;
    if (payload.config && typeof payload.config === "object") {
      return payload.config;
    }
    return payload;
  };

  const parsePositiveInt = (raw) => {
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return null;
    const intValue = Math.floor(parsed);
    return intValue > 0 ? intValue : null;
  };

  const openSettings = () => {
    setConfigOpen(true);
    fetchConfig();
  };

  const closeSettings = () => {
    if (configSaving) return;
    setConfigOpen(false);
    setConfigError("");
    setConfigHelpKey(null);
  };

  const fetchConfig = async () => {
    setConfigLoading(true);
    setConfigError("");
    try {
      const res = await fetch(`${BACKEND_URL}/config`);
      if (!res.ok) {
        await reportResponseError(res, "Failed to load settings");
        setConfigError("Failed to load settings.");
        return;
      }
      const data = await res.json();
      setConfigDraft(normalizeConfigPayload(data));
    } catch (e) {
      console.error("Failed to load settings", e);
      setConfigError(e instanceof Error ? e.message : "Failed to load settings");
    } finally {
      setConfigLoading(false);
    }
  };

  const updateWorkflowStepLimit = (raw) => {
    const parsed = parsePositiveInt(raw);
    if (!parsed) return;
    setConfigDraft((prev) => {
      if (!prev) return prev;
      return { ...prev, workflow_step_limit: parsed };
    });
  };

  const updateAgentField = (agentName, field, value) => {
    setConfigDraft((prev) => {
      if (!prev || !prev.agents || !prev.agents[agentName]) return prev;
      return {
        ...prev,
        agents: {
          ...prev.agents,
          [agentName]: {
            ...prev.agents[agentName],
            [field]: value,
          },
        },
      };
    });
  };

  const applyWorkerGroup = () => {
    if (!configDraft?.agents) return;
    const nextModel = workerGroup.model || null;
    const nextVerbosity = workerGroup.verbosity || null;
    const nextStepLimit = parsePositiveInt(workerGroup.step_limit);

    setConfigDraft((prev) => {
      if (!prev || !prev.agents) return prev;
      const agents = { ...prev.agents };
      WORKER_AGENTS.forEach((agentName) => {
        const agentCfg = agents[agentName];
        if (!agentCfg) return;
        agents[agentName] = {
          ...agentCfg,
          ...(nextModel ? { model: nextModel } : {}),
          ...(nextVerbosity ? { verbosity: nextVerbosity } : {}),
          ...(agentCfg.supports_step_limit && nextStepLimit
            ? { step_limit: nextStepLimit }
            : {}),
        };
      });
      return { ...prev, agents };
    });
  };

  const saveConfig = async () => {
    if (!configDraft || configSaving || isAnyRunActive) return;
    setConfigSaving(true);
    setConfigError("");
    try {
      const res = await fetch(`${BACKEND_URL}/config`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ config: configDraft }),
      });
      if (!res.ok) {
        await reportResponseError(res, "Failed to save settings");
        setConfigError("Failed to save settings.");
        return;
      }
      const data = await res.json();
      setConfigDraft(normalizeConfigPayload(data));
    } catch (e) {
      console.error("Failed to save settings", e);
      setConfigError(e instanceof Error ? e.message : "Failed to save settings");
    } finally {
      setConfigSaving(false);
    }
  };

  const getFilenameFromDisposition = (disposition) => {
    if (!disposition) return null;
    const quotedMatch = disposition.match(/filename="([^"]+)"/i);
    if (quotedMatch) return quotedMatch[1].trim();
    const plainMatch = disposition.match(/filename=([^;]+)/i);
    if (plainMatch) return plainMatch[1].trim();
    return null;
  };

  const downloadResponse = async (res, fallbackName) => {
    if (!res.ok) {
      await reportResponseError(res, "Failed to download");
      return false;
    }
    const blob = await res.blob();
    const headerName = getFilenameFromDisposition(
      res.headers.get("content-disposition")
    );
    const filename = headerName || fallbackName || "download";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return true;
  };

  const downloadFromEndpoint = async (url, fallbackName) => {
    const res = await fetch(url);
    return downloadResponse(res, fallbackName);
  };

  const fetchRuns = async (options = {}) => {
    const { selectLatest = false } = options;
    try {
      const res = await fetch(`${BACKEND_URL}/runs`);
      if (!res.ok) {
        await reportResponseError(res, "Failed to load runs");
        return [];
      }
      const data = await res.json();
      const sortedRuns = (data.runs ?? [])
        .slice()
        .sort(
          (a, b) =>
            new Date(b.last_updated_at).getTime() - new Date(a.last_updated_at).getTime()
        );
      setRuns(sortedRuns);
      if (selectLatest) {
        setSelectedThreadId(sortedRuns[0]?.thread_id ?? null);
      }
      return sortedRuns;
    } catch (e) {
      console.error("Failed to load runs", e);
      setError(e instanceof Error ? e.message : "Failed to load runs");
      return [];
    }
  };

  const startRenameRun = (run) => {
    if (!run) return;
    setEditingRunId(run.thread_id);
    setEditingRunName(run.name || "");
    setRunMenu((prev) => ({ ...prev, open: false }));
  };

  const submitRenameRun = async (threadId) => {
    if (!threadId) return;
    const trimmed = editingRunName.trim();
    try {
      const res = await fetch(`${BACKEND_URL}/runs/rename`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          thread_id: threadId,
          name: trimmed === "" ? null : trimmed,
        }),
      });
      if (!res.ok) {
        await reportResponseError(res, "Failed to rename run");
        return;
      }
      await fetchRuns();
    } catch (e) {
      console.error("Failed to rename run", e);
      setError(e instanceof Error ? e.message : "Failed to rename run");
    } finally {
      setEditingRunId(null);
      setEditingRunName("");
    }
  };

  const handleDeleteRun = async (run) => {
    if (!run) return;
    const label = formatRunLabel(run);
    const confirmed = window.confirm(`Delete run "${label}"?`);
    if (!confirmed) return;
    try {
      const res = await fetch(`${BACKEND_URL}/runs/delete`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          thread_id: run.thread_id,
        }),
      });
      if (!res.ok) {
        await reportResponseError(res, "Failed to delete run");
        return;
      }
      if (run.thread_id === selectedThreadId) {
        setSelectedThreadId(null);
        setMessages([]);
      }
      await fetchRuns();
    } catch (e) {
      console.error("Failed to delete run", e);
      setError(e instanceof Error ? e.message : "Failed to delete run");
    } finally {
      setRunMenu((prev) => ({ ...prev, open: false }));
    }
  };

  const openRunDetails = async (run) => {
    if (!run) return;
    setRunMenu((prev) => ({ ...prev, open: false }));
    setRunDetailsOpen(true);
    setRunDetails(null);
    setRunDetailsError("");
    setRunDetailsLoading(true);
    try {
      const res = await fetch(
        `${BACKEND_URL}/runs/info?thread_id=${encodeURIComponent(run.thread_id)}`
      );
      if (!res.ok) {
        await reportResponseError(res, "Failed to load run info");
        setRunDetailsError("Failed to load run details.");
        return;
      }
      const data = await res.json();
      setRunDetails(data);
    } catch (e) {
      console.error("Failed to load run info", e);
      setRunDetailsError("Failed to load run details.");
      setError(e instanceof Error ? e.message : "Failed to load run details");
    } finally {
      setRunDetailsLoading(false);
    }
  };

  const closeRunDetails = () => {
    setRunDetailsOpen(false);
    setRunDetails(null);
    setRunDetailsError("");
  };

  const openExportRun = (run) => {
    if (!run) return;
    setRunMenu((prev) => ({ ...prev, open: false }));
    setExportRun(run);
    setExportOptions({ image: false, output: false });
    setExportRunOpen(true);
  };

  const closeExportRun = () => {
    if (isExporting) return;
    setExportRunOpen(false);
    setExportRun(null);
  };

  const handleExportRun = async () => {
    if (!exportRun || isExporting) return;
    setIsExporting(true);
    setError("");
    try {
      const threadId = exportRun.thread_id;
      const bundleOk = await downloadFromEndpoint(
        `${BACKEND_URL}/runs/export/run?thread_id=${encodeURIComponent(threadId)}`,
        `run_${threadId}.madrun`
      );
      if (!bundleOk) return;
      if (exportOptions.image) {
        const imageOk = await downloadFromEndpoint(
          `${BACKEND_URL}/runs/export/image`,
          "madagents_image_overlay.zip"
        );
        if (!imageOk) return;
      }
      if (exportOptions.output) {
        const outputOk = await downloadFromEndpoint(
          `${BACKEND_URL}/runs/export/output`,
          "madagents_output.zip"
        );
        if (!outputOk) return;
      }
      setExportRunOpen(false);
      setExportRun(null);
    } catch (e) {
      console.error("Failed to export run", e);
      setError(e instanceof Error ? e.message : "Failed to export run");
    } finally {
      setIsExporting(false);
    }
  };

  const handleImportRunFile = async (file) => {
    if (!file || isImporting) return;
    setIsImporting(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${BACKEND_URL}/runs/import`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        await reportResponseError(res, "Failed to import run");
        return;
      }
      const data = await res.json();
      const threadId = data?.thread_id ?? null;
      await fetchRuns();
      if (threadId) {
        setSelectedThreadId(threadId);
        setMessages([]);
        setPendingRunId(null);
        streamErrorRef.current = false;
        setError("");
      }
    } catch (e) {
      console.error("Failed to import run", e);
      setError(e instanceof Error ? e.message : "Failed to import run");
    } finally {
      setIsImporting(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  useEffect(() => {
    if (!selectedThreadId || selectedThreadId === "-1") return;
    if (runs.length === 0) return;
    const exists = runs.some((run) => run.thread_id === selectedThreadId);
    if (!exists) {
      if (pendingRunId && selectedThreadId === pendingRunId) {
        return;
      }
      setSelectedThreadId(null);
      setMessages([]);
    } else if (pendingRunId && selectedThreadId === pendingRunId) {
      setPendingRunId(null);
    }
  }, [runs, selectedThreadId, pendingRunId]);

  useEffect(() => {
    setRewindEditIndex(null);
    setRewindError("");
    if (rewindTextRef.current) {
      rewindTextRef.current.value = "";
    }
  }, [selectedThreadId]);

  useEffect(() => {
    if (!runMenu.open) return;
    const handleClose = () => {
      setRunMenu((prev) => ({ ...prev, open: false }));
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        handleClose();
      }
    };
    window.addEventListener("mousedown", handleClose);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handleClose);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [runMenu.open]);

  useEffect(() => {
    if (!configHelpKey) return;
    const handleClose = (event) => {
      const target = event.target;
      if (target?.closest?.('[data-config-help="true"]')) {
        return;
      }
      setConfigHelpKey(null);
    };
    window.addEventListener("mousedown", handleClose);
    return () => {
      window.removeEventListener("mousedown", handleClose);
    };
  }, [configHelpKey]);

  useEffect(() => {
    if (!runDetailsOpen) return;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        closeRunDetails();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [runDetailsOpen]);

  useEffect(() => {
    if (!costDetailsOpen) return;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        closeCostDetails();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [costDetailsOpen]);

  useEffect(() => {
    if (!exportRunOpen) return;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        closeExportRun();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [exportRunOpen, isExporting]);

  useEffect(() => {
    let cancelled = false;
    const loadHistory = async () => {
      if (!selectedThreadId) {
        closeEventSource();
        setIsHistoryLoading(false);
        return;
      }
      if (selectedThreadId === "-1") {
        closeEventSource();
        setIsHistoryLoading(false);
        fetch(`${BACKEND_URL}/history?thread_id=-1`).catch(() => {});
        return;
      }

      if (skipHistoryRef.current) {
        skipHistoryRef.current = false;
        const cursor = loadStoredCursor(selectedThreadId);
        eventCursorRef.current = cursor;
        connectEventSource(selectedThreadId, cursor);
        setIsHistoryLoading(false);
        return;
      }

      setIsHistoryLoading(true);
      try {
        const res = await fetch(
          `${BACKEND_URL}/history?thread_id=${encodeURIComponent(
            selectedThreadId
          )}&force_refresh=1`
        );
        if (!res.ok) {
          if (res.status === 404) {
            let detail = "";
            try {
              const errData = await res.json();
              if (typeof errData?.detail === "string") {
                detail = errData.detail;
              }
            } catch (e) {
              detail = "";
            }
            if (detail === "Run not found") {
              setSelectedThreadId("-1");
              setMessages([]);
              setError("");
              return;
            }
            const message = detail
              ? `Failed to load history: ${detail}`
              : `Failed to load history (${res.status})`;
            setError(message);
            return;
          }
          await reportResponseError(res, "Failed to load history");
          return;
        }
        const data = await res.json();
        if (!cancelled) {
          setMessages(data.messages ?? []);
          setRewindStatusByThread((prev) => ({
            ...prev,
            [selectedThreadId]: data.rewind_status || "pending",
          }));
          shouldRecalcAutoScrollRef.current = true;
        }
        const cursor = Number(data.event_cursor);
        const storedCursor = loadStoredCursor(selectedThreadId);
        const nextCursor = Number.isFinite(cursor) ? cursor : storedCursor;
        eventCursorRef.current = nextCursor;
        storeCursor(selectedThreadId, nextCursor);
        if (!cancelled) {
          connectEventSource(selectedThreadId, nextCursor);
        }
      } catch (e) {
        console.error("Failed to load history", e);
        setError(e instanceof Error ? e.message : "Failed to load history");
      } finally {
        if (!cancelled) {
          setIsHistoryLoading(false);
        }
      }
    };
    loadHistory();
    return () => {
      cancelled = true;
      closeEventSource();
    };
  }, [selectedThreadId]);

  // Track whether user is near the bottom
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    const handleScroll = () => {
      const threshold = 50; // px tolerance
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      const isAtBottom = distanceFromBottom < threshold;
      setAutoScroll(isAtBottom);
    };

    el.addEventListener("scroll", handleScroll);
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (!shouldRecalcAutoScrollRef.current) return;
    shouldRecalcAutoScrollRef.current = false;
    const el = scrollContainerRef.current;
    if (!el) return;
    const threshold = 50;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoScroll(distanceFromBottom < threshold);
  }, [messages]);

  // Auto-scroll on new messages if user was at bottom
  useEffect(() => {
    if (!autoScroll) return;
    const el = scrollContainerRef.current;
    if (!el) return;

    el.scrollTo({
      top: el.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isLoading, autoScroll]);

  const interruptRun = async () => {
    if (!canInterrupt) return;
    try {
      const res = await fetch(`${BACKEND_URL}/interrupt`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ thread_id: currentThreadKey }),
      });
      if (!res.ok) {
        await reportResponseError(res, "Failed to interrupt run");
      }
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const startRewindEdit = (message) => {
    if (!message || typeof message.message_index !== "number") {
      return;
    }
    setRewindEditIndex(message.message_index);
    setRewindError("");
    if (rewindTextRef.current) {
      rewindTextRef.current.value =
        typeof message.content === "string" ? message.content : "";
    }
  };

  const cancelRewindEdit = () => {
    setRewindEditIndex(null);
    setRewindError("");
    if (rewindTextRef.current) {
      rewindTextRef.current.value = "";
    }
  };

  const confirmRewindEdit = async (message) => {
    if (!message || typeof message.message_index !== "number") {
      return;
    }
    if (rewindDisabled || isRewinding) {
      return;
    }
    const threadId = selectedThreadId;
    if (!threadId || threadId === "-1") {
      setRewindError("Select a run before rewinding.");
      return;
    }
    const draft =
      rewindTextRef.current && typeof rewindTextRef.current.value === "string"
        ? rewindTextRef.current.value
        : "";
    const trimmed = draft.trim();
    if (!trimmed) {
      setRewindError("Message cannot be empty.");
      return;
    }

    setIsRewinding(true);
    setRewindError("");
    setError("");
    streamErrorRef.current = false;
    try {
      const res = await fetch(`${BACKEND_URL}/rewind`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          thread_id: threadId,
          message_index: message.message_index,
          new_message: trimmed,
        }),
      });
      if (res.status === 409) {
        let data = null;
        try {
          data = await res.json();
        } catch (err) {
          console.error(err);
        }
        const detail = data?.detail ?? data ?? {};
        const activeThreadId = detail.active_thread_id ?? null;
        const activeName = detail.active_run_name ?? null;
        if (activeThreadId) {
          setActiveRun({ threadId: activeThreadId, name: activeName });
        }
        const busyLabel =
          (activeName && String(activeName).trim()) || activeThreadId || "another run";
        setRewindError(`Run ${busyLabel} is already running.`);
        return;
      }
      if (!res.ok) {
        await reportResponseError(res, "Failed to rewind");
        return;
      }
      setRewindEditIndex(null);
      setRewindError("");
      if (rewindTextRef.current) {
        rewindTextRef.current.value = "";
      }
      setThreadLoading(threadId, true);
      // Reload history so the UI updates even if SSE is delayed or disconnected.
      if (threadId === selectedThreadId) {
        await reloadHistory(threadId);
      }
    } catch (err) {
      console.error(err);
      setRewindError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsRewinding(false);
    }
  };

  const sendMessage = async (prompt) => {
    if (isLoading) return;
    if (blockNewMessages) return;
    if (!prompt.trim()) return;

    setRewindEditIndex(null);
    setRewindError("");
    if (rewindTextRef.current) {
      rewindTextRef.current.value = "";
    }

    const threadId = selectedThreadId ?? "-1";
    const isNewRun = threadId === "-1";

    const userMessage = { name: "user", content: prompt };
    setMessages((prev) => [...prev, userMessage]);

    streamErrorRef.current = false;
    setError("");
    setThreadLoading(threadId, true);

    try {
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          thread_id: threadId,
          message: prompt,
        }),
      });

      if (res.status === 409) {
        let data = null;
        try {
          data = await res.json();
        } catch (err) {
          console.error(err);
        }
        const detail = data?.detail ?? data ?? {};
        const activeThreadId = detail.active_thread_id ?? null;
        const activeName = detail.active_run_name ?? null;
        if (activeThreadId) {
          setActiveRun({ threadId: activeThreadId, name: activeName });
        }
        const busyLabel =
          (activeName && String(activeName).trim()) || activeThreadId || "another run";
        setError(`Run ${busyLabel} is already running.`);
        setThreadLoading(threadId, false);
        return;
      }
      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }
      const data = await res.json();
      const nextThreadId = data?.thread_id || threadId;
      if (isNewRun) {
        skipHistoryRef.current = true;
        eventCursorRef.current = 0;
        storeCursor(nextThreadId, 0);
        setSelectedThreadId(nextThreadId);
        setPendingRunId(nextThreadId);
        fetchRuns();
        moveThreadLoading(threadId, nextThreadId);
      }
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : String(err));
      setThreadLoading(threadId, false);
    }
  };

  const decoratedMessages = useMemo(() => {
    let lastPlanMetaMap = null;
    let lastPlanStatusMap = null;

    return messages.map((message) => {
      const addContent = message?.add_content || {};
      const plan = addContent.plan;
      const planMetaData = addContent.plan_meta_data;
      const hasPlan = Boolean(plan && Array.isArray(plan.steps));
      const hasMetaData = Boolean(planMetaData && Array.isArray(planMetaData.steps));

      if (!hasPlan || !hasMetaData) {
        return message;
      }

      const { updatedSteps, metaMap, statusMap } = getUpdatedPlanSteps(
        plan,
        planMetaData,
        lastPlanMetaMap,
        lastPlanStatusMap
      );
      lastPlanMetaMap = metaMap;
      lastPlanStatusMap = statusMap;

      return {
        ...message,
        add_content: {
          ...addContent,
          plan_update_steps: updatedSteps,
        },
      };
    });
  }, [messages]);

  // Group consecutive agent exec_trace messages, keeping each agent separate.
  const processedMessages = useMemo(() => {
    const result = [];
    let i = 0;
    const isAgentName = (name) =>
      Boolean(name) && name !== "user" && name !== "assistant" && name !== "orchestrator";
    const isOrchestratorToUser = (recipient) =>
      recipient === "user" || recipient === "end_user" || recipient === "";

    while (i < decoratedMessages.length) {
      const m = decoratedMessages[i];

      // 1) orchestrator -> agent group
      if (m.name === "orchestrator") {
        const addContent = m.add_content || {};
        const recipient = addContent.recipient || "";

        if (!isOrchestratorToUser(recipient) && isAgentName(recipient)) {
          const instructionMessage = addContent.message ? addContent.message : m.content;
          const instruction = {
            recipient,
            reasoning: addContent.reasoning || "",
            message: instructionMessage,
            reasoning_effort: addContent.reasoning_effort || "",
            future_note: addContent.future_note || "",
          };

          i++;
          const traces = [];

          while (
            i < decoratedMessages.length &&
            decoratedMessages[i].name === recipient &&
            decoratedMessages[i].add_content &&
            decoratedMessages[i].add_content.exec_trace
          ) {
            traces.push(decoratedMessages[i]);
            i++;
          }

          let mainMessage = null;
          if (
            i < decoratedMessages.length &&
            decoratedMessages[i].name === recipient &&
            (!decoratedMessages[i].add_content ||
              !decoratedMessages[i].add_content.exec_trace)
          ) {
            mainMessage = decoratedMessages[i];
            i++;
          }

          result.push({
            type: "agentOpGroup",
            agentName: recipient,
            traces,
            mainMessage,
            instruction,
          });
          continue;
        }
      }

      // 2) agent group
      if (isAgentName(m.name)) {
        const agentName = m.name;
        const traces = [];

        while (
          i < decoratedMessages.length &&
          decoratedMessages[i].name === agentName &&
          decoratedMessages[i].add_content &&
          decoratedMessages[i].add_content.exec_trace
        ) {
          traces.push(decoratedMessages[i]);
          i++;
        }

        let mainMessage = null;
        if (
          i < decoratedMessages.length &&
          decoratedMessages[i].name === agentName &&
          (!decoratedMessages[i].add_content ||
            !decoratedMessages[i].add_content.exec_trace)
        ) {
          mainMessage = decoratedMessages[i];
          i++;
        }

        result.push({
          type: "agentOpGroup",
          agentName,
          traces,
          mainMessage,
        });
        continue;
      }

      // 3) everything else → plain message
      result.push({ type: "message", message: m });
      i++;
    }

    return result;
  }, [decoratedMessages]);

  return (
    <div
      style={{
        height: "100vh",
        width: "100vw",
        display: "flex",
        flexDirection: "column",
        background: theme.appBg,
        padding: "1rem",
        boxSizing: "border-box",
        color: theme.text,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          flex: 1,
          width: "100%",
          display: "flex",
          gap: "1rem",
          flexWrap: "wrap",
          minHeight: 0,
        }}
      >
        <aside
          style={{
            flex: "0 0 240px",
            width: "240px",
            maxWidth: "100%",
            maxHeight: "calc(100vh - 2rem)",
            minHeight: 0,
            background: theme.cardBg,
            borderRadius: "1rem",
            boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
            display: "flex",
            flexDirection: "column",
            padding: "1rem",
            gap: "0.75rem",
            overflow: "hidden",
          }}
        >
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              onClick={() => {
                setSelectedThreadId("-1");
                setMessages([]);
                setPendingRunId(null);
                streamErrorRef.current = false;
                setError("");
              }}
              style={{
                flex: 1,
                fontSize: "0.9rem",
                borderRadius: "0.75rem",
                border: `1px solid ${theme.border}`,
                padding: "0.6rem 0.75rem",
                background: "transparent",
                color: theme.text,
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              + New run
            </button>
            <button
              type="button"
              onClick={() => importInputRef.current?.click()}
              disabled={isImporting}
              style={{
                flex: 1,
                fontSize: "0.9rem",
                borderRadius: "0.75rem",
                border: `1px solid ${theme.border}`,
                padding: "0.6rem 0.75rem",
                background: "transparent",
                color: theme.text,
                cursor: isImporting ? "not-allowed" : "pointer",
                textAlign: "left",
                opacity: isImporting ? 0.7 : 1,
              }}
            >
              {isImporting ? "Importing..." : "Import run"}
            </button>
            <input
              ref={importInputRef}
              type="file"
              accept=".madrun"
              style={{ display: "none" }}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) {
                  handleImportRunFile(file);
                }
              }}
            />
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "0.5rem",
              overflowY: "auto",
              flex: 1,
              minHeight: 0,
            }}
          >
            {runs.length === 0 && (
              <div style={{ fontSize: "0.85rem", opacity: 0.6 }}>No runs yet.</div>
            )}
            {runs.map((run) => {
              const label = formatRunLabel(run);
              const isSelected = run.thread_id === selectedThreadId;
              const isEditing = run.thread_id === editingRunId;
              return (
                <button
                  key={run.thread_id}
                  type="button"
                  onClick={() => {
                    setSelectedThreadId(run.thread_id);
                    streamErrorRef.current = false;
                    setError("");
                    setPendingRunId(null);
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setRunMenu({
                      open: true,
                      x: e.clientX,
                      y: e.clientY,
                      run,
                    });
                  }}
                  style={{
                    textAlign: "left",
                    border: isSelected ? "1px solid #2563eb" : `1px solid ${theme.border}`,
                    borderRadius: "0.75rem",
                    padding: "0.6rem 0.75rem",
                    background: isSelected ? "rgba(37, 99, 235, 0.12)" : "transparent",
                    color: theme.text,
                    cursor: "pointer",
                    boxShadow: isSelected
                      ? "0 0 0 2px rgba(37, 99, 235, 0.2)"
                      : "none",
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.85rem",
                      fontWeight: isSelected ? 600 : 500,
                    }}
                  >
                    {isEditing ? (
                      <input
                        type="text"
                        value={editingRunName}
                        autoFocus
                        onChange={(e) => setEditingRunName(e.target.value)}
                        onBlur={() => submitRenameRun(run.thread_id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            submitRenameRun(run.thread_id);
                          } else if (e.key === "Escape") {
                            e.preventDefault();
                            setEditingRunId(null);
                            setEditingRunName("");
                          }
                        }}
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          width: "100%",
                          fontSize: "0.85rem",
                          fontFamily: "inherit",
                          padding: "0.2rem 0.4rem",
                          borderRadius: "0.4rem",
                          border: `1px solid ${theme.border}`,
                          outline: "none",
                          background: theme.cardBg,
                          color: theme.text,
                        }}
                      />
                    ) : (
                      label
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        <div
          style={{
            flex: "1 1 520px",
            minWidth: "320px",
            maxHeight: "calc(100vh - 2rem)",
            minHeight: 0,
            background: theme.cardBg,
            borderRadius: "1rem",
            boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            fontSize: "1.1rem",
          }}
        >
          <header
            style={{
              padding: "1rem 1.25rem",
              borderBottom: `1px solid ${theme.headerBorder}`,
              fontWeight: 600,
              fontSize: "1.25rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span>MadAgents</span>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <button
                type="button"
                onClick={openSettings}
                title="Settings"
                aria-label="Settings"
                style={{
                  borderRadius: "999px",
                  border: `1px solid ${theme.border}`,
                  padding: "0.35rem",
                  background: "transparent",
                  color: theme.text,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.8 1.8 0 0 0 .36 1.98l.04.04a2 2 0 1 1-2.83 2.83l-.04-.04a1.8 1.8 0 0 0-1.98-.36 1.8 1.8 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.05a1.8 1.8 0 0 0-1-1.6 1.8 1.8 0 0 0-1.98.36l-.04.04a2 2 0 1 1-2.83-2.83l.04-.04a1.8 1.8 0 0 0 .36-1.98 1.8 1.8 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.05a1.8 1.8 0 0 0 1.6-1 1.8 1.8 0 0 0-.36-1.98l-.04-.04a2 2 0 1 1 2.83-2.83l.04.04a1.8 1.8 0 0 0 1.98.36 1.8 1.8 0 0 0 1-1.6V3a2 2 0 1 1 4 0v.05a1.8 1.8 0 0 0 1 1.6 1.8 1.8 0 0 0 1.98-.36l.04-.04a2 2 0 1 1 2.83 2.83l-.04.04a1.8 1.8 0 0 0-.36 1.98 1.8 1.8 0 0 0 1.6 1H21a2 2 0 1 1 0 4h-.05a1.8 1.8 0 0 0-1.6 1Z" />
                </svg>
              </button>
              <button
                type="button"
                onClick={() => setDarkMode((v) => !v)}
                title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
                aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
                style={{
                  fontSize: "0.85rem",
                  borderRadius: "999px",
                  border: `1px solid ${theme.border}`,
                  padding: "0.35rem 0.75rem",
                  background: "transparent",
                  color: theme.text,
                  cursor: "pointer",
                }}
              >
                {darkMode ? "☀️ Light" : "🌙 Dark"}
              </button>
            </div>
          </header>

          <MessageList
            processedMessages={processedMessages}
            theme={theme}
            loading={isLoading}
            error={error}
            scrollContainerRef={scrollContainerRef}
            isHistoryLoading={isHistoryLoading}
            selectedThreadId={selectedThreadId}
            rewindStatus={currentRewindStatus}
            rewindEditIndex={rewindEditIndex}
            rewindError={rewindError}
            isRewinding={isRewinding}
            rewindDisabled={rewindDisabled}
            onStartRewind={startRewindEdit}
            onCancelRewind={cancelRewindEdit}
            onConfirmRewind={confirmRewindEdit}
            rewindTextRef={rewindTextRef}
          />

          {blockNewMessages && (
            <div
              style={{
                padding: "0.5rem 1rem 0",
                fontSize: "0.85rem",
                color: theme.text,
                opacity: 0.85,
              }}
            >
              Run <strong>{activeRunLabel}</strong> is running. Finish or interrupt it
              before submitting a new task.
            </div>
          )}

          <MessageComposer
            theme={theme}
            isLoading={isLoading}
            canInterrupt={canInterrupt}
            blockNewMessages={blockNewMessages}
            onSend={sendMessage}
            onInterrupt={interruptRun}
            onClearError={() => {
              if (error) {
                streamErrorRef.current = false;
                setError("");
              }
            }}
          />
        </div>
      </div>

      {runMenu.open && (
        <div
          onClick={(e) => e.stopPropagation()}
          onContextMenu={(e) => e.preventDefault()}
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            position: "fixed",
            top: runMenu.y,
            left: runMenu.x,
            zIndex: 50,
            background: theme.cardBg,
            border: `1px solid ${theme.border}`,
            borderRadius: "0.6rem",
            boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
            display: "flex",
            flexDirection: "column",
            minWidth: "180px",
            overflow: "hidden",
          }}
        >
          <button
            type="button"
            onClick={() => startRenameRun(runMenu.run)}
            style={{
              border: "none",
              background: "transparent",
              color: theme.text,
              textAlign: "left",
              padding: "0.6rem 0.85rem",
              cursor: "pointer",
              fontSize: "0.9rem",
            }}
          >
            Change name
          </button>
          <button
            type="button"
            onClick={() => handleDeleteRun(runMenu.run)}
            style={{
              border: "none",
              borderTop: `1px solid ${theme.border}`,
              background: "transparent",
              color: theme.text,
              textAlign: "left",
              padding: "0.6rem 0.85rem",
              cursor: "pointer",
              fontSize: "0.9rem",
            }}
          >
            Delete run
          </button>
          <button
            type="button"
            onClick={() => openExportRun(runMenu.run)}
            style={{
              border: "none",
              borderTop: `1px solid ${theme.border}`,
              background: "transparent",
              color: theme.text,
              textAlign: "left",
              padding: "0.6rem 0.85rem",
              cursor: "pointer",
              fontSize: "0.9rem",
            }}
          >
            Export run
          </button>
          <div
            style={{
              borderTop: `1px solid ${theme.border}`,
              margin: "0.1rem 0",
            }}
          />
          <button
            type="button"
            onClick={() => openRunDetails(runMenu.run)}
            style={{
              border: "none",
              background: "transparent",
              color: theme.text,
              textAlign: "left",
              padding: "0.6rem 0.85rem",
              cursor: "pointer",
              fontSize: "0.9rem",
            }}
          >
            Show details
          </button>
        </div>
      )}

      <SettingsModal
        open={configOpen}
        onClose={closeSettings}
        theme={theme}
        configDraft={configDraft}
        configLoading={configLoading}
        configSaving={configSaving}
        configError={configError}
        configHelpKey={configHelpKey}
        setConfigHelpKey={setConfigHelpKey}
        workerGroup={workerGroup}
        setWorkerGroup={setWorkerGroup}
        applyWorkerGroup={applyWorkerGroup}
        updateWorkflowStepLimit={updateWorkflowStepLimit}
        updateAgentField={updateAgentField}
        parsePositiveInt={parsePositiveInt}
        saveConfig={saveConfig}
        isAnyRunActive={isAnyRunActive}
        activeRunLabel={activeRunLabel}
      />

      <RunDetailsModal
        open={runDetailsOpen}
        onClose={closeRunDetails}
        theme={theme}
        runDetails={runDetails}
        runDetailsLoading={runDetailsLoading}
        runDetailsError={runDetailsError}
        openCostDetails={openCostDetails}
      />

      <ExportRunModal
        open={exportRunOpen}
        onClose={closeExportRun}
        theme={theme}
        exportRun={exportRun}
        exportOptions={exportOptions}
        setExportOptions={setExportOptions}
        isExporting={isExporting}
        onConfirm={handleExportRun}
        formatRunLabel={formatRunLabel}
      />

      <CostDetailsModal
        open={costDetailsOpen}
        onClose={closeCostDetails}
        theme={theme}
        runDetails={runDetails}
      />
    </div>
  );
}

export default App;
