"use client";

import { useState } from "react";

export function ObsidianAutosaveSettings(props: { onChange?: (v: any) => void }) {
  const [enabled, setEnabled] = useState(false);
  const [mode, setMode] = useState("manual-only");
  const [folder, setFolder] = useState("ChatEPS/session");

  const emit = (next: any) => props.onChange?.({ enabled, mode, folder, ...next });

  return (
    <div className="rounded-lg border p-3 space-y-2">
      <h4 className="font-semibold">Obsidian Auto-save</h4>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => {
            setEnabled(e.target.checked);
            emit({ enabled: e.target.checked });
          }}
        />
        Activer auto-save
      </label>
      <select
        value={mode}
        onChange={(e) => {
          setMode(e.target.value);
          emit({ mode: e.target.value });
        }}
        className="border rounded px-2 py-1 text-sm"
      >
        <option value="manual-only">manual-only</option>
        <option value="per-message">per-message</option>
        <option value="daily-note-append">daily-note-append</option>
        <option value="canonical-only">canonical-only</option>
      </select>
      <input
        value={folder}
        onChange={(e) => {
          setFolder(e.target.value);
          emit({ folder: e.target.value });
        }}
        className="w-full border rounded px-2 py-1 text-sm"
        placeholder="Dossier cible"
      />
    </div>
  );
}
