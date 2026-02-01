/**
 * Compute a summary of plan step statuses for badges and progress bars.
 * @param {object} plan
 * @returns {{steps: Array, total: number, doneCount: number, inProgressCount: number, skippedCount: number, failedCount: number, blockedCount: number, completedCount: number}}
 */
export const getPlanStats = (plan) => {
  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
  let doneCount = 0;
  let skippedCount = 0;
  let failedCount = 0;
  let blockedCount = 0;
  let inProgressCount = 0;

  steps.forEach((step) => {
    const status = String(step?.status || "").toLowerCase();
    if (status === "done") {
      doneCount += 1;
    } else if (status === "in_progress") {
      inProgressCount += 1;
    } else if (status === "skipped") {
      skippedCount += 1;
    } else if (status === "failed") {
      failedCount += 1;
    } else if (status === "blocked") {
      blockedCount += 1;
    }
  });

  return {
    steps,
    total: steps.length,
    doneCount,
    inProgressCount,
    skippedCount,
    failedCount,
    blockedCount,
    completedCount: doneCount + skippedCount,
  };
};

export const getStatusStyle = (statusRaw, isDark) => {
  const status = String(statusRaw || "pending").toLowerCase();
  const light = {
    done: { bg: "#dcfce7", text: "#166534", border: "#86efac" },
    in_progress: { bg: "#fef3c7", text: "#92400e", border: "#fde68a" },
    pending: { bg: "#e0f2fe", text: "#075985", border: "#bae6fd" },
    blocked: { bg: "#fef2f2", text: "#991b1b", border: "#fecaca" },
    failed: { bg: "#fee2e2", text: "#b91c1c", border: "#fecaca" },
    skipped: { bg: "#f3f4f6", text: "#374151", border: "#e5e7eb" },
  };
  const dark = {
    done: { bg: "#064e3b", text: "#d1fae5", border: "#0f766e" },
    in_progress: { bg: "#78350f", text: "#fef3c7", border: "#b45309" },
    pending: { bg: "#0c4a6e", text: "#e0f2fe", border: "#075985" },
    blocked: { bg: "#7f1d1d", text: "#fee2e2", border: "#b91c1c" },
    failed: { bg: "#7f1d1d", text: "#fee2e2", border: "#b91c1c" },
    skipped: { bg: "#111827", text: "#d1d5db", border: "#374151" },
  };
  const palette = isDark ? dark : light;
  return palette[status] || palette.pending;
};

export const formatStatus = (statusRaw) => {
  const status = String(statusRaw || "pending");
  return status.replace(/_/g, " ").toUpperCase();
};

const parsePlanMetaTimestamp = (value) => {
  if (!value) {
    return null;
  }
  const ts = Date.parse(String(value));
  return Number.isFinite(ts) ? ts : null;
};

const normalizePlanStatus = (value) => {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).toLowerCase();
};

const buildPlanMetaMap = (planMetaData) => {
  const steps = Array.isArray(planMetaData?.steps) ? planMetaData.steps : [];
  const metaMap = new Map();
  steps.forEach((step) => {
    const stepId = step?.id;
    if (stepId === null || stepId === undefined) {
      return;
    }
    const updatedAt = parsePlanMetaTimestamp(step?.last_updated);
    if (updatedAt === null) {
      return;
    }
    metaMap.set(String(stepId), updatedAt);
  });
  return metaMap;
};

const buildPlanStatusMap = (plan) => {
  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
  const statusMap = new Map();
  steps.forEach((step) => {
    const stepId = step?.id;
    if (stepId === null || stepId === undefined) {
      return;
    }
    statusMap.set(String(stepId), normalizePlanStatus(step?.status));
  });
  return statusMap;
};

/**
 * Track which steps are newly updated based on meta timestamps and status transitions.
 * @param {object} plan
 * @param {object} planMetaData
 * @param {Map | null} previousMetaMap
 * @param {Map | null} previousStatusMap
 * @returns {{updatedSteps: Array, metaMap: Map, statusMap: Map}}
 */
export const getUpdatedPlanSteps = (
  plan,
  planMetaData,
  previousMetaMap,
  previousStatusMap
) => {
  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
  const metaMap = buildPlanMetaMap(planMetaData);
  const statusMap = buildPlanStatusMap(plan);
  if (!previousMetaMap) {
    return { updatedSteps: [], metaMap, statusMap };
  }

  const updatedSteps = steps.filter((step) => {
    const stepId = step?.id;
    if (stepId === null || stepId === undefined) {
      return false;
    }
    const key = String(stepId);
    const current = metaMap.get(key);
    if (current === undefined) {
      return false;
    }
    const previous = previousMetaMap.get(key);
    if (previous === undefined) {
      return true;
    }
    if (current <= previous) {
      return false;
    }
    const previousStatus = previousStatusMap?.get(key);
    const currentStatus = statusMap.get(key);
    if (previousStatus === "blocked" && currentStatus === "pending") {
      return false;
    }
    return true;
  });

  return { updatedSteps, metaMap, statusMap };
};
