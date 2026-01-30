import React from "react";
import { darkTheme } from "../../lib/constants";
import { formatApproxCost, formatCostNote, formatRunTimestamp } from "../../lib/formatters";

/**
 * Modal showing metadata and cost breakdown for a run.
 */
export default function RunDetailsModal({
  open,
  onClose,
  theme,
  runDetails,
  runDetailsLoading,
  runDetailsError,
  openCostDetails,
}) {
  if (!open) return null;

  const detailLabelStyle = {
    opacity: 0.7,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  };

  const detailSeparatorStyle = {
    opacity: 0.45,
    textAlign: "center",
  };

  const renderDetailRow = (label, value, valueStyle) => (
    <>
      <div style={detailLabelStyle}>{label}</div>
      <div style={detailSeparatorStyle}>:</div>
      <div style={valueStyle}>{value}</div>
    </>
  );

  const renderDetailSeparator = () => (
    <div
      style={{
        gridColumn: "1 / -1",
        borderTop: `1px solid ${theme.border}`,
        margin: "0.25rem 0 0.15rem",
      }}
    />
  );

  const renderCostRow = (label, value) => {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return null;
    }
    return renderDetailRow(label, formatApproxCost(value));
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
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
          width: "min(640px, 92vw)",
          background: theme.cardBg,
          borderRadius: "0.9rem",
          border: `1px solid ${theme.border}`,
          boxShadow: "0 20px 40px rgba(0,0,0,0.35)",
          padding: "1rem 1.25rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.85rem",
          maxHeight: "85vh",
          overflowY: "auto",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1rem",
          }}
        >
          <div style={{ fontSize: "1rem", fontWeight: 600 }}>Run details</div>
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

        {runDetailsLoading && (
          <div style={{ fontSize: "0.9rem", opacity: 0.8 }}>
            Loading run details...
          </div>
        )}

        {!runDetailsLoading && runDetailsError && (
          <div
            style={{
              fontSize: "0.9rem",
              color: theme === darkTheme ? "#fca5a5" : "#b91c1c",
            }}
          >
            {runDetailsError}
          </div>
        )}

        {!runDetailsLoading && !runDetailsError && runDetails && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(170px, max-content) 0.6rem 1fr",
              gap: "0.45rem 0.65rem",
              fontSize: "0.9rem",
            }}
          >
            {renderDetailRow("Name", runDetails.name?.trim() || "Unnamed run")}

            {renderDetailRow("Thread ID", runDetails.thread_id || "—", {
              fontFamily:
                "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace",
            })}

            {renderDetailRow("Workdir", runDetails.workdir || "—", {
              fontFamily:
                "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace",
            })}

            {renderDetailRow("Created", formatRunTimestamp(runDetails.created_at))}

            {renderDetailRow("Last updated", formatRunTimestamp(runDetails.last_updated_at))}

            {renderDetailSeparator()}

            {(() => {
              const baseCost = formatApproxCost(runDetails.estimated_cost_usd);
              const note = formatCostNote(runDetails.estimated_cost_note);
              const mainValue =
                typeof runDetails.estimated_cost_usd === "number" && note
                  ? `${baseCost} - ${note}`
                  : baseCost;
              const hasAgentBreakdown =
                runDetails.estimated_cost_by_agent &&
                Object.keys(runDetails.estimated_cost_by_agent).length > 0;
              return (
                <>
                  <div
                    style={{
                      ...detailLabelStyle,
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <span>Approx. cost</span>
                    {hasAgentBreakdown && (
                      <button
                        type="button"
                        onClick={openCostDetails}
                        style={{
                          border: `1px solid ${theme.border}`,
                          background: theme.inputBg,
                          color: theme.text,
                          borderRadius: "0.5rem",
                          fontSize: "0.75rem",
                          padding: "0.1rem 0.35rem",
                          cursor: "pointer",
                          lineHeight: 1,
                        }}
                        title="Cost details"
                        aria-label="Cost details"
                      >
                        ⓘ
                      </button>
                    )}
                  </div>
                  <div style={detailSeparatorStyle}>:</div>
                  <div>{mainValue}</div>
                </>
              );
            })()}

            {runDetails.estimated_cost_breakdown && (
              <>
                {renderCostRow("Output (total)", runDetails.estimated_cost_breakdown.output_cost_usd)}
                {renderCostRow(
                  "Output (reasoning)",
                  runDetails.estimated_cost_breakdown.output_reasoning_cost_usd
                )}
                {renderCostRow(
                  "Output (answer)",
                  runDetails.estimated_cost_breakdown.output_actual_cost_usd
                )}
                {renderCostRow(
                  "Cached input",
                  runDetails.estimated_cost_breakdown.cached_input_cost_usd
                )}
                {renderCostRow(
                  "Input (non-cached)",
                  runDetails.estimated_cost_breakdown.input_cost_usd
                )}
                {renderCostRow(
                  "Web search",
                  runDetails.estimated_cost_breakdown.web_search_cost_usd
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
