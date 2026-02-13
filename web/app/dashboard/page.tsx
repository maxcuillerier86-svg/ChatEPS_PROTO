"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { apiFetch('/dashboard/me').then(r=>r.json()).then(setData).catch(()=>null); }, []);
  return <div className="card"><h2>Mon parcours novice → expert</h2><pre>{JSON.stringify(data, null, 2)}</pre></div>;
}
