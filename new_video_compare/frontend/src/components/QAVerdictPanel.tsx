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
  const [comment, setComment] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existingDecision, setExistingDecision] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);

  // Load existing decision on mount
  useEffect(() => {
    fetch(`/api/v1/compare/${jobId}/decision`)
      .then((r) => r.json())
      .then((data) => {
        if (data.exists) {
          setExistingDecision(data);
          setVerdict(data.verdict as any);
          setReasoning(data.reasoning || "");
          setComment(data.comment || "");
          setOverrideReason(data.override_reason || "");
          setSaved(true);
          setIsEditing(false);
        } else {
          setIsEditing(true);
        }
      })
      .catch(() => { setIsEditing(true); });
  }, [jobId]);

  const handleSave = async () => {
    if (!verdict) { setError("Select a verdict before saving."); return; }
    setSaving(true);
    setError(null);
    try {
      const isOverride = existingDecision?.decided_by === "agent";
      const response = await fetch(`/api/v1/compare/${jobId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          verdict,
          reasoning: comment || reasoning || undefined,  // Use comment as main reasoning if provided
          comment: comment || undefined,
          override_reason: isOverride ? overrideReason || undefined : undefined,
          client_name: clientName || undefined,
          decided_by: "human",
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const updatedDecision = {
        ...existingDecision,
        verdict,
        reasoning: comment || reasoning,
        comment,
        override_reason: overrideReason,
        decided_by: "human",
      };
      setExistingDecision(updatedDecision);
      setSaved(true);
      setIsEditing(false);
      localStorage.removeItem("cradle-auto-video-compare");
      if (onSaveSuccess) setTimeout(onSaveSuccess, 2000);
    } catch (e: any) {
      setError(`Save error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleStartEdit = () => {
    setIsEditing(true);
    setSaved(false);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setSaved(true);
    setVerdict(existingDecision?.verdict || null);
    setReasoning(existingDecision?.reasoning || "");
    setComment(existingDecision?.comment || "");
    setOverrideReason(existingDecision?.override_reason || "");
  };

  const selectedStyle = verdict ? VERDICT_LABELS[verdict] : null;
  const isAiDecision = existingDecision?.decided_by === "agent";
  const isHumanOverride = existingDecision?.decided_by === "human";

  // ── Read-only view ──
  if (saved && !isEditing && existingDecision) {
    return (
      <div className="mt-8 mb-4 mx-auto max-w-7xl print:hidden">
        <div className={`rounded-2xl shadow-md border-2 p-6 transition-all ${selectedStyle ? `${selectedStyle.light} ${selectedStyle.ring} ring-2` : "bg-white border-gray-200"}`}>
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">📋</span>
              <div>
                <h2 className="text-xl font-bold text-gray-900">QA Decision</h2>
                {clientName && <p className="text-sm text-gray-500">Client: <span className="font-semibold text-gray-700">{clientName}</span></p>}
              </div>
            </div>
            {verdict && selectedStyle && (
              <span className={`px-4 py-1.5 rounded-full text-sm font-bold ${selectedStyle.text} ${selectedStyle.light} border`}>
                {VERDICT_LABELS[verdict].label}
              </span>
            )}
          </div>

          {/* Author badge */}
          <div className="mb-4">
            {isHumanOverride ? (
              <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-sm font-semibold w-fit">
                <span>👤</span><span>Human override — decision changed by QA user</span>
              </div>
            ) : isAiDecision ? (
              <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-50 border border-purple-200 text-purple-800 text-sm font-semibold w-fit">
                <span>🧠</span><span>AI Analyst (Agent 2) — automatic decision</span>
              </div>
            ) : null}
          </div>

          {/* AI Reasoning (if AI decision or preserved after override) */}
          {existingDecision.ai_reasoning && (
            <div className="mb-3 rounded-xl bg-purple-50 border border-purple-200 px-4 py-3">
              <p className="text-xs font-semibold text-purple-600 uppercase tracking-wider mb-1">🧠 AI Analysis</p>
              <p className="text-sm text-gray-700 leading-relaxed">{existingDecision.ai_reasoning}</p>
            </div>
          )}

          {/* Override Reason (if human overrode AI) */}
          {isHumanOverride && existingDecision.override_reason && (
            <div className="mb-3 rounded-xl bg-blue-50 border border-blue-200 px-4 py-3">
              <p className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-1">✏️ Override Reason</p>
              <p className="text-sm text-gray-700 leading-relaxed">{existingDecision.override_reason}</p>
            </div>
          )}

          {/* QA Comment */}
          {existingDecision.comment && (
            <div className="mb-4 rounded-xl bg-white border border-gray-200 px-4 py-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">💬 QA Comment</p>
              <p className="text-sm text-gray-700 leading-relaxed">{existingDecision.comment}</p>
            </div>
          )}

          {/* Override button */}
          <button
            onClick={handleStartEdit}
            className={`w-full py-3 rounded-xl font-bold text-sm transition-all shadow flex items-center justify-center gap-2 ${
              isAiDecision ? "bg-blue-600 hover:bg-blue-700 text-white" : "bg-gray-100 hover:bg-gray-200 text-gray-700 border border-gray-300"
            }`}
          >
            <span>✏️</span>
            <span>{isAiDecision ? "Override AI Decision" : "Edit Decision"}</span>
          </button>
        </div>
      </div>
    );
  }

  // ── Edit/Create mode ──
  return (
    <div className="mt-8 mb-4 mx-auto max-w-7xl print:hidden">
      <div className={`rounded-2xl shadow-md border-2 p-6 transition-all ${saved && selectedStyle ? `${selectedStyle.light} ${selectedStyle.ring} ring-2` : "bg-white border-gray-200"}`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">📋</span>
            <div>
              <h2 className="text-xl font-bold text-gray-900">QA Decision</h2>
              {clientName && <p className="text-sm text-gray-500">Client: <span className="font-semibold text-gray-700">{clientName}</span></p>}
            </div>
          </div>
          {isAiDecision && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-purple-50 border border-purple-200 text-purple-700 text-xs font-semibold">
              <span>🧠</span><span>Overriding AI verdict</span>
            </div>
          )}
        </div>

        {/* Show original AI reasoning when overriding */}
        {isAiDecision && existingDecision?.ai_reasoning && (
          <div className="mb-4 rounded-xl bg-purple-50 border border-purple-200 px-4 py-3">
            <p className="text-xs font-semibold text-purple-600 uppercase tracking-wider mb-1">🧠 Original AI Analysis (for reference)</p>
            <p className="text-sm text-gray-600 leading-relaxed italic">{existingDecision.ai_reasoning}</p>
          </div>
        )}

        {/* Verdict Buttons */}
        <div className="flex gap-3 mb-5">
          {(["approve", "reject", "review"] as const).map((v) => {
            const style = VERDICT_LABELS[v];
            const isSelected = verdict === v;
            return (
              <button key={v} onClick={() => { setVerdict(v); setSaved(false); }}
                className={`flex-1 py-3 px-4 rounded-xl text-white font-bold text-sm transition-all shadow-sm ${style.bg} ${isSelected ? `ring-4 ring-offset-2 ${style.ring} scale-105` : "opacity-80 hover:opacity-100"}`}>
                {style.label}
              </button>
            );
          })}
        </div>

        {/* Override Reason (only shown when overriding AI) */}
        {isAiDecision && (
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Override Reason <span className="text-gray-400 font-normal">(why are you changing the AI decision?)</span>
            </label>
            <input
              type="text"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="e.g. 'AI missed logo change at 0:08'"
              className="w-full rounded-xl border border-purple-300 px-4 py-2.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-purple-400 transition"
            />
          </div>
        )}

        {/* QA Comment */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            QA Comment <span className="text-gray-400 font-normal">(notes for the team, visible in knowledge base)</span>
          </label>
          <textarea
            value={comment}
            onChange={(e) => { setComment(e.target.value); setSaved(false); }}
            rows={3}
            placeholder="e.g. 'Background color difference at 0:04-0:07, acceptable compression artifact. Audio identical.'"
            className="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400 resize-none transition"
          />
        </div>

        {error && <p className="text-red-600 text-sm mb-3 font-medium">⚠️ {error}</p>}

        {/* Action Buttons */}
        <div className="flex gap-3">
          {existingDecision && isEditing && (
            <button onClick={handleCancel}
              className="flex-none py-3 px-5 rounded-xl font-bold text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 border border-gray-300 transition-all">
              Cancel
            </button>
          )}
          <button onClick={handleSave} disabled={saving || !verdict}
            className={`flex-1 py-3 rounded-xl text-white font-bold text-base transition-all shadow ${saving || !verdict ? "bg-gray-300 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700 active:scale-[0.98]"}`}>
            {saving ? "Saving..." : isAiDecision ? "💾 Save as Human Override" : "💾 Save decision and continue automation"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default QAVerdictPanel;
