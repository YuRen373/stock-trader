import type { Analysis } from "../types";

const colors: Record<string, string> = {
  "STRONG BUY": "from-green-800 to-green-700",
  BUY: "from-green-700 to-green-600",
  HOLD: "from-orange-700 to-orange-600",
  SELL: "from-red-700 to-red-600",
  "STRONG SELL": "from-red-800 to-red-700",
};

export default function SignalBadge({ analysis }: { analysis: Analysis }) {
  const bg = colors[analysis.signal] ?? "from-gray-700 to-gray-600";
  return (
    <div className={`bg-gradient-to-br ${bg} rounded-xl p-5 text-center text-white`}>
      <div className="text-2xl font-bold">{analysis.signal}</div>
      <div className="text-sm mt-1 opacity-80">Score: {analysis.score >= 0 ? "+" : ""}{analysis.score.toFixed(1)}</div>
    </div>
  );
}
