"use client";
import Tabs from "@/components/Tabs";
import ContextView from "@/components/context/ContextView";
import ComparisonView from "@/components/comparison/ComparisonView";
import AnalysisView from "@/components/analysis/AnalysisView";

export default function Home() {
  return (
    <Tabs
      tabs={[
        { id: "context", label: "Setup" },
        { id: "comparison", label: "Comparison" },
        { id: "analysis", label: "Analysis" },
      ]}
      children={{
        context: <ContextView />,
        comparison: <ComparisonView />,
        analysis: <AnalysisView />,
      }}
    />
  );
}
