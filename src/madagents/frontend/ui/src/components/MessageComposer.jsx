import React, { memo, useEffect, useRef, useState } from "react";

/**
 * Message input box with auto-growing textarea and send/interrupt actions.
 */
const MessageComposer = memo(function MessageComposer({
  theme,
  isLoading,
  canInterrupt,
  blockNewMessages,
  onSend,
  onInterrupt,
  onClearError,
}) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef(null);
  const maxInputLines = 14;
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    const styles = window.getComputedStyle(el);
    const lineHeight = Number.parseFloat(styles.lineHeight) || 20;
    const paddingTop = Number.parseFloat(styles.paddingTop) || 0;
    const paddingBottom = Number.parseFloat(styles.paddingBottom) || 0;
    const borderTop = Number.parseFloat(styles.borderTopWidth) || 0;
    const borderBottom = Number.parseFloat(styles.borderBottomWidth) || 0;
    const verticalExtras = paddingTop + paddingBottom + borderTop + borderBottom;
    const minHeight = lineHeight + verticalExtras;
    const maxHeight = lineHeight * maxInputLines + verticalExtras;
    el.style.height = "auto";
    const scrollHeight = el.scrollHeight + borderTop + borderBottom;
    const nextHeight = Math.min(scrollHeight, maxHeight);
    el.style.height = `${Math.max(nextHeight, minHeight)}px`;
    el.style.overflowY = scrollHeight > maxHeight ? "auto" : "hidden";
    el.style.minHeight = `${minHeight}px`;
    el.style.maxHeight = `${maxHeight}px`;
    setIsExpanded(scrollHeight > minHeight + 1);
  }, [draft, maxInputLines]);

  const handleSubmit = (e) => {
    if (e) {
      e.preventDefault();
    }
    const trimmed = draft.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setDraft("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        display: "flex",
        gap: "0.75rem",
        padding: "1rem",
        borderTop: `1px solid ${theme.headerBorder}`,
        background: theme.inputBg,
      }}
    >
      <textarea
        ref={inputRef}
        rows={1}
        placeholder="Type a message..."
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          if (onClearError) {
            onClearError();
          }
        }}
        onKeyDown={handleKeyDown}
        style={{
          flex: 1,
          padding: "0.5rem 0.9rem",
          borderRadius: isExpanded ? "0.9rem" : "999px",
          border: `1px solid ${theme.border}`,
          boxSizing: "border-box",
          fontSize: "1rem",
          fontFamily: "inherit",
          outline: "none",
          background: theme.cardBg,
          color: theme.text,
          resize: "none",
          lineHeight: 1.2,
        }}
      />
      {isLoading ? (
        <button
          type="button"
          onClick={onInterrupt}
          disabled={!canInterrupt}
          style={{
            padding: "0.75rem 1.25rem",
            borderRadius: "999px",
            border: "none",
            background: canInterrupt ? "#dc2626" : "#6b7280",
            color: "white",
            fontWeight: 500,
            fontSize: "1rem",
            cursor: canInterrupt ? "pointer" : "default",
          }}
        >
          Interrupt
        </button>
      ) : (
        <button
          type="submit"
          disabled={blockNewMessages}
          style={{
            padding: "0.75rem 1.25rem",
            borderRadius: "999px",
            border: "none",
            background: blockNewMessages ? "#6b7280" : "#2563eb",
            color: "white",
            fontWeight: 500,
            fontSize: "1rem",
            cursor: blockNewMessages ? "default" : "pointer",
          }}
        >
          {blockNewMessages ? "Busy" : "Send"}
        </button>
      )}
    </form>
  );
});

export default MessageComposer;
