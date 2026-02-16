"use client";

import { useState } from "react";

export function SaveToObsidianButton(props: { payload: any; apiBase?: string }) {
  const [status, setStatus] = useState<string>("");

  async function save() {
    try {
      setStatus("⏳");
      const res = await fetch(`${props.apiBase || "http://localhost:8000"}/obsidian/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Pseudo": "WebUser" },
        body: JSON.stringify(props.payload),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setStatus(data?.saved?.open_uri ? `✅ ${data.saved.path}` : "✅");
    } catch (e: any) {
      setStatus(`❌ ${e.message}`);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button onClick={save} className="rounded bg-blue-600 text-white px-3 py-1 text-sm">
        Save to Obsidian
      </button>
      <span className="text-xs text-slate-600">{status}</span>
    </div>
  );
}
