"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { API_URL, getToken } from "../../lib/api";

type Doc = { id: number; title: string; status: string };

function StatusBadge({ status }: { status: string }) {
  const cls = status === "ready" ? "status-ready" : status === "failed" ? "status-failed" : "status-pending";
  const label = status === "ready" ? "prêt" : status === "failed" ? "échec" : status;
  return <span className={`status-badge ${cls}`}>{label}</span>;
}

export default function LibraryPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    try {
      const r = await fetch(`${API_URL}/library/documents`, { headers: { Authorization: `Bearer ${getToken()}` } });
      if (r.ok) setDocs(await r.json());
      else setStatus({ ok: false, msg: "Connectez-vous pour voir vos documents." });
    } catch { setStatus({ ok: false, msg: "API injoignable." }); }
  };
  useEffect(() => { load(); }, []);

  const pick = (f: File | null) => {
    setFile(f);
    if (f && !title.trim()) setTitle(f.name.replace(/\.pdf$/i, ""));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) { setStatus({ ok: false, msg: "Choisissez un fichier PDF." }); return; }
    setBusy(true);
    setStatus(null);
    try {
      const form = new FormData();
      form.set("title", title.trim() || file.name.replace(/\.pdf$/i, ""));
      form.set("file", file);
      const r = await fetch(`${API_URL}/library/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: form,
      });
      if (!r.ok) throw new Error(await r.text());
      setStatus({ ok: true, msg: "PDF envoyé et en cours d'indexation." });
      setFile(null); setTitle("");
      if (fileRef.current) fileRef.current.value = "";
      load();
    } catch (err: any) {
      setStatus({ ok: false, msg: err.message || "Échec de l'upload." });
    } finally { setBusy(false); }
  };

  return (
    <div className="grid">
      <div className="card" style={{ height: "fit-content" }}>
        <h2>Ajouter un PDF</h2>
        <p className="sub">Vos documents deviennent des sources pour le chat (RAG).</p>
        <form onSubmit={submit} className="stack">
          <div>
            <label className="field" htmlFor="t">Titre du document</label>
            <input id="t" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Ex. Guide didactique EPS" />
          </div>
          <input ref={fileRef} type="file" accept="application/pdf" hidden onChange={(e) => pick(e.target.files?.[0] || null)} />
          <div
            className={`dropzone ${drag ? "drag" : ""}`}
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f?.type === "application/pdf") pick(f); }}
          >
            {file ? <>📄 <b>{file.name}</b><br /><span className="muted">Prêt à uploader</span></>
                  : <><b>Cliquez</b> ou glissez un PDF ici<br /><span className="muted">Le document sera indexé pour le RAG</span></>}
          </div>
          <button className="block" disabled={busy}>{busy ? <><span className="spinner" /> Ingestion…</> : "Uploader le PDF"}</button>
        </form>
        {status && <div className={`alert ${status.ok ? "ok" : "err"}`} style={{ marginTop: 12 }}>{status.msg}</div>}
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>Bibliothèque PDF</h2>
          <button className="ghost sm" onClick={load}>↻ Rafraîchir</button>
        </div>
        <div style={{ marginTop: 12 }}>
          {docs.length === 0 && <p className="muted">Aucun document pour le moment.</p>}
          {docs.map((d) => (
            <div className="doc-item" key={d.id}>
              <span style={{ fontSize: 18 }}>📄</span>
              <span className="doc-title">{d.title}</span>
              <StatusBadge status={d.status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
