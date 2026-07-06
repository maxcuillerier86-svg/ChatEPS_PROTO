"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

type TL = { type: string; at: string; payload?: any };
type Data = {
  metrics?: { iterations?: number; chat_turns?: number; source_usage?: number; metacognition_prompts?: number };
  timeline?: TL[];
};

const METRIC_LABELS: [keyof NonNullable<Data["metrics"]>, string, string][] = [
  ["chat_turns", "Échanges de chat", "💬"],
  ["iterations", "Itérations d'artefacts", "🔁"],
  ["source_usage", "Réponses sourcées", "📎"],
  ["metacognition_prompts", "Moments métacognitifs", "🧠"],
];

const EVENT_LABELS: Record<string, string> = {
  conversation_create: "Nouvelle discussion",
  conversation_rename: "Discussion renommée",
  conversation_delete: "Discussion supprimée",
  chat_turn: "Échange de chat",
  artifact_iteration: "Itération d'artefact",
  metacognition: "Métacognition",
};

export default function DashboardPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch("/dashboard/me")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setError("Connectez-vous pour voir votre progression."));
  }, []);

  const fmtDate = (s: string) => { try { return new Date(s).toLocaleString("fr-CA"); } catch { return s; } };

  return (
    <div>
      <div className="card">
        <h2>Mon parcours novice → expert</h2>
        <p className="sub">Indicateurs de co-création issus de vos traces d'activité.</p>
        {error && <div className="alert err">{error}</div>}
        {!error && !data && <p className="muted">Chargement…</p>}
        {data && (
          <div className="tiles">
            {METRIC_LABELS.map(([key, label, ico]) => (
              <div className="tile" key={key}>
                <div className="n">{data.metrics?.[key] ?? 0}</div>
                <div className="l">{ico} {label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {data?.timeline && data.timeline.length > 0 && (
        <div className="card">
          <h2>Activité récente</h2>
          <div className="timeline">
            {[...data.timeline].reverse().map((e, i) => (
              <div className="tl-item" key={i}>
                <span className="t">{EVENT_LABELS[e.type] || e.type}</span>
                <span className="at">{fmtDate(e.at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
