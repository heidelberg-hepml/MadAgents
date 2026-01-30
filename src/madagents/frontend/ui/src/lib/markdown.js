import { stripControlChars } from "./formatters";

function replaceMathDelimiters(text) {
  if (!text) {
    return text;
  }
  const blockMath = /\\\[((?:[\s\S]*?))\\\]/g;
  const inlineMath = /\\\(([\s\S]*?)\\\)/g;
  return text
    .replace(blockMath, (_, content) => `$$${content}$$`)
    .replace(inlineMath, (_, content) => `$${content}$`);
}

function outdentMathDelimiters(text) {
  if (!text) {
    return text;
  }
  return text.replace(/^([ \t]*)\$\$\s*$/gm, (line, indent) => {
    if (indent.length <= 3) {
      return `${indent}$$`;
    }
    return "  $$";
  });
}

function normalizeMathSegment(text) {
  return outdentMathDelimiters(replaceMathDelimiters(text));
}

/**
 * Normalize math delimiters outside of code fences and inline code spans.
 * @param {unknown} value
 * @returns {unknown}
 */
export function normalizeMathDelimiters(value) {
  if (typeof value !== "string") {
    return value;
  }

  const cleaned = stripControlChars(value);
  const lines = cleaned.split("\n");
  const segments = [];
  let buffer = [];
  let inFence = false;
  let fenceChar = "";
  let fenceSize = 0;

  const flush = (asCode) => {
    if (!buffer.length) {
      return;
    }
    segments.push({ text: buffer.join("\n"), isCode: asCode });
    buffer = [];
  };

  for (const line of lines) {
    const fenceMatch = line.match(/^\s{0,3}(```+|~~~+)/);
    if (fenceMatch) {
      const fence = fenceMatch[1];
      if (!inFence) {
        flush(false);
        inFence = true;
        fenceChar = fence[0];
        fenceSize = fence.length;
        buffer.push(line);
        continue;
      }
      if (fence[0] === fenceChar && fence.length >= fenceSize) {
        buffer.push(line);
        flush(true);
        inFence = false;
        fenceChar = "";
        fenceSize = 0;
        continue;
      }
    }
    buffer.push(line);
  }
  flush(inFence);

  const inlineCodeRegex = /(`+)([^`]*?)\1/g;
  const normalizeInlineSafe = (text) => {
    let result = "";
    let lastIndex = 0;
    let match;

    while ((match = inlineCodeRegex.exec(text)) !== null) {
      result += normalizeMathSegment(text.slice(lastIndex, match.index));
      result += match[0];
      lastIndex = match.index + match[0].length;
    }

    result += normalizeMathSegment(text.slice(lastIndex));
    return result;
  };

  return segments
    .map((segment) =>
      segment.isCode ? segment.text : normalizeInlineSafe(segment.text)
    )
    .join("\n");
}
