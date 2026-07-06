"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  ["Accueil", "/"],
  ["Connexion", "/login"],
  ["Chat", "/chat"],
  ["Bibliothèque", "/library"],
  ["Atelier", "/artifacts"],
  ["Progression", "/dashboard"],
] as const;

export default function NavBar() {
  const pathname = usePathname();
  return (
    <div className="topbar">
      <div className="topbar-inner">
        <div className="brand">
          <span className="logo">UQÀM</span>
          <div className="titles">
            <h1>Co-PE · chat-EPS</h1>
            <p>Co-création IA-Humain pour l'EPS (local, sans cloud)</p>
          </div>
        </div>
        <nav className="nav">
          {nav.map(([label, href]) => (
            <Link key={href} href={href} className={pathname === href ? "active" : ""}>
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}
