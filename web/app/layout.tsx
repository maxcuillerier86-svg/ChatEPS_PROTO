import "./globals.css";
import type { Metadata } from "next";
import NavBar from "./nav";

export const metadata: Metadata = {
  title: "Co-PE · chat-EPS",
  description: "Co-création IA-Humain pour l'Éducation Physique et Sportive (local, sans cloud).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <NavBar />
        <main>{children}</main>
      </body>
    </html>
  );
}
