import "./globals.css";
import Link from "next/link";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <main>
          <h1>Co-PE</h1>
          <nav style={{ display: "flex", gap: 12, marginBottom: 16 }}>
            <Link href="/login">Connexion</Link>
            <Link href="/chat">Chat</Link>
            <Link href="/library">Bibliothèque</Link>
            <Link href="/artifacts">Atelier</Link>
            <Link href="/dashboard">Progression</Link>
          </nav>
          {children}
        </main>
      </body>
    </html>
  );
}
