import React from "react";

/**
 * Modal for exporting run bundles and optional assets.
 */
export default function ExportRunModal({
  open,
  onClose,
  theme,
  exportRun,
  exportOptions,
  setExportOptions,
  isExporting,
  onConfirm,
  formatRunLabel,
}) {
  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 65,
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
          width: "min(520px, 92vw)",
          background: theme.cardBg,
          borderRadius: "0.9rem",
          border: `1px solid ${theme.border}`,
          boxShadow: "0 20px 40px rgba(0,0,0,0.35)",
          padding: "1rem 1.25rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.85rem",
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
          <div style={{ fontSize: "1rem", fontWeight: 600 }}>Export run</div>
          <button
            type="button"
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              color: theme.text,
              fontSize: "1.1rem",
              cursor: isExporting ? "not-allowed" : "pointer",
              opacity: isExporting ? 0.6 : 1,
            }}
            aria-label="Close"
            disabled={isExporting}
          >
            ×
          </button>
        </div>

        <div style={{ fontSize: "0.9rem", opacity: 0.85 }}>
          Run: <strong>{exportRun ? formatRunLabel(exportRun) : "—"}</strong>
        </div>

        <div
          style={{
            padding: "0.65rem 0.75rem",
            borderRadius: "0.7rem",
            border: `1px solid ${theme.border}`,
            background: "rgba(0,0,0,0.03)",
            fontSize: "0.88rem",
            lineHeight: 1.4,
          }}
        >
          <strong>Run bundle</strong> (.madrun) includes workdir, checkpoints, and run
          data.
        </div>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.6rem",
            fontSize: "0.9rem",
          }}
        >
          <input
            type="checkbox"
            checked={exportOptions.image}
            onChange={(event) =>
              setExportOptions((prev) => ({
                ...prev,
                image: event.target.checked,
              }))
            }
          />
          Export image + overlay (zip)
        </label>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.6rem",
            fontSize: "0.9rem",
          }}
        >
          <input
            type="checkbox"
            checked={exportOptions.output}
            onChange={(event) =>
              setExportOptions((prev) => ({
                ...prev,
                output: event.target.checked,
              }))
            }
          />
          Export output folder (zip)
        </label>

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "0.6rem",
            marginTop: "0.35rem",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={isExporting}
            style={{
              borderRadius: "0.6rem",
              border: `1px solid ${theme.border}`,
              padding: "0.45rem 0.9rem",
              background: "transparent",
              color: theme.text,
              cursor: isExporting ? "not-allowed" : "pointer",
              fontSize: "0.9rem",
              opacity: isExporting ? 0.7 : 1,
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isExporting || !exportRun}
            style={{
              borderRadius: "0.6rem",
              border: "1px solid #2563eb",
              padding: "0.45rem 0.9rem",
              background: "#2563eb",
              color: "#fff",
              cursor: isExporting ? "not-allowed" : "pointer",
              fontSize: "0.9rem",
              opacity: isExporting ? 0.7 : 1,
            }}
          >
            {isExporting ? "Exporting..." : "Export"}
          </button>
        </div>
      </div>
    </div>
  );
}
