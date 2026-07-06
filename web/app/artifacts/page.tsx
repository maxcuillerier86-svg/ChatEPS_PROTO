"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

type Artifact = { id: number; title: string; status: string };

export default function ArtifactsPage() {
  const [items, setItems] = useState<Artifact[]>([]);
  const [title, setTitle] = useState("Plan de séance");
  const [content, setContent] = useState("# Objectifs\n- \n\n# Déroulement\n- \n\n# Évaluation\n- ");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null);

  const load = async () => {
    try { setItems(await (await apiFetch("/artefacts")).json()); }
    catch { setStatus({ ok: false, msg: "Connectez-vous pour voir vos artefacts." }); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!title.trim()) { setStatus({ ok: false, msg: "Le titre est requis." }); return; }
    setBusy(true); setStatus(null);
    try {
      await apiFetch("/artefacts", { method: "POST", body: JSON.stringify({ title: title.trim(), content_md: content }) });
      setStatus({ ok: true, msg: "Artefact créé." });
      load();
    } catch (e: any) { setStatus({ ok: false, msg: e.message || "Échec de création." }); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid">
      <div className="card" style={{ height: "fit-content" }}>
        <h2>Nouvel artefact</h2>
        <p className="sub">Rédigez en Markdown ; chaque enregistrement crée une version.</p>
        <div className="stack">
          <div>
            <label className="field" htmlFor="at">Titre</label>
            <input id="at" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="field" htmlFor="ac">Contenu (Markdown)</label>
            <textarea id="ac" value={content} onChange={(e) => setContent(e.target.value)} rows={10} style={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }} />
          </div>
          <button className="block" onClick={create} disabled={busy}>{busy ? <><span className="spinner" /> Création…</> : "Créer l'artefact"}</button>
          {status && <div className={`alert ${status.ok ? "ok" : "err"}`}>{status.msg}</div>}
        </div>
      </div>

      <div className="card">
        <h2>Mes artefacts</h2>
        <div style={{ marginTop: 12 }}>
          {items.length === 0 && <p className="muted">Aucun artefact pour le moment.</p>}
          {items.map((i) => (
            <div className="doc-item" key={i.id}>
              <span style={{ fontSize: 18 }}>🛠️</span>
              <span className="doc-title">{i.title}</span>
              <span className="status-badge status-pending">{i.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
