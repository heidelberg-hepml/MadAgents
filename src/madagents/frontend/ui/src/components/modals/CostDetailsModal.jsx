import React from "react";
import {
  formatApproxCost,
  formatCostNote,
  formatRecipientLabel,
} from "../../lib/formatters";

/**
 * Modal showing per-agent cost breakdown for a run.
 */
export default function CostDetailsModal({ open, onClose, theme, runDetails }) {
  if (!open) return null;

  const renderCostRow = (label, value) => {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return null;
    }
    return (
      <>
        <div style={{ opacity: 0.7 }}>{label}</div>
        <div style={{ opacity: 0.45, textAlign: "center" }}>:</div>
        <div>{formatApproxCost(value)}</div>
      </>
    );
  };

  const getAgentTotalCost = (breakdown) => {
    if (!breakdown) {
      return null;
    }
    const parts = [
      breakdown.cached_input_cost_usd,
      breakdown.input_cost_usd,
      breakdown.output_cost_usd,
      breakdown.web_search_cost_usd,
    ];
    if (!parts.some((value) => typeof value === "number" && Number.isFinite(value))) {
      return null;
    }
    return parts.reduce((sum, value) => {
      if (typeof value === "number" && Number.isFinite(value)) {
        return sum + value;
      }
      return sum;
    }, 0);
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
          width: "min(720px, 92vw)",
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
          <div style={{ fontSize: "1rem", fontWeight: 600 }}>Cost details</div>
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

        {runDetails?.estimated_cost_note && (
          <div style={{ fontSize: "0.85rem", opacity: 0.75 }}>
            {formatCostNote(runDetails.estimated_cost_note)}
          </div>
        )}

        {(!runDetails?.estimated_cost_by_agent ||
          Object.keys(runDetails.estimated_cost_by_agent).length === 0) && (
          <div style={{ fontSize: "0.9rem", opacity: 0.8 }}>Cost details unavailable.</div>
        )}

        {runDetails?.estimated_cost_by_agent &&
          Object.keys(runDetails.estimated_cost_by_agent).length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
              {Object.keys(runDetails.estimated_cost_by_agent)
                .sort()
                .map((agentKey) => {
                  const breakdown = runDetails.estimated_cost_by_agent[agentKey];
                  if (!breakdown) {
                    return null;
                  }
                  return (
                    <div
                      key={agentKey}
                      style={{
                        border: `1px solid ${theme.border}`,
                        borderRadius: "0.75rem",
                        padding: "0.65rem 0.75rem",
                        display: "flex",
                        flexDirection: "column",
                        gap: "0.45rem",
                      }}
                    >
                      <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                        {formatRecipientLabel(agentKey)}
                      </div>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "minmax(170px, max-content) 0.6rem 1fr",
                          gap: "0.4rem 0.6rem",
                          fontSize: "0.85rem",
                        }}
                      >
                        {renderCostRow("Total", getAgentTotalCost(breakdown))}
                        {renderCostRow("Output (total)", breakdown.output_cost_usd)}
                        {renderCostRow(
                          "Output (reasoning)",
                          breakdown.output_reasoning_cost_usd
                        )}
                        {renderCostRow("Output (answer)", breakdown.output_actual_cost_usd)}
                        {renderCostRow("Cached input", breakdown.cached_input_cost_usd)}
                        {renderCostRow("Input (non-cached)", breakdown.input_cost_usd)}
                        {renderCostRow("Web search", breakdown.web_search_cost_usd)}
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
      </div>
    </div>
  );
}
