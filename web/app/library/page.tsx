"use client";
import { FormEvent, useEffect, useState } from "react";
import { API_URL, getToken } from "../../lib/api";

export default function LibraryPage() {
  const [docs, setDocs] = useState<any[]>([]);
  const [title, setTitle] = useState("Document EPS");
  const [file, setFile] = useState<File | null>(null);

  const load = async () => {
    const r = await fetch(`${API_URL}/library/documents`, { headers: { Authorization: `Bearer ${getToken()}` } });
    if (r.ok) setDocs(await r.json());
  };
  useEffect(() => { load(); }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.set("title", title); form.set("file", file);
    await fetch(`${API_URL}/library/upload`, { method: "POST", headers: { Authorization: `Bearer ${getToken()}` }, body: form });
    load();
  };

  return <div className="card"><h2>Bibliothèque PDF</h2><form onSubmit={submit}><input value={title} onChange={e=>setTitle(e.target.value)}/><input type="file" accept="application/pdf" onChange={e=>setFile(e.target.files?.[0]||null)}/><button>Uploader</button></form>{docs.map(d=><p key={d.id}>{d.title} - {d.status}</p>)}</div>;
}
