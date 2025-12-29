/**
 * Get the effective classification for a drift based on classifier mode.
 * 
 * Rules:
 * - If classifier_mode_used === "conformance": use drift.classification (fallback "unknown")
 * - Else: use drift.type (fallback "unknown")
 * 
 * This ensures consistent classification across timeline badges, summary counts, and detail panels.
 */
export function getPrimaryClassification(drift) {
  if (!drift) {
    return "unknown";
  }
  
  // In conformance mode, use classification field
  if (drift.classifier_mode_used === "conformance") {
    const cls = (drift.classification ?? "").toString().trim().toLowerCase();
    return cls || "unknown";
  }
  
  // In keywords mode (or mode not set), use type field
  const type = (drift.type ?? "").toString().trim().toLowerCase();
  return type || "unknown";
}

export function getClassificationMeta(drift) {
  const key = getPrimaryClassification(drift);
  if (key === "positive") return { key, label: "Positive", tone: "positive" };
  if (key === "negative") return { key, label: "Negative", tone: "negative" };
  if (key === "needs_review") return { key, label: "Needs Review", tone: "neutral" };
  if (key === "unknown") return { key, label: "Unknown", tone: "neutral" };
  if (key === "no_change") return { key, label: "No Change", tone: "neutral" };
  return { key, label: key ? key.replace(/_/g, " ") : "Unknown", tone: "neutral" };
}

