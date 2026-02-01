import React from "react";
import {
  REASONING_EFFORT_LEVELS,
  SUPPORTED_MODELS,
  VERBOSITY_LEVELS,
  WORKER_AGENTS,
  darkTheme,
} from "../../lib/constants";
import { formatRecipientLabel } from "../../lib/formatters";

const configHelpText = {
  workflow_step_limit:
    "Maximum number of internal decision steps while handling a single user message. The counter resets for each new user message. If the limit is reached, the run stops and an error is shown.",
  model: "Selects which language model this agent will use.",
  verbosity: "Controls how detailed the agent’s responses tend to be.",
  step_limit:
    "Maximum number of internal cycles this agent may take when it is selected to act. In each cycle, the agent may call one or more tools and then continue. The counter resets the next time this agent is selected. If the limit is reached, the run stops and an error is shown.",
  reasoning_effort:
    "Controls how much internal reasoning effort the model uses per response.",
  summarizer_token_threshold:
    "Summaries are created when the conversation grows beyond this size.",
  summarizer_keep_last:
    "Number of most recent messages kept verbatim instead of summarized.",
  summarizer_min_tail_tokens:
    "Minimum token budget reserved for recent messages before summarizing older content.",
  summarizer_settings:
    "The summarizer first keeps the last N messages verbatim. If a response includes multiple tool calls, it still counts as one message. Then it keeps additional recent messages until it reaches the “Keep recent tokens” budget. Everything older than that is summarized.",
};

/**
 * Settings modal for configuring agent model/verbosity and summarization.
 */
export default function SettingsModal({
  theme,
  open,
  onClose,
  configDraft,
  configLoading,
  configSaving,
  configError,
  configHelpKey,
  setConfigHelpKey,
  workerGroup,
  setWorkerGroup,
  applyWorkerGroup,
  updateWorkflowStepLimit,
  updateAgentField,
  parsePositiveInt,
  saveConfig,
  isAnyRunActive,
  activeRunLabel,
}) {
  if (!open) return null;

  const toggleConfigHelp = (key) => {
    setConfigHelpKey((prev) => (prev === key ? null : key));
  };

  const renderHelpButton = (id, label, helpKey, options = {}) => (
    <span data-config-help="true" style={{ position: "relative", display: "inline-flex" }}>
      <button
        type="button"
        onClick={() => toggleConfigHelp(id)}
        title={`Explain ${label}`}
        aria-label={`Explain ${label}`}
        style={{
          marginLeft: "0.35rem",
          border: `1px solid ${theme.border}`,
          background: "transparent",
          color: theme.text,
          borderRadius: "999px",
          width: "1.1rem",
          height: "1.1rem",
          fontSize: "0.7rem",
          lineHeight: 1,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          opacity: 0.7,
        }}
      >
        ?
      </button>
      {configHelpKey === id && configHelpText[helpKey] && (
        <div
          data-config-help="true"
          style={{
            position: "absolute",
            top: "1.5rem",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 10,
            minWidth: options.minWidth || "220px",
            maxWidth: options.maxWidth || "280px",
            padding: "0.5rem 0.6rem",
            borderRadius: "0.5rem",
            border: `1px solid ${theme.border}`,
            background: theme.cardBg,
            fontSize: "0.8rem",
            color: theme.text,
            boxShadow: "0 12px 24px rgba(0,0,0,0.18)",
            whiteSpace: "normal",
          }}
        >
          {configHelpText[helpKey]}
        </div>
      )}
    </span>
  );

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 70,
        background: "rgba(15, 23, 42, 0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(900px, 96vw)",
          background: theme.cardBg,
          borderRadius: "0.9rem",
          border: `1px solid ${theme.border}`,
          boxShadow: "0 20px 40px rgba(0,0,0,0.35)",
          display: "flex",
          flexDirection: "column",
          maxHeight: "90vh",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "1rem 1.25rem",
            borderBottom: `1px solid ${theme.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1rem",
          }}
        >
          <div style={{ fontSize: "1rem", fontWeight: 600 }}>Settings</div>
          <button
            type="button"
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              color: theme.text,
              fontSize: "1.1rem",
              cursor: "pointer",
            }}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div
          style={{
            padding: "1rem 1.25rem",
            overflowY: "auto",
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: "0.85rem",
          }}
        >
          {configLoading && (
            <div style={{ fontSize: "0.9rem", opacity: 0.8 }}>Loading settings...</div>
          )}

          {!configLoading && configError && (
            <div
              style={{
                fontSize: "0.9rem",
                color: theme === darkTheme ? "#fca5a5" : "#b91c1c",
              }}
            >
              {configError}
            </div>
          )}

          {!configLoading && configDraft && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div
                style={{
                  padding: "0.9rem",
                  borderRadius: "0.85rem",
                  border: `1px solid ${theme.border}`,
                }}
              >
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "170px 1fr",
                    gap: "0.65rem",
                    alignItems: "center",
                    fontSize: "0.9rem",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", opacity: 0.75 }}>
                    <span>Workflow step limit</span>
                    {renderHelpButton(
                      "workflow_step_limit",
                      "workflow step limit",
                      "workflow_step_limit"
                    )}
                  </div>
                  <input
                    type="number"
                    min="1"
                    value={configDraft.workflow_step_limit ?? ""}
                    onChange={(e) => updateWorkflowStepLimit(e.target.value)}
                    style={{
                      width: "100%",
                      maxWidth: "240px",
                      fontSize: "0.9rem",
                      fontFamily: "inherit",
                      padding: "0.4rem 0.6rem",
                      borderRadius: "0.5rem",
                      border: `1px solid ${theme.border}`,
                      outline: "none",
                      background: theme.inputBg,
                      color: theme.text,
                    }}
                  />
                </div>
              </div>

              <div
                style={{
                  padding: "0.9rem",
                  borderRadius: "0.85rem",
                  border: `1px solid ${theme.border}`,
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem",
                }}
              >
                <div style={{ fontSize: "0.95rem", fontWeight: 600 }}>Controlling agents</div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "170px 1fr 1fr 1fr",
                    gap: "0.5rem",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ opacity: 0.7 }}>Agent</div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ opacity: 0.7 }}>Model</span>
                    {renderHelpButton("model_controlling", "model", "model")}
                  </div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ opacity: 0.7 }}>Verbosity</span>
                    {renderHelpButton("verbosity_controlling", "verbosity", "verbosity")}
                  </div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ opacity: 0.7 }}>Step limit</span>
                    {renderHelpButton("step_limit_controlling", "step limit", "step_limit")}
                  </div>
                </div>
                {["orchestrator", "planner", "plan_updater", "reviewer"]
                  .filter((name) => configDraft.agents?.[name])
                  .map((agentName) => {
                    const cfg = configDraft.agents[agentName];
                    return (
                      <div
                        key={agentName}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "170px 1fr 1fr 1fr",
                          gap: "0.5rem",
                          alignItems: "center",
                        }}
                      >
                        <div style={{ fontWeight: 600 }}>
                          {formatRecipientLabel(agentName)}
                        </div>
                        <select
                          value={cfg.model}
                          onChange={(e) => updateAgentField(agentName, "model", e.target.value)}
                          style={{
                            padding: "0.4rem 0.6rem",
                            borderRadius: "0.5rem",
                            border: `1px solid ${theme.border}`,
                            background: theme.inputBg,
                            color: theme.text,
                            fontSize: "0.85rem",
                          }}
                        >
                          {SUPPORTED_MODELS.map((model) => (
                            <option key={model} value={model}>
                              {model}
                            </option>
                          ))}
                        </select>
                        <select
                          value={cfg.verbosity}
                          onChange={(e) =>
                            updateAgentField(agentName, "verbosity", e.target.value)
                          }
                          style={{
                            padding: "0.4rem 0.6rem",
                            borderRadius: "0.5rem",
                            border: `1px solid ${theme.border}`,
                            background: theme.inputBg,
                            color: theme.text,
                            fontSize: "0.85rem",
                          }}
                        >
                          {VERBOSITY_LEVELS.map((level) => (
                            <option key={level} value={level}>
                              {level}
                            </option>
                          ))}
                        </select>
                        {cfg.supports_step_limit ? (
                          <input
                            type="number"
                            min="1"
                            value={cfg.step_limit ?? ""}
                            onChange={(e) => {
                              const parsed = parsePositiveInt(e.target.value);
                              if (!parsed) return;
                              updateAgentField(agentName, "step_limit", parsed);
                            }}
                            style={{
                              padding: "0.4rem 0.6rem",
                              borderRadius: "0.5rem",
                              border: `1px solid ${theme.border}`,
                              background: theme.inputBg,
                              color: theme.text,
                              fontSize: "0.85rem",
                            }}
                          />
                        ) : (
                          <div style={{ opacity: 0.6 }}>—</div>
                        )}
                      </div>
                    );
                  })}
              </div>

              <div
                style={{
                  padding: "0.9rem",
                  borderRadius: "0.85rem",
                  border: `1px solid ${theme.border}`,
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem",
                }}
              >
                <div style={{ fontSize: "0.95rem", fontWeight: 600 }}>Worker agents</div>
                <div
                  style={{
                    padding: "0.6rem",
                    borderRadius: "0.6rem",
                    border: `1px dashed ${theme.border}`,
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.5rem",
                  }}
                >
                  <div style={{ fontSize: "0.8rem", opacity: 0.7 }}>
                    Apply these settings to all worker agents.
                  </div>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr 1fr auto",
                      gap: "0.5rem",
                      alignItems: "center",
                    }}
                  >
                    <select
                      value={workerGroup.model}
                      onChange={(e) =>
                        setWorkerGroup((prev) => ({
                          ...prev,
                          model: e.target.value,
                        }))
                      }
                      style={{
                        padding: "0.4rem 0.6rem",
                        borderRadius: "0.5rem",
                        border: `1px solid ${theme.border}`,
                        background: theme.inputBg,
                        color: theme.text,
                        fontSize: "0.85rem",
                      }}
                    >
                      <option value="">Model (no change)</option>
                      {SUPPORTED_MODELS.map((model) => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                    </select>
                    <select
                      value={workerGroup.verbosity}
                      onChange={(e) =>
                        setWorkerGroup((prev) => ({
                          ...prev,
                          verbosity: e.target.value,
                        }))
                      }
                      style={{
                        padding: "0.4rem 0.6rem",
                        borderRadius: "0.5rem",
                        border: `1px solid ${theme.border}`,
                        background: theme.inputBg,
                        color: theme.text,
                        fontSize: "0.85rem",
                      }}
                    >
                      <option value="">Verbosity (no change)</option>
                      {VERBOSITY_LEVELS.map((level) => (
                        <option key={level} value={level}>
                          {level}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min="1"
                      placeholder="Step limit (no change)"
                      value={workerGroup.step_limit}
                      onChange={(e) =>
                        setWorkerGroup((prev) => ({
                          ...prev,
                          step_limit: e.target.value,
                        }))
                      }
                      style={{
                        padding: "0.4rem 0.6rem",
                        borderRadius: "0.5rem",
                        border: `1px solid ${theme.border}`,
                        background: theme.inputBg,
                        color: theme.text,
                        fontSize: "0.85rem",
                      }}
                    />
                    <button
                      type="button"
                      onClick={applyWorkerGroup}
                      title="Apply the selected options to all worker agents."
                      aria-label="Apply to all worker agents"
                      style={{
                        padding: "0.45rem 0.75rem",
                        borderRadius: "0.5rem",
                        border: `1px solid ${theme.border}`,
                        background: "transparent",
                        color: theme.text,
                        cursor: "pointer",
                        fontSize: "0.85rem",
                      }}
                    >
                      Apply
                    </button>
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "170px 1fr 1fr 1fr",
                    gap: "0.5rem",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ opacity: 0.7 }}>Agent</div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ opacity: 0.7 }}>Model</span>
                    {renderHelpButton("model_workers", "model", "model")}
                  </div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ opacity: 0.7 }}>Verbosity</span>
                    {renderHelpButton("verbosity_workers", "verbosity", "verbosity")}
                  </div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ opacity: 0.7 }}>Step limit</span>
                    {renderHelpButton("step_limit_workers", "step limit", "step_limit")}
                  </div>
                </div>
                {WORKER_AGENTS.filter((name) => configDraft.agents?.[name]).map((agentName) => {
                  const cfg = configDraft.agents[agentName];
                  return (
                    <div
                      key={agentName}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "170px 1fr 1fr 1fr",
                        gap: "0.5rem",
                        alignItems: "center",
                      }}
                    >
                      <div style={{ fontWeight: 600 }}>
                        {formatRecipientLabel(agentName)}
                      </div>
                      <select
                        value={cfg.model}
                        onChange={(e) => updateAgentField(agentName, "model", e.target.value)}
                        style={{
                          padding: "0.4rem 0.6rem",
                          borderRadius: "0.5rem",
                          border: `1px solid ${theme.border}`,
                          background: theme.inputBg,
                          color: theme.text,
                          fontSize: "0.85rem",
                        }}
                      >
                        {SUPPORTED_MODELS.map((model) => (
                          <option key={model} value={model}>
                            {model}
                          </option>
                        ))}
                      </select>
                      <select
                        value={cfg.verbosity}
                        onChange={(e) =>
                          updateAgentField(agentName, "verbosity", e.target.value)
                        }
                        style={{
                          padding: "0.4rem 0.6rem",
                          borderRadius: "0.5rem",
                          border: `1px solid ${theme.border}`,
                          background: theme.inputBg,
                          color: theme.text,
                          fontSize: "0.85rem",
                        }}
                      >
                        {VERBOSITY_LEVELS.map((level) => (
                          <option key={level} value={level}>
                            {level}
                          </option>
                        ))}
                      </select>
                      <input
                        type="number"
                        min="1"
                        value={cfg.step_limit ?? ""}
                        onChange={(e) => {
                          const parsed = parsePositiveInt(e.target.value);
                          if (!parsed) return;
                          updateAgentField(agentName, "step_limit", parsed);
                        }}
                        style={{
                          padding: "0.4rem 0.6rem",
                          borderRadius: "0.5rem",
                          border: `1px solid ${theme.border}`,
                          background: theme.inputBg,
                          color: theme.text,
                          fontSize: "0.85rem",
                        }}
                      />
                    </div>
                  );
                })}
              </div>

              <div
                style={{
                  padding: "0.9rem",
                  borderRadius: "0.85rem",
                  border: `1px solid ${theme.border}`,
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem",
                }}
              >
                <div style={{ fontSize: "0.95rem", fontWeight: 600 }}>
                  Conversation summarization
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "170px 1fr 1fr 1fr",
                    gap: "0.5rem",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ opacity: 0.7 }}>Agent</div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ opacity: 0.7 }}>Model</span>
                    {renderHelpButton("model_summarizer", "model", "model")}
                  </div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ opacity: 0.7 }}>Verbosity</span>
                    {renderHelpButton("verbosity_summarizer", "verbosity", "verbosity")}
                  </div>
                  <div style={{ display: "flex", alignItems: "center" }}>
                    <span style={{ opacity: 0.7 }}>Reasoning effort</span>
                    {renderHelpButton(
                      "reasoning_summarizer",
                      "reasoning effort",
                      "reasoning_effort"
                    )}
                  </div>
                </div>
                {configDraft.agents?.summarizer && (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "170px 1fr 1fr 1fr",
                      gap: "0.5rem",
                      alignItems: "center",
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>
                      {formatRecipientLabel("summarizer")}
                    </div>
                    <select
                      value={configDraft.agents.summarizer.model}
                      onChange={(e) => updateAgentField("summarizer", "model", e.target.value)}
                      style={{
                        padding: "0.4rem 0.6rem",
                        borderRadius: "0.5rem",
                        border: `1px solid ${theme.border}`,
                        background: theme.inputBg,
                        color: theme.text,
                        fontSize: "0.85rem",
                      }}
                    >
                      {SUPPORTED_MODELS.map((model) => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                    </select>
                    <select
                      value={configDraft.agents.summarizer.verbosity}
                      onChange={(e) =>
                        updateAgentField("summarizer", "verbosity", e.target.value)
                      }
                      style={{
                        padding: "0.4rem 0.6rem",
                        borderRadius: "0.5rem",
                        border: `1px solid ${theme.border}`,
                        background: theme.inputBg,
                        color: theme.text,
                        fontSize: "0.85rem",
                      }}
                    >
                      {VERBOSITY_LEVELS.map((level) => (
                        <option key={level} value={level}>
                          {level}
                        </option>
                      ))}
                    </select>
                    <select
                      value={configDraft.agents.summarizer.reasoning_effort ?? "low"}
                      onChange={(e) =>
                        updateAgentField("summarizer", "reasoning_effort", e.target.value)
                      }
                      style={{
                        padding: "0.4rem 0.6rem",
                        borderRadius: "0.5rem",
                        border: `1px solid ${theme.border}`,
                        background: theme.inputBg,
                        color: theme.text,
                        fontSize: "0.85rem",
                      }}
                    >
                      {REASONING_EFFORT_LEVELS.map((level) => (
                        <option key={level} value={level}>
                          {level}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {configDraft.agents?.summarizer && (
                  <div
                    style={{
                      marginTop: "0.35rem",
                      paddingTop: "0.6rem",
                      borderTop: `1px dashed ${theme.border}`,
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.6rem",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "0.85rem",
                        fontWeight: 600,
                        display: "flex",
                        alignItems: "center",
                      }}
                    >
                      <span>Summary settings</span>
                      {renderHelpButton(
                        "summarizer_settings",
                        "summary settings",
                        "summarizer_settings",
                        { minWidth: "320px", maxWidth: "420px" }
                      )}
                    </div>
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "210px 1fr",
                        gap: "0.45rem 0.6rem",
                        alignItems: "center",
                        fontSize: "0.85rem",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center" }}>
                        <span style={{ opacity: 0.7 }}>Summarize after (tokens)</span>
                      </div>
                      <input
                        type="number"
                        min="1"
                        value={configDraft.agents.summarizer.token_threshold ?? ""}
                        onChange={(e) => {
                          const parsed = parsePositiveInt(e.target.value);
                          if (!parsed) return;
                          updateAgentField("summarizer", "token_threshold", parsed);
                        }}
                        style={{
                          width: "100%",
                          maxWidth: "240px",
                          fontSize: "0.85rem",
                          fontFamily: "inherit",
                          padding: "0.35rem 0.5rem",
                          borderRadius: "0.45rem",
                          border: `1px solid ${theme.border}`,
                          outline: "none",
                          background: theme.inputBg,
                          color: theme.text,
                        }}
                      />
                      <div style={{ display: "flex", alignItems: "center" }}>
                        <span style={{ opacity: 0.7 }}>Keep last messages</span>
                      </div>
                      <input
                        type="number"
                        min="1"
                        value={configDraft.agents.summarizer.keep_last_messages ?? ""}
                        onChange={(e) => {
                          const parsed = parsePositiveInt(e.target.value);
                          if (!parsed) return;
                          updateAgentField("summarizer", "keep_last_messages", parsed);
                        }}
                        style={{
                          width: "100%",
                          maxWidth: "240px",
                          fontSize: "0.85rem",
                          fontFamily: "inherit",
                          padding: "0.35rem 0.5rem",
                          borderRadius: "0.45rem",
                          border: `1px solid ${theme.border}`,
                          outline: "none",
                          background: theme.inputBg,
                          color: theme.text,
                        }}
                      />
                      <div style={{ display: "flex", alignItems: "center" }}>
                        <span style={{ opacity: 0.7 }}>Keep recent tokens</span>
                      </div>
                      <input
                        type="number"
                        min="1"
                        value={configDraft.agents.summarizer.min_tail_tokens ?? ""}
                        onChange={(e) => {
                          const parsed = parsePositiveInt(e.target.value);
                          if (!parsed) return;
                          updateAgentField("summarizer", "min_tail_tokens", parsed);
                        }}
                        style={{
                          width: "100%",
                          maxWidth: "240px",
                          fontSize: "0.85rem",
                          fontFamily: "inherit",
                          padding: "0.35rem 0.5rem",
                          borderRadius: "0.45rem",
                          border: `1px solid ${theme.border}`,
                          outline: "none",
                          background: theme.inputBg,
                          color: theme.text,
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            padding: "0.85rem 1.25rem",
            borderTop: `1px solid ${theme.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.8rem",
          }}
        >
          {isAnyRunActive && (
            <div
              style={{
                fontSize: "0.85rem",
                color: theme.text,
                opacity: 0.85,
              }}
            >
              Run <strong>{activeRunLabel}</strong> is running. Finish or interrupt it
              before saving settings.
            </div>
          )}
          <div style={{ marginLeft: "auto", display: "flex", gap: "0.6rem" }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                border: `1px solid ${theme.border}`,
                background: "transparent",
                color: theme.text,
                borderRadius: "0.6rem",
                padding: "0.45rem 0.9rem",
                cursor: "pointer",
              }}
            >
              Close
            </button>
            <button
              type="button"
              onClick={saveConfig}
              disabled={configSaving || isAnyRunActive}
              style={{
                border: "none",
                background: isAnyRunActive ? theme.border : "rgba(37, 99, 235, 0.9)",
                color: "#fff",
                borderRadius: "0.6rem",
                padding: "0.45rem 0.9rem",
                cursor: configSaving || isAnyRunActive ? "not-allowed" : "pointer",
                opacity: configSaving ? 0.7 : 1,
              }}
            >
              {configSaving ? "Saving..." : "Save settings"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
