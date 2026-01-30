import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { darkTheme } from "../lib/constants";
import { normalizeMathDelimiters } from "../lib/markdown";
import { extractTextFromChildren } from "../lib/formatters";
import { CodeCopyButton } from "./CopyButtons";

/**
 * Render reasoning and optional future note for orchestrator instructions.
 */
export default function OrchestratorReasoningBlock({
  reasoning,
  futureNote,
  theme,
}) {
  const [showNote, setShowNote] = useState(false);
  const safeReasoning = typeof reasoning === "string" ? reasoning : "";
  const safeFutureNote = typeof futureNote === "string" ? futureNote : "";
  const hasReasoning = safeReasoning.trim().length > 0;
  const hasFutureNote = safeFutureNote.trim().length > 0;
  const isDark = theme === darkTheme;
  const blockCodeBg = isDark ? "#0b1220" : "#111827";
  const blockCodeText = "#f9fafb";
  const inlineCodeBg = isDark ? "#0b1220" : "rgba(17,24,39,0.10)";
  const inlineCodeText = isDark ? "#f9fafb" : "#111827";
  const mono =
    'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';

  const markdownComponents = {
    p: ({ node, ...props }) => <p {...props} style={{ margin: "0.05rem 0" }} />,
    pre: ({ node, children: preChildren, ...props }) => (
      <pre
        {...props}
        style={{
          padding: "0.5rem 0.7rem",
          paddingTop: "1.5rem",
          borderRadius: "0.5rem",
          overflowX: "auto",
          background: blockCodeBg,
          color: blockCodeText,
          margin: "0.2rem 0",
          position: "relative",
          fontFamily: mono,
        }}
      >
        <CodeCopyButton
          text={extractTextFromChildren(preChildren).replace(/\n$/, "")}
        />
        {preChildren}
      </pre>
    ),
    code: ({ inline, className, children, ...props }) => {
      const text = React.Children.toArray(children)
        .map((c) => (typeof c === "string" ? c : ""))
        .join("")
        .replace(/\n$/, "");

      if (!inline) {
        return (
          <code
            {...props}
            className={className}
            style={{
              background: "transparent",
              padding: 0,
              fontSize: "0.9em",
              color: "inherit",
              fontFamily: mono,
            }}
          >
            {text}
          </code>
        );
      }

      return (
        <code
          {...props}
          className={className}
          style={{
            padding: "0.1rem 0.3rem",
            borderRadius: "0.25rem",
            background: inlineCodeBg,
            color: inlineCodeText,
            fontSize: "0.9em",
            fontFamily: mono,
          }}
        >
          {text}
        </code>
      );
    },
  };

  if (!hasReasoning && !hasFutureNote) {
    return null;
  }

  const noteTitle = showNote ? "Hide future note" : "Show future note";
  const noteHoverTitle = "Future note scratchpad";
  const noteIcon = "📝";
  const noteButtonBg = showNote
    ? theme === darkTheme
      ? "#0b1220"
      : "rgba(229, 231, 235, 0.85)"
    : theme === darkTheme
      ? "#020617"
      : "rgba(249, 250, 251, 0.9)";

  return (
    <div style={{ marginLeft: "0.25rem", marginBottom: "0.25rem" }}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: hasReasoning ? "space-between" : "flex-end",
          gap: "0.5rem",
          width: "100%",
        }}
      >
        {hasReasoning && (
          <div
            style={{
              flex: 1,
              fontSize: "0.8rem",
              opacity: 0.85,
              fontStyle: "italic",
              marginTop: "0.0rem",
            }}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeKatex]}
              components={markdownComponents}
            >
              {normalizeMathDelimiters(safeReasoning)}
            </ReactMarkdown>
          </div>
        )}

        {hasFutureNote && (
          <button
            type="button"
            onClick={() => setShowNote((v) => !v)}
            title={noteHoverTitle}
            aria-label={noteTitle}
            style={{
              border: `1px solid ${theme.border}`,
              background: noteButtonBg,
              color: theme.text,
              cursor: "pointer",
              borderRadius: "0.6rem",
              padding: "0.15rem 0.45rem",
              fontSize: "0.7rem",
              lineHeight: 1.1,
              opacity: showNote ? 0.95 : 0.75,
            }}
          >
            {noteIcon}
          </button>
        )}
      </div>

      {hasFutureNote && showNote && (
        <div
          style={{
            marginTop: "0.35rem",
            borderRadius: "0.6rem",
            border: `1px solid ${theme.border}`,
            background:
              theme === darkTheme ? "#0b1220" : "rgba(249, 250, 251, 0.9)",
            padding: "0.4rem 0.6rem",
            fontSize: "0.8rem",
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={markdownComponents}
          >
            {normalizeMathDelimiters(safeFutureNote)}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
