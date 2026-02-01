import React, { useState } from "react";
import { darkTheme } from "../lib/constants";
import { getRecipientDisplayName, stripControlChars } from "../lib/formatters";
import MarkdownBubble from "./MarkdownBubble";
import ReplyAccordion from "./ReplyAccordion";
import OrchestratorReasoningBlock from "./OrchestratorReasoningBlock";
import {
  PlanCard,
  PlanUpdatesCard,
  renderPlanLabel,
  renderPlanUpdateLabel,
} from "./PlanCard";

/**
 * Render grouped agent traces and final replies with optional instruction header.
 */
export default function AgentOpGroup({ group, theme }) {
  const [open, setOpen] = useState(false);
  const { traces, mainMessage } = group;
  const agentName = group.agentName || "undefined agent";
  const normalizedAgentName = agentName.toLowerCase();
  const openMainReplyByDefault =
    normalizedAgentName === "planner" || normalizedAgentName === "plan_updater";
  const instruction = group.instruction || null;
  const instructionMessage = instruction?.message ?? "";
  const instructionReasoning = instruction?.reasoning ?? "";
  const instructionFutureNote =
    typeof instruction?.future_note === "string"
      ? stripControlChars(instruction.future_note)
      : "";
  const instructionRecipient = getRecipientDisplayName(
    instruction?.recipient || agentName
  );
  const instructionEffort = instruction?.reasoning_effort ?? "";
  const hasInstruction = Boolean(
    instructionMessage ||
      instructionReasoning ||
      instructionFutureNote.trim().length > 0
  );
  const plannerPlan = mainMessage?.add_content?.plan;
  const hasPlannerPlan = Boolean(plannerPlan && Array.isArray(plannerPlan.steps));
  const showPlannerPlan =
    normalizedAgentName === "planner" || normalizedAgentName === "plan_updater";
  const planUpdateSteps = Array.isArray(mainMessage?.add_content?.plan_update_steps)
    ? mainMessage.add_content.plan_update_steps
    : [];
  const showPlanUpdates =
    normalizedAgentName === "plan_updater" && planUpdateSteps.length > 0;

  const hasTraces = traces && traces.length > 0;

  const formatPayload = (payload) => {
    if (payload === null || payload === undefined) return "";
    if (typeof payload === "string") return stripControlChars(payload);
    try {
      return stripControlChars(JSON.stringify(payload, null, 2));
    } catch {
      return stripControlChars(String(payload));
    }
  };

  const parseArguments = (argumentsRaw) => {
    if (argumentsRaw === null || argumentsRaw === undefined) return null;
    if (typeof argumentsRaw === "object") return argumentsRaw;
    if (typeof argumentsRaw === "string") {
      try {
        return JSON.parse(argumentsRaw);
      } catch {
        return null;
      }
    }
    return null;
  };

  const getTraceCallId = (trace) => {
    const addContent = trace?.add_content || {};
    const raw = addContent.call_id || addContent.tool_call_id || addContent.id;
    if (typeof raw === "string" && raw.trim() !== "") {
      return raw;
    }
    return null;
  };

  const renderTraceBlock = (t, i, options = {}) => {
    const addContent = t.add_content || {};
    const tType = addContent.type;
    const suppressToolName = Boolean(options.suppressToolName);
    const renderCallLabel = (label) => (
      <span>
        Tool call
        {!suppressToolName ? (
          <>
            : <strong>{label}</strong>
          </>
        ) : null}
      </span>
    );
    const renderToolLabel = (label) => (
      <span>
        Tool result
        {!suppressToolName ? (
          <>
            : <strong>{label}</strong>
          </>
        ) : null}
      </span>
    );

    // TEXT trace → markdown
    if (tType === "text") {
      const text = addContent.content ?? t.content ?? "";
      return (
        <div key={i}>
          <MarkdownBubble isUser={false} theme={theme}>
            {text}
          </MarkdownBubble>
        </div>
      );
    }

    // FUNCTION_CALL trace -> show tool name and arguments
    if (tType === "function_call") {
      const callName = addContent.name || "tool";
      const args = parseArguments(addContent.arguments);
      const argsText = formatPayload(args ?? addContent.arguments);
      const waitValue =
        args && args.wait_s !== undefined && args.wait_s !== null
          ? String(args.wait_s)
          : "";
      const commands =
        args && typeof args.commands === "string" ? args.commands : "";
      const code = args && typeof args.code === "string" ? args.code : "";
      const pdfPath =
        args && typeof args.pdf_file_path === "string" ? args.pdf_file_path : "";
      const imagePath =
        args && typeof args.image_file_path === "string"
          ? args.image_file_path
          : "";
      const cliCommand =
        args && typeof args.command === "string" ? args.command : "";
      const hasArgs = argsText.trim() !== "";

      if (callName === "wait") {
        const minutesValue =
          args && args.minutes !== undefined && args.minutes !== null
            ? String(args.minutes)
            : "";
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("Wait")}
              {minutesValue && <span>{minutesValue} minutes</span>}
            </div>
          </div>
        );
      }

      if (callName === "apply_patch") {
        const operations = Array.isArray(args?.operations) ? args.operations : [];

        const languageForPath = (path) => {
          if (typeof path !== "string") return "";
          const lower = path.toLowerCase();
          if (lower.endsWith(".py")) return "python";
          if (lower.endsWith(".js")) return "javascript";
          if (lower.endsWith(".jsx")) return "jsx";
          if (lower.endsWith(".ts")) return "typescript";
          if (lower.endsWith(".tsx")) return "tsx";
          if (lower.endsWith(".json")) return "json";
          if (lower.endsWith(".yml") || lower.endsWith(".yaml")) return "yaml";
          if (lower.endsWith(".md")) return "markdown";
          if (lower.endsWith(".txt")) return "text";
          if (lower.endsWith(".sh") || lower.endsWith(".bash")) return "bash";
          if (lower.endsWith(".toml")) return "toml";
          if (lower.endsWith(".ini") || lower.endsWith(".cfg")) return "ini";
          if (lower.endsWith(".html")) return "html";
          if (lower.endsWith(".css")) return "css";
          if (lower.endsWith(".scss")) return "scss";
          if (lower.endsWith(".java")) return "java";
          if (lower.endsWith(".c")) return "c";
          if (lower.endsWith(".h")) return "c";
          if (lower.endsWith(".cpp") || lower.endsWith(".hpp")) return "cpp";
          if (lower.endsWith(".rs")) return "rust";
          if (lower.endsWith(".go")) return "go";
          if (lower.endsWith(".rb")) return "ruby";
          if (lower.endsWith(".php")) return "php";
          if (lower.endsWith(".xml")) return "xml";
          if (lower.endsWith(".csv")) return "csv";
          if (lower.endsWith(".sql")) return "sql";
          return "";
        };

        const extractCreateContent = (diffText) => {
          if (typeof diffText !== "string") return "";
          const lines = diffText.split("\n");
          const nonEmpty = lines.filter((line) => line !== "");
          const allPlus =
            nonEmpty.length > 0 && nonEmpty.every((line) => line.startsWith("+"));
          if (!allPlus) return diffText;
          return lines
            .map((line) => (line.startsWith("+") ? line.slice(1) : line))
            .join("\n");
        };

        const diffLinesFrom = (diffText) => {
          if (typeof diffText !== "string" || diffText.trim() === "") {
            return [];
          }
          return diffText.split("\n");
        };

        const getLineColor = (line) => {
          if (line.startsWith("+")) return "#22c55e";
          if (line.startsWith("-")) return "#f87171";
          if (line.startsWith("@@")) return "#94a3b8";
          return theme.text;
        };

        const formatTypeLabel = (value) => {
          if (value === "create_file") return "create_file";
          if (value === "update_file") return "update_file";
          if (value === "delete_file") return "delete_file";
          return value || "unknown";
        };

        const getTypeBadge = (value) => {
          if (value === "create_file") return "#22c55e";
          if (value === "update_file") return "#f59e0b";
          if (value === "delete_file") return "#ef4444";
          return theme.border;
        };

        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.5rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("Apply patch")}
              {operations.length > 0 && <span>{operations.length} operation(s)</span>}
            </div>

            {operations.length === 0 && (
              <div style={{ fontSize: "0.8rem" }}>No operations provided.</div>
            )}

            {operations.map((op, idxOp) => {
              const opType = op && typeof op.type === "string" ? op.type : "";
              const opPath = op && typeof op.path === "string" ? op.path : "";
              const diff = op && typeof op.diff === "string" ? op.diff : "";
              const diffLines = diffLinesFrom(diff);
              const isUpdate = opType === "update_file";
              const isCreate = opType === "create_file";
              const createContent = isCreate ? extractCreateContent(diff) : "";
              const language = languageForPath(opPath);

              return (
                <div
                  key={`${idxOp}-${opPath}`}
                  style={{
                    border: `1px solid ${theme.border}`,
                    borderRadius: "0.5rem",
                    padding: "0.5rem 0.6rem",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.35rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.45rem",
                      fontSize: "0.8rem",
                    }}
                  >
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: "0.15rem 0.4rem",
                        borderRadius: "999px",
                        background: getTypeBadge(opType),
                        color: "#ffffff",
                        fontSize: "0.7rem",
                        textTransform: "uppercase",
                        letterSpacing: "0.03em",
                      }}
                    >
                      {formatTypeLabel(opType)}
                    </span>
                    <span
                      style={{
                        fontFamily:
                          "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace",
                      }}
                    >
                      {opPath || "unknown path"}
                    </span>
                  </div>

                  {isUpdate && diffLines.length > 0 && (
                    <details open>
                      <summary
                        style={{
                          cursor: "pointer",
                          fontSize: "0.8rem",
                          opacity: 0.8,
                        }}
                      >
                        File diff
                      </summary>
                      <div
                        style={{
                          borderRadius: "0.4rem",
                          background: "#111827",
                          padding: "0.4rem 0.6rem",
                          fontFamily:
                            "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace",
                          fontSize: "0.8rem",
                          marginTop: "0.4rem",
                        }}
                      >
                        {diffLines.map((line, idxLine) => (
                          <div
                            key={`${idxOp}-diff-${idxLine}`}
                            style={{
                              color: getLineColor(line),
                              whiteSpace: "pre",
                            }}
                          >
                            {line}
                          </div>
                        ))}
                      </div>
                    </details>
                  )}

                  {isCreate && (
                    <details open>
                      <summary
                        style={{
                          cursor: "pointer",
                          fontSize: "0.8rem",
                          opacity: 0.8,
                        }}
                      >
                        File content
                      </summary>
                      <pre
                        style={{
                          padding: "0.4rem 0.6rem",
                          borderRadius: "0.4rem",
                          overflowX: "auto",
                          background: "#111827",
                          fontSize: "0.8rem",
                          marginTop: "0.4rem",
                        }}
                      >
                        <code className={language ? `language-${language}` : ""}>
                          {createContent}
                        </code>
                      </pre>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        );
      }

      if (callName === "bash" && commands) {
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("Bash")}
            </div>
            <pre
              style={{
                padding: "0.4rem 0.6rem",
                borderRadius: "0.4rem",
                overflowX: "auto",
                background: "#111827",
                fontSize: "0.8rem",
              }}
            >
              <code className="language-bash">{commands}</code>
            </pre>
          </div>
        );
      }

      if (callName === "python" && code) {
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("Python")}
            </div>
            <pre
              style={{
                padding: "0.4rem 0.6rem",
                borderRadius: "0.4rem",
                overflowX: "auto",
                background: "#111827",
                fontSize: "0.8rem",
              }}
            >
              <code className="language-python">{code}</code>
            </pre>
          </div>
        );
      }

      if (callName === "save_answer") {
        const saveFilePath =
          args && typeof args.file_path === "string" ? args.file_path : "";
        const saveText = saveFilePath
          ? `Saving answer to ${saveFilePath}.`
          : "Saving answer.";
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div style={{ fontSize: "0.8rem" }}>{saveText}</div>
          </div>
        );
      }

      if (callName === "read_pdf" && pdfPath) {
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("Read PDF")}
            </div>
            <div style={{ fontSize: "0.8rem" }}>Opening the PDF file {pdfPath}</div>
          </div>
        );
      }

      if (callName === "read_image" && imagePath) {
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("Read image")}
            </div>
            <div style={{ fontSize: "0.8rem" }}>Opening the image file {imagePath}</div>
          </div>
        );
      }

      if (callName === "read_int_cli_output") {
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("Read CLI output")}
              {waitValue && <span>wait_s: {waitValue}</span>}
            </div>
            <div style={{ fontSize: "0.8rem" }}>Waiting for CLI output...</div>
          </div>
        );
      }

      if (callName === "read_int_cli_transcript") {
        const startLine =
          args && typeof args.start_line === "number" ? args.start_line : null;
        const endLine = args && typeof args.end_line === "number" ? args.end_line : null;
        const rangeText =
          startLine !== null || endLine !== null ? `${startLine ?? "?"}-${endLine ?? "?"}` : "";
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("CLI transcript")}
              {rangeText && <span>lines: {rangeText}</span>}
            </div>
            <div style={{ fontSize: "0.8rem" }}>Reading transcript lines...</div>
          </div>
        );
      }

      if (callName === "int_cli_status") {
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("CLI status")}
            </div>
            <div style={{ fontSize: "0.8rem" }}>Checking CLI status...</div>
          </div>
        );
      }

      if (callName === "run_int_cli_command" && cliCommand) {
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderCallLabel("Run CLI command")}
              {waitValue && <span>wait_s: {waitValue}</span>}
            </div>
            <pre
              style={{
                padding: "0.4rem 0.6rem",
                borderRadius: "0.4rem",
                overflowX: "auto",
                background: "#111827",
                fontSize: "0.8rem",
              }}
            >
              <code className="language-bash">{cliCommand}</code>
            </pre>
          </div>
        );
      }

      return (
        <div
          key={i}
          style={{
            borderRadius: "0.6rem",
            padding: "0.5rem 0.6rem",
            background: theme === darkTheme ? "#020617" : "#ffffff",
            border: `1px solid ${theme.border}`,
            display: "flex",
            flexDirection: "column",
            gap: "0.35rem",
          }}
        >
          <div
            style={{
              fontSize: "0.75rem",
              opacity: 0.75,
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            {renderCallLabel(callName)}
          </div>

          {hasArgs && (
            <div>
              <div
                style={{
                  fontSize: "0.75rem",
                  opacity: 0.7,
                  marginBottom: "0.15rem",
                }}
              >
                Arguments
              </div>
              <pre
                style={{
                  padding: "0.4rem 0.6rem",
                  borderRadius: "0.4rem",
                  overflowX: "auto",
                  background: "#111827",
                  fontSize: "0.8rem",
                }}
              >
                <code>{argsText}</code>
              </pre>
            </div>
          )}
        </div>
      );
    }

    // TOOL_MESSAGE trace → tool-specific render
    if (tType === "tool_message") {
      const toolName = addContent.name || "";
      const toolPayload = addContent.content;
      const isScriptTool = toolName === "python" || toolName === "bash";
      const isMadgraphTool =
        toolName === "run_int_cli_command" ||
        toolName === "read_int_cli_output" ||
        (toolPayload && (toolPayload.cli_input || toolPayload.cli_output));

      if (toolName === "save_answer") {
        const saveText = formatPayload(toolPayload);
        const hasText = saveText.trim() !== "";
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            {hasText && <div style={{ fontSize: "0.8rem" }}>{saveText}</div>}
          </div>
        );
      }

      if (toolName === "read_pdf") {
        const pdfText = formatPayload(toolPayload);
        const hasText = pdfText.trim() !== "";
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderToolLabel("Read PDF")}
            </div>

            {hasText && <div style={{ fontSize: "0.8rem" }}>{pdfText}</div>}
          </div>
        );
      }

      if (toolName === "read_image") {
        const imageText = formatPayload(toolPayload);
        const hasText = imageText.trim() !== "";
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderToolLabel("Read image")}
            </div>

            {hasText && <div style={{ fontSize: "0.8rem" }}>{imageText}</div>}
          </div>
        );
      }

      if (toolName === "wait") {
        const waitText = formatPayload(toolPayload);
        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderToolLabel("Wait")}
            </div>

            {waitText && <div style={{ fontSize: "0.8rem" }}>{waitText}</div>}
          </div>
        );
      }

      if (toolName === "int_cli_status") {
        const payload = toolPayload && typeof toolPayload === "object" ? toolPayload : {};
        const statusText =
          typeof payload.status === "string" ? payload.status : "CLI status";
        const contextText = typeof payload.context === "string" ? payload.context : "";
        const fallbackOutput = typeof toolPayload === "string" ? toolPayload : "";
        const newOutputText =
          typeof payload.new_output === "string" ? payload.new_output : fallbackOutput;
        const beforeCount =
          typeof payload.lines_before === "number" && Number.isFinite(payload.lines_before)
            ? payload.lines_before
            : null;
        const afterCount =
          typeof payload.lines_after === "number" && Number.isFinite(payload.lines_after)
            ? payload.lines_after
            : null;
        const countsText =
          beforeCount !== null || afterCount !== null
            ? `before: ${beforeCount ?? "?"} · after: ${afterCount ?? "?"}`
            : "";
        const hasContext = contextText.trim() !== "";
        const hasNewOutput = newOutputText.trim() !== "";

        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderToolLabel("CLI status")}
              {countsText && <span>{countsText}</span>}
            </div>

            {statusText && <div style={{ fontSize: "0.8rem" }}>{statusText}</div>}

            {hasContext && (
              <div>
                <div
                  style={{
                    fontSize: "0.75rem",
                    opacity: 0.7,
                    marginBottom: "0.15rem",
                  }}
                >
                  Context (last 10 lines)
                </div>
                <pre
                  style={{
                    padding: "0.4rem 0.6rem",
                    borderRadius: "0.4rem",
                    overflowX: "auto",
                    background: "#111827",
                    fontSize: "0.8rem",
                  }}
                >
                  <code>{contextText}</code>
                </pre>
              </div>
            )}

            {hasNewOutput && (
              <div>
                <div
                  style={{
                    fontSize: "0.75rem",
                    opacity: 0.7,
                    marginBottom: "0.15rem",
                  }}
                >
                  New output
                </div>
                <pre
                  style={{
                    padding: "0.4rem 0.6rem",
                    borderRadius: "0.4rem",
                    overflowX: "auto",
                    background: "#111827",
                    fontSize: "0.8rem",
                  }}
                >
                  <code>{newOutputText}</code>
                </pre>
              </div>
            )}
          </div>
        );
      }

      if (toolName === "read_int_cli_transcript") {
        const payload = toolPayload && typeof toolPayload === "object" ? toolPayload : {};
        const text = typeof payload.text === "string" ? payload.text : "";
        const startLine = typeof payload.start_line === "number" ? payload.start_line : null;
        const endLine = typeof payload.end_line === "number" ? payload.end_line : null;
        const rangeText =
          startLine !== null || endLine !== null ? `${startLine ?? "?"}-${endLine ?? "?"}` : "";
        const errorText = typeof payload.error === "string" ? payload.error : "";
        const hasText = text.trim() !== "";
        const hasError = errorText.trim() !== "";

        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderToolLabel("CLI transcript")}
              {rangeText && <span>lines: {rangeText}</span>}
            </div>

            {hasError && <div style={{ fontSize: "0.8rem" }}>{errorText}</div>}

            {hasText && (
              <pre
                style={{
                  padding: "0.4rem 0.6rem",
                  borderRadius: "0.4rem",
                  overflowX: "auto",
                  background: "#111827",
                  fontSize: "0.8rem",
                }}
              >
                <code>{text}</code>
              </pre>
            )}
          </div>
        );
      }

      if (toolName === "apply_patch") {
        const payload = toolPayload && typeof toolPayload === "object" ? toolPayload : {};
        const results = Array.isArray(payload.results) ? payload.results : [];
        const errors = results.filter((result) => result && result.status !== "completed");

        if (errors.length === 0) {
          return null;
        }

        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderToolLabel("Apply patch")}
              <span>{errors.length} error(s)</span>
            </div>

            {errors.length > 0 && (
              <div
                style={{
                  fontSize: "0.85rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.25rem",
                }}
              >
                {errors.map((err, idxErr) => {
                  const path = typeof err.path === "string" ? err.path : "unknown";
                  const type = typeof err.type === "string" ? err.type : "unknown";
                  const output =
                    typeof err.output === "string" ? err.output : "Unknown error";
                  return (
                    <div key={`apply-patch-err-${idxErr}`}>
                      {path} ({type}): {output}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      }

      if (isScriptTool) {
        const normalized = toolPayload && typeof toolPayload === "object" ? toolPayload : {};
        const {
          exit_code,
          stdout,
          stderr,
          timeout,
          pid,
          stdout_last_n,
          stderr_last_n,
          stdout_path,
          stderr_path,
        } = normalized;
        const responseWindowExceeded = Boolean(timeout);

        const parseLastN = (value) => {
          if (typeof value === "number" && Number.isFinite(value) && value > 0) {
            return value;
          }
          if (typeof value === "string") {
            const n = Number(value);
            if (Number.isFinite(n) && n > 0) return n;
          }
          return null;
        };

        const stdoutLastN = parseLastN(stdout_last_n);
        const stderrLastN = parseLastN(stderr_last_n);
        const stdoutText = stdout !== undefined && stdout !== null ? String(stdout) : "";
        const stderrText = stderr !== undefined && stderr !== null ? String(stderr) : "";
        const hasStdout = stdoutText.trim() !== "";
        const hasStderr = stderrText.trim() !== "";
        const hasStdoutPath =
          typeof stdout_path === "string" && stdout_path.trim() !== "";
        const hasStderrPath =
          typeof stderr_path === "string" && stderr_path.trim() !== "";

        const formatLastLabel = (label, count) => {
          if (count === 1) return `${label} (last line)`;
          return `${label} (last ${count} lines)`;
        };

        const responseWindowBadgeStyle = {
          fontSize: "0.7rem",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          padding: "0.15rem 0.45rem",
          borderRadius: 999,
          background: theme === darkTheme ? "rgba(245, 158, 11, 0.2)" : "#fffbeb",
          color: theme === darkTheme ? "#fbbf24" : "#92400e",
          border: `1px solid ${theme === darkTheme ? "#92400e" : "#fde68a"}`,
        };

        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderToolLabel(
                toolName === "python" ? "Python" : toolName === "bash" ? "Bash" : toolName
              )}
              {responseWindowExceeded ? (
                <span style={responseWindowBadgeStyle}>Response window exceeded</span>
              ) : (
                <span>exit code: {exit_code ?? "?"}</span>
              )}
            </div>

            {responseWindowExceeded && (
              <div style={{ fontSize: "0.8rem" }}>
                Response window exceeded. Process is still running
                {pid !== undefined && pid !== null ? ` (pid: ${String(pid)})` : ""}. Output
                continues to stream to the log files below.
              </div>
            )}

            {(hasStdoutPath || hasStderrPath) && (
              <div
                style={{
                  fontSize: "0.75rem",
                  opacity: 0.7,
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.15rem",
                }}
              >
                {hasStdoutPath && <div>stdout log: {stdout_path}</div>}
                {hasStderrPath && <div>stderr log: {stderr_path}</div>}
              </div>
            )}

            {hasStdout && (
              <div>
                <div
                  style={{
                    fontSize: "0.75rem",
                    opacity: 0.7,
                    marginBottom: "0.15rem",
                  }}
                >
                  {stdoutLastN ? formatLastLabel("Stdout", stdoutLastN) : "Stdout"}
                </div>
                <pre
                  style={{
                    padding: "0.4rem 0.6rem",
                    borderRadius: "0.4rem",
                    overflowX: "auto",
                    background: "#111827",
                    fontSize: "0.8rem",
                  }}
                >
                  <code>{stdoutText}</code>
                </pre>
                {stdoutLastN && hasStdoutPath && (
                  <div style={{ fontSize: "0.75rem", opacity: 0.7 }}>
                    Output truncated; full log at path above.
                  </div>
                )}
              </div>
            )}

            {!hasStdout && hasStdoutPath && (
              <div style={{ fontSize: "0.75rem", opacity: 0.7 }}>
                Output is still streaming; see log.
              </div>
            )}

            {hasStderr && (
              <div>
                <div
                  style={{
                    fontSize: "0.75rem",
                    opacity: 0.7,
                    marginBottom: "0.15rem",
                  }}
                >
                  {stderrLastN ? formatLastLabel("Stderr", stderrLastN) : "Stderr"}
                </div>
                <pre
                  style={{
                    padding: "0.4rem 0.6rem",
                    borderRadius: "0.4rem",
                    overflowX: "auto",
                    background: "#111827",
                    fontSize: "0.8rem",
                  }}
                >
                  <code>{stderrText}</code>
                </pre>
                {stderrLastN && hasStderrPath && (
                  <div style={{ fontSize: "0.75rem", opacity: 0.7 }}>
                    Output truncated; full log at path above.
                  </div>
                )}
              </div>
            )}

            {!hasStderr && hasStderrPath && (
              <div style={{ fontSize: "0.75rem", opacity: 0.7 }}>
                Output is still streaming; see log.
              </div>
            )}
          </div>
        );
      }

      if (isMadgraphTool) {
        const actionName = addContent.name || "";
        const payload = addContent.content || {};
        const cli_input = payload && typeof payload === "object" ? payload.cli_input : "";
        const cli_output =
          typeof payload === "string"
            ? payload
            : payload && typeof payload === "object"
              ? payload.cli_output
              : "";

        const hasCliInput = typeof cli_input === "string" && cli_input.trim() !== "";
        const outputText = cli_output ?? "";

        return (
          <div
            key={i}
            style={{
              borderRadius: "0.6rem",
              padding: "0.5rem 0.6rem",
              background: theme === darkTheme ? "#020617" : "#ffffff",
              border: `1px solid ${theme.border}`,
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {renderToolLabel("MadGraph CLI")}
              {actionName && <span>action: {actionName}</span>}
            </div>

            {hasCliInput && (
              <div>
                <div
                  style={{
                    fontSize: "0.75rem",
                    opacity: 0.7,
                    marginBottom: "0.15rem",
                  }}
                >
                  Command
                </div>
                <pre
                  style={{
                    padding: "0.4rem 0.6rem",
                    borderRadius: "0.4rem",
                    overflowX: "auto",
                    background: "#111827",
                    fontSize: "0.8rem",
                  }}
                >
                  <code className="language-bash">{cli_input}</code>
                </pre>
              </div>
            )}

            {
              <div>
                <div
                  style={{
                    fontSize: "0.75rem",
                    opacity: 0.7,
                    marginBottom: "0.15rem",
                  }}
                >
                  Output
                </div>
                <pre
                  style={{
                    padding: "0.4rem 0.6rem",
                    borderRadius: "0.4rem",
                    overflowX: "auto",
                    background: "#111827",
                    fontSize: "0.8rem",
                  }}
                >
                  <code className="language-bash">{outputText}</code>
                </pre>
              </div>
            }
          </div>
        );
      }

      const payloadText = formatPayload(toolPayload);
      const hasPayload = payloadText.trim() !== "";

      return (
        <div
          key={i}
          style={{
            borderRadius: "0.6rem",
            padding: "0.5rem 0.6rem",
            background: theme === darkTheme ? "#020617" : "#ffffff",
            border: `1px solid ${theme.border}`,
            display: "flex",
            flexDirection: "column",
            gap: "0.35rem",
          }}
        >
          <div
            style={{
              fontSize: "0.75rem",
              opacity: 0.75,
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            {renderToolLabel(toolName || "Unknown tool")}
          </div>

          {hasPayload && (
            <div>
              <div
                style={{
                  fontSize: "0.75rem",
                  opacity: 0.7,
                  marginBottom: "0.15rem",
                }}
              >
                Output
              </div>
              <pre
                style={{
                  padding: "0.4rem 0.6rem",
                  borderRadius: "0.4rem",
                  overflowX: "auto",
                  background: "#111827",
                  fontSize: "0.8rem",
                }}
              >
                <code>{payloadText}</code>
              </pre>
            </div>
          )}
        </div>
      );
    }

    // Fallback: just show content as markdown
    return (
      <div key={i}>
        <MarkdownBubble isUser={false} theme={theme}>
          {t.content || ""}
        </MarkdownBubble>
      </div>
    );
  };

  const buildTraceItems = () => {
    const pairs = new Map();

    traces.forEach((trace, idx) => {
      const addContent = trace.add_content || {};
      const tType = addContent.type;
      if (tType !== "function_call" && tType !== "tool_message") {
        return;
      }
      const callId = getTraceCallId(trace);
      if (!callId) {
        return;
      }
      const entry = pairs.get(callId) || { id: callId };
      if (tType === "function_call") {
        entry.call = trace;
        entry.callIndex = idx;
      } else if (tType === "tool_message") {
        entry.result = trace;
        entry.resultIndex = idx;
      }
      pairs.set(callId, entry);
    });

    const pairAtIndex = new Map();
    pairs.forEach((entry) => {
      if (!entry.call || !entry.result) {
        return;
      }
      const renderIndex = entry.callIndex ?? entry.resultIndex;
      if (renderIndex === null || renderIndex === undefined) {
        return;
      }
      if (!pairAtIndex.has(renderIndex)) {
        pairAtIndex.set(renderIndex, entry);
      }
    });

    const consumed = new Set();
    const items = [];

    for (let i = 0; i < traces.length; i++) {
      if (consumed.has(i)) continue;

      const entry = pairAtIndex.get(i);
      if (entry) {
        if (entry.callIndex !== null && entry.callIndex !== undefined) {
          consumed.add(entry.callIndex);
        }
        if (entry.resultIndex !== null && entry.resultIndex !== undefined) {
          consumed.add(entry.resultIndex);
        }

        const toolLabel =
          entry.call?.add_content?.name || entry.result?.add_content?.name || "Tool";
        const labelText =
          typeof toolLabel === "string" && toolLabel.trim() !== "" ? toolLabel : "Tool";

        items.push(
          <div
            key={`tool-pair-${entry.id}-${i}`}
            style={{
              borderRadius: "0.75rem",
              padding: "0.6rem 0.7rem",
              background: theme === darkTheme ? "rgba(15, 23, 42, 0.6)" : "#ffffff",
              border: `1px solid ${theme.border}`,
              boxShadow:
                theme === darkTheme
                  ? "0 0 0 1px rgba(255,255,255,0.04)"
                  : "0 1px 2px rgba(0,0,0,0.06)",
              display: "flex",
              flexDirection: "column",
              gap: "0.4rem",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                opacity: 0.7,
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <span>
                Tool: <strong>{labelText}</strong>
              </span>
            </div>
            {entry.call
              ? renderTraceBlock(entry.call, entry.callIndex ?? i, {
                  suppressToolName: true,
                })
              : null}
            {entry.result
              ? renderTraceBlock(entry.result, entry.resultIndex ?? i, {
                  suppressToolName: true,
                })
              : null}
          </div>
        );
        continue;
      }

      items.push(renderTraceBlock(traces[i], i));
    }

    return items;
  };

  return (
    <div
      style={{
        alignSelf: "flex-start",
        maxWidth: "80%",
        display: "flex",
        flexDirection: "column",
        gap: "0.25rem",
      }}
    >
      {hasInstruction && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "0.35rem",
          }}
        >
          <div
            style={{
              fontSize: "0.8rem",
              opacity: 0.75,
              marginLeft: "0.25rem",
              display: "flex",
              alignItems: "center",
              gap: "0.35rem",
            }}
          >
            <span style={{ fontWeight: 500 }}>
              {getRecipientDisplayName("orchestrator")}
            </span>
            <span style={{ opacity: 0.6 }}>→</span>
            <span>{instructionRecipient}</span>
            {instructionEffort && (
              <span style={{ fontSize: "0.7rem", opacity: 0.6 }}>
                effort: {instructionEffort}
              </span>
            )}
          </div>

          <OrchestratorReasoningBlock
            reasoning={instructionReasoning}
            futureNote={instructionFutureNote}
            theme={theme}
          />

          {instructionMessage && (
            <ReplyAccordion theme={theme} defaultOpen={false} label="Instruction">
              <MarkdownBubble isUser={false} theme={theme}>
                {instructionMessage}
              </MarkdownBubble>
            </ReplyAccordion>
          )}
        </div>
      )}

      {/* Foldable execution trace */}
      {hasTraces && (
        <div
          style={{
            borderRadius: "0.75rem",
            border: `1px solid ${theme.border}`,
            background: theme === darkTheme ? "#020617" : "rgba(249, 250, 251, 0.9)",
            padding: "0.5rem 0.75rem",
            fontSize: "0.8rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.35rem",
          }}
        >
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            style={{
              alignSelf: "flex-start",
              border: "none",
              background: "transparent",
              color: theme.text,
              cursor: "pointer",
              fontSize: "0.8rem",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              padding: 0,
            }}
          >
            <span>{open ? "▼" : "▶"}</span>
            <span>Execution trace ({traces.length})</span>
          </button>

          {open && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.4rem",
                marginTop: "0.25rem",
              }}
            >
              {buildTraceItems()}
            </div>
          )}
        </div>
      )}

      {/* Final agent message */}
      {mainMessage &&
        (showPlanUpdates ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
            <ReplyAccordion
              theme={theme}
              defaultOpen={openMainReplyByDefault}
              label={renderPlanUpdateLabel(planUpdateSteps, theme)}
            >
              <PlanUpdatesCard steps={planUpdateSteps} theme={theme} showStatusIcons={false} />
            </ReplyAccordion>
            {hasPlannerPlan && (
              <ReplyAccordion
                theme={theme}
                defaultOpen={false}
                label={renderPlanLabel(plannerPlan, theme, "Full plan")}
              >
                <PlanCard plan={plannerPlan} theme={theme} />
              </ReplyAccordion>
            )}
          </div>
        ) : (
          <ReplyAccordion
            theme={theme}
            defaultOpen={openMainReplyByDefault}
            label={
              showPlannerPlan && hasPlannerPlan
                ? renderPlanLabel(plannerPlan, theme)
                : "Reply"
            }
          >
            {showPlannerPlan && hasPlannerPlan ? (
              <PlanCard plan={plannerPlan} theme={theme} />
            ) : (
              <MarkdownBubble
                isUser={false}
                theme={theme}
                showCopy={true}
                copyText={formatPayload(mainMessage.content)}
              >
                {mainMessage.content}
              </MarkdownBubble>
            )}
          </ReplyAccordion>
        ))}
    </div>
  );
}
