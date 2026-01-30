import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { darkTheme } from "../lib/constants";
import { normalizeMathDelimiters } from "../lib/markdown";
import { extractTextFromChildren } from "../lib/formatters";
import { CodeCopyButton, MessageCopyButton, MessageRewindButton } from "./CopyButtons";

/**
 * Render a markdown message bubble with optional action buttons.
 */
export default function MarkdownBubble({
  children,
  isUser,
  theme,
  showCopy = false,
  copyText = "",
  showRewind = false,
  onRewind = null,
  rewindDisabled = false,
}) {
  const isDark = theme === darkTheme;
  const remarkPlugins = isUser
    ? [remarkGfm, remarkMath, remarkBreaks]
    : [remarkGfm, remarkMath];
  const copyTextValue = typeof copyText === "string" ? copyText : "";
  const showCopyButton = showCopy && copyTextValue.trim() !== "";
  const showRewindButton = showRewind && typeof onRewind === "function";
  const showActionButtons = showCopyButton || showRewindButton;
  const markdownContent =
    typeof children === "string" ? normalizeMathDelimiters(children) : children;

  // Code styling: ensure contrast in BOTH themes
  const blockCodeBg = isUser
    ? "rgba(0,0,0,0.25)"
    : isDark
      ? "#0b1220"
      : "#111827";

  const blockCodeText = isUser ? theme.userBubbleText : "#f9fafb";

  const inlineCodeBg = isUser
    ? "rgba(0,0,0,0.25)"
    : isDark
      ? "#0b1220"
      : "rgba(17,24,39,0.10)";

  const inlineCodeText = isUser
    ? theme.userBubbleText
    : isDark
      ? "#f9fafb"
      : "#111827";

  const mono =
    'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';

  return (
    <div
      style={{
        background: isUser ? theme.userBubbleBg : theme.botBubbleBg,
        color: isUser ? theme.userBubbleText : theme.botBubbleText,
        borderRadius: isUser
          ? "1rem 1rem 0.25rem 1rem"
          : "1rem 1rem 1rem 0.25rem",
        padding: showActionButtons ? "1.5rem 5.2rem 0.75rem 1rem" : "0.75rem 1rem",
        fontSize: "0.95rem",
        lineHeight: 1.5,
        position: showActionButtons ? "relative" : "static",
      }}
    >
      {showRewindButton && (
        <MessageRewindButton
          theme={theme}
          isUser={isUser}
          onClick={onRewind}
          disabled={rewindDisabled}
        />
      )}
      {showCopyButton && (
        <MessageCopyButton text={copyTextValue} theme={theme} isUser={isUser} />
      )}
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
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
                padding: "0.6rem 0.8rem",
                paddingTop: "1.6rem",
                borderRadius: "0.5rem",
                overflowX: "auto",
                background: blockCodeBg,
                color: blockCodeText,
                margin: "0.25rem 0",
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
            // Never stringify undefined -> prevents rendering a literal "undefined"
            const text = React.Children.toArray(children)
              .map((c) => (typeof c === "string" ? c : ""))
              .join("")
              .replace(/\n$/, "");

            if (!inline) {
              // fenced code block: <pre> handles the box styling
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

            // inline code
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
            <ul {...props} style={{ paddingLeft: "1.25rem", margin: "0.25rem 0" }} />
          ),
          ol: ({ node, ...props }) => (
            <ol {...props} style={{ paddingLeft: "1.25rem", margin: "0.25rem 0" }} />
          ),
          p: ({ node, ...props }) => <p {...props} style={{ margin: "0.25rem 0" }} />,
        }}
      >
        {markdownContent}
      </ReactMarkdown>
    </div>
  );
}
