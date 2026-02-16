"use client";
import { useState } from "react";
import { API_URL } from "../../lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("prof@cope.local");
  const [password, setPassword] = useState("password123");
  const [msg, setMsg] = useState("");

  const login = async () => {
    const r = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) return setMsg("Échec de connexion");
    const data = await r.json();
    localStorage.setItem("token", data.access_token);
    setMsg("Connecté");
  };

  return <div className="card"><h2>Connexion</h2><input value={email} onChange={e=>setEmail(e.target.value)}/><input type="password" value={password} onChange={e=>setPassword(e.target.value)}/><button onClick={login}>Se connecter</button><p>{msg}</p></div>;
}
