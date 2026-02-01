import React, { useState } from "react";
import { darkTheme } from "../lib/constants";

/**
 * Small accordion used to collapse agent replies and plan sections.
 */
export default function ReplyAccordion({
  theme,
  defaultOpen = false,
  label = "Reply",
  children,
}) {
  const [open, setOpen] = useState(defaultOpen);
  const labelContent =
    typeof label === "string" ? (
      <span style={{ fontWeight: 600, opacity: 0.85 }}>{label}</span>
    ) : (
      label
    );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          alignSelf: "flex-start",
          border: `1px solid ${theme.border}`,
          background: theme === darkTheme ? "#020617" : "rgba(249, 250, 251, 0.9)",
          color: theme.text,
          cursor: "pointer",
          borderRadius: "0.75rem",
          padding: "0.35rem 0.6rem",
          fontSize: "0.8rem",
          display: "flex",
          alignItems: "center",
          gap: "0.8rem",
        }}
      >
        <span style={{ width: 14, textAlign: "center" }}>{open ? "▼" : "▶"}</span>
        {labelContent}
      </button>

      {open && children}
    </div>
  );
}
