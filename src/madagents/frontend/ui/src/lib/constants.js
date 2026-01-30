export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
export const SELECTED_THREAD_ID_KEY = "madagents_selected_thread_id";

// Theme tokens are shared across components to allow strict equality checks.
export const lightTheme = {
  appBg: "#f3f4f6",
  cardBg: "#ffffff",
  text: "#111827",
  userBubbleBg: "#2563eb",
  userBubbleText: "#ffffff",
  botBubbleBg: "#e5e7eb",
  botBubbleText: "#111827",
  headerBorder: "#e5e7eb",
  inputBg: "#f9fafb",
  border: "#d1d5db",
};

export const darkTheme = {
  appBg: "#020617",
  cardBg: "#020617",
  text: "#e5e7eb",
  userBubbleBg: "#2563eb",
  userBubbleText: "#ffffff",
  botBubbleBg: "#111827",
  botBubbleText: "#e5e7eb",
  headerBorder: "#1f2937",
  inputBg: "#020617",
  border: "#374151",
};

export const SUPPORTED_MODELS = [
  "gpt-5-nano",
  "gpt-5-mini",
  "gpt-5",
  "gpt-5.1",
  "gpt-5.2",
];

export const VERBOSITY_LEVELS = ["low", "medium", "high"];
export const REASONING_EFFORT_LEVELS = ["minimal", "low", "medium", "high"];

export const WORKER_AGENTS = [
  "madgraph_operator",
  "script_operator",
  "plotter",
  "user_cli_operator",
  "pdf_reader",
  "researcher",
];

export const AGENT_ORDER = [
  "orchestrator",
  "planner",
  "plan_updater",
  "summarizer",
  "reviewer",
  ...WORKER_AGENTS,
];

export const CONTROL_CHAR_REGEX =
  /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g;
