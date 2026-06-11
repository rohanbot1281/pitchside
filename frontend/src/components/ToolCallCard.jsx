import React, { useState } from "react";

const TOOL_LABELS = {
  get_fixtures: "FIXTURES",
  simulate_match: "SIMULATION",
  search_knowledge: "KNOWLEDGE BASE",
};

function summarize(name, input, output) {
  if (!output) return null;
  if (output.error) return output.error;
  if (name === "get_fixtures")
    return `${output.match_count} match${output.match_count === 1 ? "" : "es"} · source: ${output.source}`;
  if (name === "simulate_match") {
    const probs = output.probabilities || {};
    return Object.entries(probs)
      .map(([k, v]) => `${k.replace(/_/g, " ")} ${(v * 100).toFixed(0)}%`)
      .join(" · ");
  }
  if (name === "search_knowledge")
    return (output.results || [])
      .map((r) => r.heading)
      .slice(0, 3)
      .join(" · ");
  return null;
}

export default function ToolCallCard({ name, input, output }) {
  const [open, setOpen] = useState(false);
  const pending = output === null;
  const summary = summarize(name, input, output);

  return (
    <div className={`tool-card ${pending ? "pending" : "settled"}`}>
      <button
        className="tool-head"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="tool-kind">{TOOL_LABELS[name] || name}</span>
        <span className="tool-args">
          {Object.values(input || {}).filter(Boolean).join(" · ") || "—"}
        </span>
        <span className="tool-status">{pending ? "CHECKING" : "✓"}</span>
      </button>
      {!pending && summary && <div className="tool-summary">{summary}</div>}
      {open && !pending && (
        <pre className="tool-raw">{JSON.stringify(output, null, 2)}</pre>
      )}
    </div>
  );
}
