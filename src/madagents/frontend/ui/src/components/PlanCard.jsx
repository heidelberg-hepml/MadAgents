import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { darkTheme } from "../lib/constants";
import { normalizeMathDelimiters } from "../lib/markdown";
import { extractTextFromChildren } from "../lib/formatters";
import { formatStatus, getPlanStats, getStatusStyle } from "../lib/plan";
import { CodeCopyButton } from "./CopyButtons";

function getPlanStatusColors(theme) {
  const isDark = theme === darkTheme;
  return {
    okColor: isDark ? "#22c55e" : "#16a34a",
    inProgressColor: isDark ? "#fef3c7" : "#92400e",
    skipColor: isDark ? "#9ca3af" : "#6b7280",
    badColor: isDark ? "#f87171" : "#dc2626",
    blockedColor: isDark ? "#fbbf24" : "#b45309",
  };
}

const renderPlanStatusItems = (
  stats,
  theme,
  { showTotal = true, omitZero = false } = {}
) => {
  const { doneCount, inProgressCount, skippedCount, failedCount, blockedCount, total } =
    stats;
  const { okColor, inProgressColor, skipColor, badColor, blockedColor } =
    getPlanStatusColors(theme);
  const items = [];
  const pushItem = (count, icon, color, key) => {
    if (omitZero && !count) {
      return;
    }
    items.push(
      <span
        key={key}
        style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}
      >
        <span style={{ color, fontWeight: 700 }}>{icon}</span>
        <span style={{ fontSize: "0.8rem", opacity: 0.85 }}>{count}</span>
      </span>
    );
  };

  pushItem(inProgressCount, "⚙️", inProgressColor, "status-in-progress");
  pushItem(doneCount, "✓", okColor, "status-done");
  pushItem(skippedCount, "⏭", skipColor, "status-skipped");
  pushItem(failedCount, "✕", badColor, "status-failed");
  pushItem(blockedCount, "🔒", blockedColor, "status-blocked");

  if (showTotal) {
    items.push(
      <span
        key="status-total"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0,
          fontSize: "0.8rem",
          opacity: 0.75,
        }}
      >
        <span style={{ marginRight: "0.8rem" }}>/</span>
        <span>{total}</span>
      </span>
    );
  }

  return items;
};

export const renderPlanLabel = (plan, theme, label = "Plan") => {
  const stats = getPlanStats(plan);

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.7rem" }}>
      <span style={{ fontWeight: 600, opacity: 0.85 }}>{label}</span>
      {renderPlanStatusItems(stats, theme, { showTotal: true, omitZero: false })}
    </span>
  );
};

export const renderPlanUpdateLabel = (steps, theme) => {
  const stats = getPlanStats({ steps: Array.isArray(steps) ? steps : [] });
  const statusItems = renderPlanStatusItems(stats, theme, {
    showTotal: false,
    omitZero: true,
  });

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.7rem" }}>
      <span style={{ fontWeight: 600, opacity: 0.85 }}>Plan update</span>
      {statusItems}
    </span>
  );
};

function PlanMarkdown({ children, theme, fontSize = "0.9rem", italic = false }) {
  const isDark = theme === darkTheme;

  const blockCodeBg = isDark ? "#0b1220" : "#111827";
  const blockCodeText = "#f9fafb";
  const inlineCodeBg = isDark ? "#0b1220" : "rgba(17,24,39,0.10)";
  const inlineCodeText = isDark ? "#f9fafb" : "#111827";
  const mono =
    'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';
  const markdownContent =
    typeof children === "string" ? normalizeMathDelimiters(children) : children;

  return (
    <div
      style={{
        fontSize,
        fontStyle: italic ? "italic" : "normal",
        opacity: italic ? 0.85 : 1,
        lineHeight: 1.45,
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          a: ({ node, ...props }) => (
            <a
              {...props}
              style={{ textDecoration: "underline" }}
              target="_blank"
              rel="noreferrer"
            />
          ),
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
          ul: ({ node, ...props }) => (
            <ul {...props} style={{ paddingLeft: "1.25rem", margin: "0.2rem 0" }} />
          ),
          ol: ({ node, ...props }) => (
            <ol {...props} style={{ paddingLeft: "1.25rem", margin: "0.2rem 0" }} />
          ),
          p: ({ node, ...props }) => <p {...props} style={{ margin: "0.2rem 0" }} />,
        }}
      >
        {markdownContent}
      </ReactMarkdown>
    </div>
  );
}

function PlanStepItem({ step, idx, theme, isDark }) {
  const [open, setOpen] = useState(false);
  const style = getStatusStyle(step?.status, isDark);
  const dependsOn = Array.isArray(step?.depends_on) ? step.depends_on : [];
  const description = step?.description || "";
  const rationale = step?.rationale || "";
  const outcome = step?.outcome || "";
  const rawTitle = typeof step?.title === "string" ? step.title.trim() : "";
  const stepId = step?.id ?? idx + 1;
  const stepLabel = rawTitle ? rawTitle : `Step ${stepId}`;
  const stepIdLabel = `ID: ${stepId}`;

  return (
    <div
      style={{
        border: `1px solid ${theme.border}`,
        borderRadius: "0.6rem",
        padding: "0.5rem 0.6rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.35rem",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          border: "none",
          background: "transparent",
          padding: 0,
          cursor: "pointer",
          textAlign: "left",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          width: "100%",
          color: theme.text,
        }}
      >
        <span style={{ width: 14, textAlign: "center" }}>{open ? "▼" : "▶"}</span>
        <span
          style={{
            fontSize: "0.7rem",
            padding: "0.15rem 0.45rem",
            borderRadius: 999,
            background: style.bg,
            color: style.text,
            border: `1px solid ${style.border}`,
            fontWeight: 600,
          }}
        >
          {formatStatus(step?.status)}
        </span>
        <span style={{ fontWeight: 600 }}>{stepLabel}</span>
        <span
          style={{
            marginLeft: "auto",
            fontSize: "0.75rem",
            opacity: 0.7,
          }}
        >
          {stepIdLabel}
        </span>
      </button>

      {open && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
          {description && (
            <PlanMarkdown theme={theme} fontSize="0.95rem">
              {description}
            </PlanMarkdown>
          )}

          {outcome && (
            <div>
              <div style={{ fontSize: "0.7rem", opacity: 0.6 }}>Outcome</div>
              <PlanMarkdown theme={theme} fontSize="0.95rem">
                {outcome}
              </PlanMarkdown>
            </div>
          )}

          {rationale && (
            <div>
              <div style={{ fontSize: "0.7rem", opacity: 0.6 }}>Rationale</div>
              <PlanMarkdown theme={theme} fontSize="0.8rem" italic>
                {rationale}
              </PlanMarkdown>
            </div>
          )}

          {dependsOn.length > 0 && (
            <div style={{ fontSize: "0.75rem", opacity: 0.7 }}>
              Depends on: {dependsOn.join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PlanUpdateStepItem({ step, idx, theme, isDark }) {
  const style = getStatusStyle(step?.status, isDark);
  const description = step?.description || "";
  const outcome = step?.outcome || "";
  const rawTitle = typeof step?.title === "string" ? step.title.trim() : "";
  const stepId = step?.id ?? idx + 1;
  const stepLabel = rawTitle ? rawTitle : `Step ${stepId}`;
  const stepIdLabel = `ID: ${stepId}`;

  return (
    <div
      style={{
        border: `1px solid ${theme.border}`,
        borderRadius: "0.6rem",
        padding: "0.6rem 0.7rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.45rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span
          style={{
            fontSize: "0.7rem",
            padding: "0.15rem 0.45rem",
            borderRadius: 999,
            background: style.bg,
            color: style.text,
            border: `1px solid ${style.border}`,
            fontWeight: 600,
          }}
        >
          {formatStatus(step?.status)}
        </span>
        <span style={{ fontWeight: 600 }}>{stepLabel}</span>
        <span
          style={{
            marginLeft: "auto",
            fontSize: "0.75rem",
            opacity: 0.7,
          }}
        >
          {stepIdLabel}
        </span>
      </div>

      {description && (
        <PlanMarkdown theme={theme} fontSize="0.95rem">
          {description}
        </PlanMarkdown>
      )}

      {outcome && (
        <div
          style={{
            borderRadius: "0.6rem",
            padding: "0.5rem 0.6rem",
            background: isDark ? "#0b1220" : "rgba(15, 23, 42, 0.04)",
            border: `1px solid ${style.border}`,
          }}
        >
          <div style={{ fontSize: "0.7rem", opacity: 0.65 }}>Outcome</div>
          <PlanMarkdown theme={theme} fontSize="0.95rem">
            {outcome}
          </PlanMarkdown>
        </div>
      )}
    </div>
  );
}

export function PlanUpdatesCard({ steps, theme, showStatusIcons = true }) {
  const isDark = theme === darkTheme;
  const stats = getPlanStats({ steps: Array.isArray(steps) ? steps : [] });
  const statusItems = renderPlanStatusItems(stats, theme, {
    showTotal: false,
    omitZero: true,
  });

  if (!steps || steps.length === 0) {
    return null;
  }

  const orderedSteps = [...steps].reverse();

  return (
    <div
      style={{
        border: `1px solid ${theme.border}`,
        background: theme.cardBg,
        borderRadius: "0.8rem",
        padding: "0.75rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.6rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: "0.5rem",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.6rem",
          }}
        >
          <span style={{ fontWeight: 600 }}>Updated steps</span>
          {showStatusIcons && statusItems.length > 0 && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.6rem",
              }}
            >
              {statusItems}
            </span>
          )}
        </div>
        <div style={{ fontSize: "0.8rem", opacity: 0.7 }}>{steps.length}</div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        {orderedSteps.map((step, idx) => (
          <PlanUpdateStepItem
            key={step?.id ?? `updated-step-${idx}`}
            step={step}
            idx={idx}
            theme={theme}
            isDark={isDark}
          />
        ))}
      </div>
    </div>
  );
}

export function PlanCard({ plan, theme }) {
  const isDark = theme === darkTheme;
  const { steps, total, completedCount } = getPlanStats(plan);
  const progress = total ? Math.round((completedCount / total) * 100) : 0;

  return (
    <div
      style={{
        border: `1px solid ${theme.border}`,
        background: theme.cardBg,
        borderRadius: "0.8rem",
        padding: "0.75rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.6rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: "0.5rem",
        }}
      >
        <div style={{ fontWeight: 600 }}>Plan</div>
        <div style={{ fontSize: "0.8rem", opacity: 0.7 }}>
          {completedCount}/{steps.length} done
        </div>
      </div>
      <div style={{ height: 6, background: theme.border, borderRadius: 999 }}>
        <div
          style={{
            height: "100%",
            width: `${progress}%`,
            background: isDark ? "#22c55e" : "#16a34a",
            borderRadius: 999,
          }}
        />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {steps.map((step, idx) => {
          return (
            <PlanStepItem
              key={step?.id ?? `step-${idx}`}
              step={step}
              idx={idx}
              theme={theme}
              isDark={isDark}
            />
          );
        })}
      </div>
    </div>
  );
}
