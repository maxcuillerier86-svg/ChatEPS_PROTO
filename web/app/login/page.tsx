"use client";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL, getToken } from "../../lib/api";

const DEMO = [
  ["Admin", "admin@cope.local"],
  ["Enseignant", "prof@cope.local"],
  ["Étudiant", "etudiant1@cope.local"],
] as const;

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("prof@cope.local");
  const [password, setPassword] = useState("password123");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null);
  const [alreadyIn, setAlreadyIn] = useState(false);

  useEffect(() => { setAlreadyIn(!!getToken()); }, []);

  const login = async (e?: FormEvent) => {
    e?.preventDefault();
    setLoading(true);
    setStatus(null);
    try {
      const r = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!r.ok) {
        let detail = "Identifiants invalides";
        try { detail = (await r.json()).detail || detail; } catch { /* ignore */ }
        setStatus({ ok: false, msg: detail });
        return;
      }
      const data = await r.json();
      localStorage.setItem("token", data.access_token);
      setAlreadyIn(true);
      setStatus({ ok: true, msg: "Connecté ! Redirection vers le chat…" });
      setTimeout(() => router.push("/chat"), 700);
    } catch (err: any) {
      setStatus({ ok: false, msg: "API injoignable — vérifiez que le backend tourne sur " + API_URL });
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    setAlreadyIn(false);
    setStatus({ ok: true, msg: "Déconnecté." });
  };

  return (
    <div style={{ maxWidth: 440, margin: "0 auto" }}>
      <div className="card">
        <h2>Connexion</h2>
        <p className="sub">Accédez à la plateforme avec un compte local.</p>

        {alreadyIn && (
          <div className="alert ok" style={{ marginBottom: 14 }}>
            Vous êtes déjà connecté. <button className="danger sm" onClick={logout} style={{ marginLeft: 6 }}>Se déconnecter</button>
          </div>
        )}

        <form onSubmit={login} className="stack">
          <div>
            <label className="field" htmlFor="email">Adresse e-mail</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
          </div>
          <div>
            <label className="field" htmlFor="pw">Mot de passe</label>
            <div className="row" style={{ flexWrap: "nowrap" }}>
              <input id="pw" type={show ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
              <button type="button" className="ghost sm" onClick={() => setShow((s) => !s)} title={show ? "Masquer" : "Afficher"}>
                {show ? "🙈" : "👁"}
              </button>
            </div>
          </div>
          <button type="submit" className="block" disabled={loading}>
            {loading ? <><span className="spinner" /> Connexion…</> : "Se connecter"}
          </button>
        </form>

        {status && <div className={`alert ${status.ok ? "ok" : "err"}`} style={{ marginTop: 14 }}>{status.msg}</div>}

        <div style={{ marginTop: 16 }}>
          <div className="muted" style={{ marginBottom: 6 }}>Comptes de démo (mot de passe <code>password123</code>)</div>
          <div className="row">
            {DEMO.map(([role, mail]) => (
              <button key={mail} type="button" className="ghost sm" onClick={() => { setEmail(mail); setPassword("password123"); }}>
                {role}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
