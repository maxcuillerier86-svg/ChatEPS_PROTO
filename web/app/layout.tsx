import "./globals.css";
import Link from "next/link";

const nav = [
  ["Accueil", "/"],
  ["Connexion", "/login"],
  ["Chat", "/chat"],
  ["Bibliothèque", "/library"],
  ["Atelier", "/artifacts"],
  ["Progression", "/dashboard"],
] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <main>
          <header className="card" style={{ marginTop: 12 }}>
            <h1 style={{ margin: 0 }}>Co-PE</h1>
            <p style={{ margin: "8px 0 0 0" }}>Co-création pédagogique en EPS (local, sans cloud)</p>
            <nav style={{ display: "flex", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
              {nav.map(([label, href]) => (
                <Link key={href} href={href}>
                  {label}
                </Link>
              ))}
            </nav>
          </header>
          {children}
        </main>
      </body>
    </html>
  );
}
