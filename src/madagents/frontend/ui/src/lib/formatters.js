import React from "react";
import recipientNameMap from "../recipient_name_map.json";
import { CONTROL_CHAR_REGEX } from "./constants";

/**
 * Map an internal recipient id to a display name, falling back to the raw value.
 * @param {string | null | undefined} name
 * @returns {string | null | undefined}
 */
export const getRecipientDisplayName = (name) => {
  if (name === null || name === undefined || name === "") {
    return name;
  }
  const key = String(name);
  const mapped = recipientNameMap?.[key];
  if (typeof mapped === "string" && mapped.trim() !== "") {
    return mapped;
  }
  return key;
};

/**
 * Strip ASCII control characters from a string to avoid rendering glitches.
 * @param {unknown} value
 * @returns {unknown}
 */
export function stripControlChars(value) {
  if (typeof value !== "string") {
    return value;
  }
  return value.replace(CONTROL_CHAR_REGEX, "");
}

/**
 * Recursively extract a plain-text string from React children.
 * @param {React.ReactNode} children
 * @returns {string}
 */
export function extractTextFromChildren(children) {
  return React.Children.toArray(children)
    .map((child) => {
      if (typeof child === "string") {
        return child;
      }
      if (React.isValidElement(child)) {
        return extractTextFromChildren(child.props.children);
      }
      return "";
    })
    .join("");
}

/**
 * Format an ISO-ish timestamp into a user-local string when possible.
 * @param {string | number | null | undefined} value
 * @returns {string}
 */
export function formatRunTimestamp(value) {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

/**
 * Format a numeric cost value into a USD string.
 * @param {number} value
 * @returns {string}
 */
export function formatApproxCost(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "Unavailable";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Replace known agent ids in cost notes with friendly display names.
 * @param {string | null | undefined} note
 * @returns {string | null}
 */
export function formatCostNote(note) {
  if (!note) {
    return null;
  }
  const planUpdaterLabel = recipientNameMap.plan_updater ?? "plan_updater";
  return String(note).replace("plan_updater", planUpdaterLabel);
}

/**
 * Render a user-friendly agent label.
 * @param {string | null | undefined} name
 * @returns {string}
 */
export function formatRecipientLabel(name) {
  if (!name) {
    return "Unknown";
  }
  return recipientNameMap[name] ?? name;
}
