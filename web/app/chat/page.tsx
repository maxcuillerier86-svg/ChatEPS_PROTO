"use client";
import { useEffect, useRef, useState } from "react";
import { apiFetch, API_URL, getToken } from "../../lib/api";

type Conv = { id: number; title: string; mode: string };
type Citation = { doc_id?: number; title?: string; page?: number | string; excerpt?: string };
type Msg = { role: string; content: string; metadata_json?: { citations?: Citation[] } };

const MODES: [string, string][] = [
  ["co_design", "🛠 Co-conception"],
  ["exploration_novice", "🧭 Exploration (novice)"],
  ["critique", "🔍 Critique"],
  ["justification", "📖 Justification"],
  ["evaluation_reflexive", "🪞 Évaluation réflexive"],
];

const SUGGESTIONS = [
  "Aide-moi à créer un plan de séance de volleyball pour débutants, avec objectifs, différenciation et évaluation.",
  "Propose une situation d'apprentissage en athlétisme (course de haies) avec critères de réussite.",
  "Comment évaluer les compétences motrices de mes élèves de façon formative ?",
];

export default function ChatPage() {
  const [convs, setConvs] = useState<Conv[]>([]);
  const [convId, setConvId] = useState<number | null>(null);
  const [mode, setMode] = useState("co_design");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

  const loadConvs = async () => {
    try {
      const data = await (await apiFetch("/chat/conversations")).json();
      setConvs(Array.isArray(data) ? data : data?.items || []);
    } catch (e: any) {
      setError("Connectez-vous d'abord (onglet Connexion).");
    }
  };
  useEffect(() => { loadConvs(); }, []);
  useEffect(() => { if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight; }, [messages]);

  const createConv = async () => {
    try {
      const resp = await apiFetch("/chat/conversations", {
        method: "POST",
        body: JSON.stringify({ title: "Nouvelle discussion", mode }),
      });
      const c = await resp.json();
      setConvId(c.id);
      setMessages([]);
      loadConvs();
    } catch (e: any) { setError(e.message || "Échec de création"); }
  };

  const loadMsgs = async (c: Conv) => {
    setConvId(c.id);
    setMode(c.mode || "co_design");
    setMessages(await (await apiFetch(`/chat/conversations/${c.id}/messages`)).json());
  };

  const send = async () => {
    const content = input.trim();
    if (!content) return;
    let id = convId;
    if (!id) {
      await createConv();
      // createConv sets convId asynchronously; read from a fresh conversation
      try {
        const data = await (await apiFetch("/chat/conversations")).json();
        const items: Conv[] = Array.isArray(data) ? data : data?.items || [];
        id = items[0]?.id ?? null;
        setConvId(id);
      } catch { /* ignore */ }
      if (!id) return;
    }
    setError("");
    setInput("");
    setMessages((m) => [...m, { role: "user", content }, { role: "assistant", content: "" }]);
    setStreaming(true);
    try {
      const resp = await fetch(`${API_URL}/chat/conversations/${id}/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ content, use_rag: true, collection_ids: [], model: "" }),
      });
      if (!resp.ok || !resp.body) {
        const t = await resp.text();
        setMessages((m) => { const c = [...m]; c[c.length - 1] = { role: "assistant", content: `❌ ${t}` }; return c; });
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const line of parts) {
          if (!line.startsWith("data:")) continue;
          let data: any;
          try { data = JSON.parse(line.slice(5).trim()); } catch { continue; }
          if (data.token) {
            setMessages((m) => {
              const c = [...m];
              const last = c[c.length - 1];
              c[c.length - 1] = { ...last, content: last.content + data.token };
              return c;
            });
          }
          if (data.citations?.length) {
            setMessages((m) => {
              const c = [...m];
              const last = c[c.length - 1];
              c[c.length - 1] = { ...last, metadata_json: { citations: data.citations } };
              return c;
            });
          }
          if (data.error) {
            setMessages((m) => { const c = [...m]; c[c.length - 1] = { role: "assistant", content: `❌ ${data.error}` }; return c; });
          }
        }
      }
    } catch (e: any) {
      setMessages((m) => { const c = [...m]; c[c.length - 1] = { role: "assistant", content: `❌ ${e.message}` }; return c; });
    } finally {
      setStreaming(false);
    }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!streaming) send(); }
  };

  return (
    <div className="chat-shell">
      <div className="card" style={{ height: "fit-content" }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ fontSize: 16 }}>Discussions</h2>
          <button className="sm" onClick={createConv}>+ Nouveau</button>
        </div>
        <div className="conv-list" style={{ marginTop: 12 }}>
          {convs.length === 0 && <p className="muted">Aucune discussion pour l'instant.</p>}
          {convs.map((c) => (
            <div key={c.id} className={`conv ${convId === c.id ? "active" : ""}`} onClick={() => loadMsgs(c)}>
              <span className="conv-title">{c.title || "Sans titre"}</span>
              <span className="conv-mode">{(MODES.find((m) => m[0] === c.mode)?.[1] || c.mode || "").replace(/^\S+\s/, "")}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card chat-main">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <h2 style={{ fontSize: 16 }}>💬 Co-création</h2>
          <select value={mode} onChange={(e) => setMode(e.target.value)} style={{ width: "auto", maxWidth: 230, fontSize: 12.5, padding: "6px 9px" }}
            title="Posture pédagogique de l'IA">
            {MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>

        {error && <div className="alert err" style={{ marginBottom: 10 }}>{error}</div>}

        <div className="messages" ref={boxRef}>
          {messages.length === 0 ? (
            <div className="empty-chat">
              <div className="big">🏅</div>
              <h3>Lancez la co-création</h3>
              <p>Choisissez une idée ou écrivez votre message ci-dessous.</p>
              <div className="stack" style={{ marginTop: 14 }}>
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} className="ghost" style={{ textAlign: "left", fontWeight: 500 }} onClick={() => setInput(s)}>{s}</button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => {
              const isAi = m.role === "assistant";
              const cits = m.metadata_json?.citations || [];
              return (
                <div key={i} className={`turn ${isAi ? "ai" : "user"}`}>
                  <div className={`avatar ${isAi ? "ai" : "user"}`}>{isAi ? "🤖" : "🧑"}</div>
                  <div className="bubble-wrap">
                    <div className="bubble">
                      {isAi && m.content === "" && streaming
                        ? <span className="typing"><span></span><span></span><span></span></span>
                        : m.content}
                    </div>
                    {isAi && cits.length > 0 && (
                      <details className="citations">
                        <summary>📎 {cits.length} source(s) PDF</summary>
                        {cits.map((c, j) => (
                          <div className="cite" key={j}>
                            <b>{c.title || "Document"}</b> · p.{String(c.page ?? "?")}
                            <span className="ex">{c.excerpt}</span>
                          </div>
                        ))}
                      </details>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="composer">
          <div className="input-row">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKey}
              rows={2}
              placeholder="Écrivez votre message…  (Entrée pour envoyer, Maj+Entrée pour un saut de ligne)"
            />
            <button className="send-btn" onClick={send} disabled={streaming} title="Envoyer">
              {streaming ? <span className="spinner" /> : "➤"}
            </button>
          </div>
          <p className="muted" style={{ marginTop: 6 }}>💡 Les réponses s'appuient sur vos PDF (RAG) quand des sources sont disponibles.</p>
        </div>
      </div>
    </div>
  );
}
