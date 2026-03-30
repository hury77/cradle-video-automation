import React, { useState, useEffect } from "react";

interface QAVerdictPanelProps {
  jobId: number;
  clientName: string;
  onSaveSuccess?: () => void;
}

const VERDICT_LABELS = {
  approve: { label: "✅ APPROVE", bg: "bg-green-500 hover:bg-green-600", ring: "ring-green-500", text: "text-green-700", light: "bg-green-50 border-green-200" },
  reject: { label: "❌ REJECT", bg: "bg-red-500 hover:bg-red-600", ring: "ring-red-500", text: "text-red-700", light: "bg-red-50 border-red-200" },
  review: { label: "👤 REVIEW", bg: "bg-amber-500 hover:bg-amber-600", ring: "ring-amber-500", text: "text-amber-700", light: "bg-amber-50 border-amber-200" },
};

const QAVerdictPanel: React.FC<QAVerdictPanelProps> = ({ jobId, clientName, onSaveSuccess }) => {
  const [verdict, setVerdict] = useState<"approve" | "reject" | "review" | null>(null);
  const [reasoning, setReasoning] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existingDecision, setExistingDecision] = useState<any>(null);

  // Load existing decision on mount
  useEffect(() => {
    fetch(`/api/v1/compare/${jobId}/decision`)
      .then((r) => r.json())
      .then((data) => {
        if (data.exists) {
          setExistingDecision(data);
          setVerdict(data.verdict as any);
          setReasoning(data.reasoning || "");
          setSaved(true);
        }
      })
      .catch(() => {});
  }, [jobId]);

  const handleSave = async () => {
    if (!verdict) {
      setError("Select a verdict before saving.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const response = await fetch(`/api/v1/compare/${jobId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          verdict,
          reasoning,
          client_name: clientName || undefined,
          decided_by: "human",
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setSaved(true);

      // Signal to base tab that automation can continue (next asset)
      // Clear auto-compare flag so automation doesn't loop
      localStorage.removeItem("cradle-auto-video-compare");
      
      // Auto-navigate back to dashboard after 2s
      if (onSaveSuccess) {
          setTimeout(onSaveSuccess, 2000);
      }
    } catch (e: any) {
      setError(`Save error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const selectedStyle = verdict ? VERDICT_LABELS[verdict] : null;

  return (
    <div className="mt-8 mb-4 mx-auto max-w-7xl print:hidden">
      <div
        className={`rounded-2xl shadow-md border-2 p-6 transition-all ${
          saved && selectedStyle
            ? `${selectedStyle.light} ${selectedStyle.ring} ring-2`
            : "bg-white border-gray-200"
        }`}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">📋</span>
            <div>
              <h2 className="text-xl font-bold text-gray-900">QA Decision</h2>
              {clientName && (
                <p className="text-sm text-gray-500">
                  Client: <span className="font-semibold text-gray-700">{clientName}</span>
                </p>
              )}
            </div>
          </div>
          {saved && verdict && (
            <span
              className={`px-4 py-1.5 rounded-full text-sm font-bold ${selectedStyle?.text} ${selectedStyle?.light} border`}
            >
              {VERDICT_LABELS[verdict].label} — saved
            </span>
          )}
        </div>

        {/* Verdict Buttons */}
        <div className="flex gap-3 mb-5">
          {(["approve", "reject", "review"] as const).map((v) => {
            const style = VERDICT_LABELS[v];
            const isSelected = verdict === v;
            return (
              <button
                key={v}
                onClick={() => { setVerdict(v); setSaved(false); }}
                className={`flex-1 py-3 px-4 rounded-xl text-white font-bold text-sm transition-all shadow-sm ${style.bg} ${
                  isSelected ? `ring-4 ring-offset-2 ${style.ring} scale-105` : "opacity-80 hover:opacity-100"
                }`}
              >
                {style.label}
              </button>
            );
          })}
        </div>

        {/* Reasoning */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Reasoning <span className="text-gray-400 font-normal">(optional, but helpful for Agent 2)</span>
          </label>
          <textarea
            value={reasoning}
            onChange={(e) => { setReasoning(e.target.value); setSaved(false); }}
            rows={3}
            placeholder="e.g. 'Background color difference in 0:04-0:07, acceptable due to compression. Audio identical.'"
            className="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400 resize-none transition"
          />
        </div>

        {/* Error */}
        {error && (
          <p className="text-red-600 text-sm mb-3 font-medium">⚠️ {error}</p>
        )}

        {/* Save Button */}
        <button
          onClick={handleSave}
          disabled={saving || !verdict}
          className={`w-full py-3 rounded-xl text-white font-bold text-base transition-all shadow ${
            saving || !verdict
              ? "bg-gray-300 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-700 active:scale-[0.98]"
          }`}
        >
          {saving ? "Saving..." : saved ? "✓ Saved — Automation can continue" : "💾 Save decision and continue automation"}
        </button>

        {saved && (
          <p className="text-center text-sm text-gray-500 mt-3">
            Decision saved to Knowledge Base. Automation will proceed to the next asset.
          </p>
        )}
      </div>
    </div>
  );
};

export default QAVerdictPanel;
