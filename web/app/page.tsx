import Link from "next/link";

const features = [
  { ico: "💬", title: "Chat de co-création", desc: "Dialogue IA-Humain avec postures pédagogiques (novice → expert) et streaming en direct." },
  { ico: "📚", title: "Bibliothèque PDF (RAG)", desc: "Ingestion locale de vos documents et réponses ancrées avec citations de sources." },
  { ico: "🛠️", title: "Atelier d'artefacts", desc: "Créez et versionnez vos plans de séance et supports pédagogiques." },
  { ico: "📈", title: "Progression", desc: "Suivi de votre parcours et indicateurs de co-création, dans le respect du consentement." },
];

export default function Home() {
  return (
    <div>
      <div className="card">
        <div className="hero">
          <div className="big">🏅</div>
          <h2>Plateforme Co-PE prête à l'emploi</h2>
          <p className="sub" style={{ maxWidth: 560, margin: "6px auto 0" }}>
            Concevez, itérez et évaluez vos séances d'EPS avec un assistant IA local — vos PDF comme sources,
            aucune donnée envoyée dans le cloud.
          </p>
          <div className="cta-row">
            <Link className="btn" href="/chat">Ouvrir le chat →</Link>
            <Link className="btn ghost" href="/login" style={{ textDecoration: "none" }}>Se connecter</Link>
          </div>
        </div>

        <div className="features">
          {features.map((f) => (
            <div className="feature" key={f.title}>
              <div className="ico">{f.ico}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Pour commencer</h2>
        <ol className="stack" style={{ paddingLeft: 18 }}>
          <li>Connectez-vous avec un compte de démonstration (ex. <code>prof@cope.local</code> / <code>password123</code>).</li>
          <li>Ajoutez vos <Link href="/library">PDF</Link> pour enrichir les réponses.</li>
          <li>Lancez une discussion dans le <Link href="/chat">Chat</Link> et itérez votre séance.</li>
          <li>Suivez votre <Link href="/dashboard">progression</Link> pédagogique.</li>
        </ol>
      </div>
    </div>
  );
}
