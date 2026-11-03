import { TokenUsage } from "@/lib/types";

const num = (n: number) => n.toLocaleString("en-US");

/** Total tokens with the input/output split on hover. Renders nothing when usage is unknown. */
export default function TokenCount({ t, suffix = "" }: { t?: TokenUsage | null; suffix?: string }) {
  if (!t) return null;
  const tip = `Input ${num(t.input)} (${num(t.cacheRead)} read from cache), output ${num(t.output)}`;
  return <span title={tip}>{num(t.total)}{suffix}</span>;
}
