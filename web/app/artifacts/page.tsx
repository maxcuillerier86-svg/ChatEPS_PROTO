"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

export default function ArtifactsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [title, setTitle] = useState("Plan de séance");
  const [content, setContent] = useState("# Objectifs\n- ...");

  const load = async () => setItems(await (await apiFetch("/artefacts")).json());
  useEffect(() => { load().catch(()=>null); }, []);

  const create = async () => {
    await apiFetch("/artefacts", { method: "POST", body: JSON.stringify({ title, content_md: content }) });
    load();
  };

  return <div className="card"><h2>Atelier d’artefacts</h2><input value={title} onChange={e=>setTitle(e.target.value)}/><textarea value={content} onChange={e=>setContent(e.target.value)} rows={8}/><button onClick={create}>Créer</button>{items.map(i=><p key={i.id}>{i.title} - {i.status}</p>)}</div>;
}
