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
            <p className="text-sm text-[var(--text-muted)] mt-1">
              GAME_AGENT_FINANCE (Cortex Analyst over SV_GAME_SALES), GAME_AGENT_ANALYST (Cortex Analyst plus catalog
              search and its own SQL) and GAME_AGENT_SENSE (Cortex Sense context: catalog, feedback rules, query history and
              knowledge documents). 10 questions: 2 ties, 8 that need data or rules outside the semantic view.
            </p>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
