"use client";
import { useState } from "react";

interface TabsProps {
  tabs: { id: string; label: string }[];
  children: Record<string, React.ReactNode>;
}

export default function Tabs({ tabs, children }: TabsProps) {
  const [active, setActive] = useState(tabs[0].id);

  return (
    <div>
      <div className="flex gap-1 border-b border-[var(--border)] mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
              active === tab.id
                ? "border-[var(--sense)] text-[var(--sense)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div>{children[active]}</div>
    </div>
  );
}
