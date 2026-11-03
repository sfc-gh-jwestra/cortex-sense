import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Gaming Analytics: Three Agents, With and Without Cortex Sense",
  description: "Side-by-side comparison of a semantic view agent, a capable analyst agent and a Cortex Sense agent on 10 gaming portfolio questions",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[var(--bg)] text-[var(--text)] antialiased">
        <header className="border-b border-[var(--border)] bg-[var(--bg-card)]">
          <div className="max-w-7xl mx-auto px-6 py-5">
            <h1 className="text-2xl font-bold tracking-tight">Gaming Analytics: Three Agents, With and Without Cortex Sense</h1>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
