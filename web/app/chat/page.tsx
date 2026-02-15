"use client";
import { useEffect, useState } from "react";
import { apiFetch, API_URL, getToken } from "../../lib/api";

type Conv = { id: number; title: string; mode: string };

type Msg = { role: string; content: string; metadata_json?: { citations?: any[] } };

export default function ChatPage() {
  const [convs, setConvs] = useState<Conv[]>([]);
  const [convId, setConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("Aide-moi à créer un plan de séance volleyball.");

  const loadConvs = async () => setConvs(await (await apiFetch("/chat/conversations")).json());

  useEffect(() => { loadConvs().catch(() => null); }, []);

  const createConv = async () => {
    const resp = await apiFetch("/chat/conversations", { method: "POST", body: JSON.stringify({ title: "Nouveau fil", mode: "co_design" }) });
    const c = await resp.json();
    setConvId(c.id);
    loadConvs();
  };

  const loadMsgs = async (id: number) => {
    setConvId(id);
    setMessages(await (await apiFetch(`/chat/conversations/${id}/messages`)).json());
  };

  const send = async () => {
    if (!convId) return;
    setMessages((m) => [...m, { role: "user", content: input }, { role: "assistant", content: "" }]);
    const resp = await fetch(`${API_URL}/chat/conversations/${convId}/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
      body: JSON.stringify({ content: input, use_rag: true, collection_ids: [] }),
    });
    const reader = resp.body?.getReader();
    const decoder = new TextDecoder();
    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      chunk.split("\n\n").forEach((line) => {
        if (!line.startsWith("data:")) return;
        const data = JSON.parse(line.replace("data:", "").trim());
        if (data.token) {
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], content: copy[copy.length - 1].content + data.token };
            return copy;
          });
        }
      });
    }
  };

  return <div className="grid"><div className="card"><button onClick={createConv}>Nouveau fil</button>{convs.map(c=><p key={c.id}><button onClick={()=>loadMsgs(c.id)}>{c.title} ({c.mode})</button></p>)}</div><div className="card"><h2>Co-création</h2><div style={{minHeight:300}}>{messages.map((m,i)=><p key={i}><b>{m.role}:</b> {m.content}</p>)}</div><textarea value={input} onChange={e=>setInput(e.target.value)} rows={4}/><button onClick={send}>Envoyer</button></div></div>;
}
