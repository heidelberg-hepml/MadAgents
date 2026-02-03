import React, { useEffect, useRef, useState } from "react";
import { darkTheme } from "../lib/constants";
import { copyToClipboard } from "../lib/clipboard";

/**
 * Copy button used inside fenced code blocks.
 */
export function CodeCopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const handleCopy = async () => {
    if (!text) {
      return;
    }
    try {
      await copyToClipboard(text);
      setCopied(true);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      disabled={!text}
      title={copied ? "Copied" : "Copy code"}
      aria-label="Copy code block"
      style={{
        position: "absolute",
        top: "0.35rem",
        right: "0.45rem",
        border: "1px solid rgba(255,255,255,0.25)",
        background: "rgba(0,0,0,0.45)",
        color: "#f9fafb",
        padding: "0.2rem 0.35rem",
        borderRadius: "0.35rem",
        cursor: text ? "pointer" : "not-allowed",
        opacity: text ? 0.95 : 0.4,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {copied ? (
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          width="14"
          height="14"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M20 6 9 17l-5-5" />
        </svg>
      ) : (
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          width="14"
          height="14"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </button>
  );
}

/**
 * Copy button for chat messages.
 */
export function MessageCopyButton({ text, theme, isUser }) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const textToCopy = typeof text === "string" ? text : "";
  const isDark = theme === darkTheme;
  const buttonBg = isUser
    ? "rgba(0,0,0,0.35)"
    : isDark
      ? "rgba(255,255,255,0.08)"
      : "rgba(17,24,39,0.06)";
  const buttonBorder = isUser
    ? "rgba(255,255,255,0.4)"
    : isDark
      ? "rgba(255,255,255,0.18)"
      : "rgba(17,24,39,0.15)";
  const buttonColor = isUser ? "#f9fafb" : theme.text;

  const handleCopy = async () => {
    if (!textToCopy) {
      return;
    }
    try {
      await copyToClipboard(textToCopy);
      setCopied(true);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  if (!textToCopy) {
    return null;
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? "Copied" : "Copy message"}
      aria-label="Copy message"
      style={{
        position: "absolute",
        top: "0.35rem",
        right: "0.45rem",
        border: `1px solid ${buttonBorder}`,
        background: buttonBg,
        color: buttonColor,
        fontSize: "0.7rem",
        padding: "0.15rem 0.4rem",
        borderRadius: "0.35rem",
        cursor: "pointer",
        opacity: 0.95,
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

/**
 * Button for rewinding a user message.
 */
export function MessageRewindButton({
  theme,
  isUser,
  onClick,
  disabled = false,
  loading = false,
  tooltip = "Rewind",
}) {
  const isDark = theme === darkTheme;
  const buttonBg = isUser
    ? "rgba(0,0,0,0.35)"
    : isDark
      ? "rgba(255,255,255,0.08)"
      : "rgba(17,24,39,0.06)";
  const buttonBorder = isUser
    ? "rgba(255,255,255,0.4)"
    : isDark
      ? "rgba(255,255,255,0.18)"
      : "rgba(17,24,39,0.15)";
  const buttonColor = isUser ? "#f9fafb" : theme.text;
  const isDisabled = disabled || loading;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isDisabled}
      title={tooltip}
      aria-label={tooltip}
      style={{
        position: "absolute",
        top: "0.35rem",
        right: "3.05rem",
        border: `1px solid ${buttonBorder}`,
        background: buttonBg,
        color: buttonColor,
        fontSize: "0.7rem",
        padding: "0.15rem 0.4rem",
        borderRadius: "0.35rem",
        cursor: isDisabled ? "default" : "pointer",
        opacity: isDisabled ? 0.5 : 0.95,
        display: "inline-flex",
        alignItems: "center",
        gap: "0.25rem",
      }}
    >
      Rewind
      {loading && (
        <svg
          width="12"
          height="12"
          viewBox="0 0 50 50"
          aria-hidden="true"
          focusable="false"
        >
          <circle
            cx="25"
            cy="25"
            r="20"
            fill="none"
            stroke={buttonColor}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray="31.4 31.4"
          >
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 25 25"
              to="360 25 25"
              dur="0.8s"
              repeatCount="indefinite"
            />
          </circle>
        </svg>
      )}
    </button>
  );
}
