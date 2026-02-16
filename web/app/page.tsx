import Link from "next/link";

export default function Home() {
  return (
    <div className="card">
      <h2>Plateforme Co-PE prête à l’emploi</h2>
      <ul>
        <li>💬 Chat de co-création IA-Humain (modes novice/expert).</li>
        <li>📚 Banque PDF avec ingestion RAG locale et citations.</li>
        <li>🛠️ Atelier d’artefacts versionnés.</li>
        <li>📈 Dashboard de progression pédagogique et consentement.</li>
      </ul>
      <p>
        Commencez par <Link href="/login">vous connecter</Link>, puis ouvrez <Link href="/chat">Chat</Link>.
      </p>
    </div>
  );
}
