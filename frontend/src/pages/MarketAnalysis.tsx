import { useState, useEffect } from "react";
import { useOutletContext } from "react-router-dom";
import { getStock } from "../api/client";
import type { StockData } from "../types";
import SignalBadge from "../components/SignalBadge";
import StockChart from "../components/StockChart";

function fmt(n: number) {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-900 rounded-lg p-3 text-center border border-gray-800">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-sm font-semibold">{value}</div>
    </div>
  );
}

export default function MarketAnalysis() {
  const { watchlist, period } = useOutletContext<{ watchlist: string[]; period: string }>();
  const [active, setActive] = useState<string>("");
  const [stock, setStock] = useState<StockData | null>(null);
  const [loading, setLoading] = useState(false);
  const [showFundamentals, setShowFundamentals] = useState(false);

  useEffect(() => {
    if (watchlist.length && !active) setActive(watchlist[0]);
  }, [watchlist, active]);

  useEffect(() => {
    if (!active) return;
    setLoading(true);
    getStock(active, period).then(setStock).finally(() => setLoading(false));
  }, [active, period]);

  if (!watchlist.length) return <p className="text-gray-500">Add a ticker in the sidebar to get started.</p>;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Market Analysis</h1>

      {/* Ticker tabs */}
      <div className="flex gap-1 mb-6 flex-wrap">
        {watchlist.map((t) => (
          <button
            key={t}
            onClick={() => setActive(t)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              active === t ? "bg-teal-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading && <p className="text-gray-500">Loading {active}...</p>}

      {stock && !loading && (
        <>
          {/* Header row */}
          <div className="flex gap-6 items-start mb-6">
            <div className="flex-1">
              <h2 className="text-xl font-bold">{stock.name} ({stock.ticker})</h2>
              <p className="text-sm text-gray-500 mb-3">{stock.sector} | {stock.industry}</p>

              <div className="grid grid-cols-4 gap-3">
                <Metric label="Price" value={`$${stock.price.toFixed(2)}`} />
                <Metric label="Day High" value={`$${stock.high.toFixed(2)}`} />
                <Metric label="Day Low" value={`$${stock.low.toFixed(2)}`} />
                <Metric label="Volume" value={stock.volume >= 1e6 ? `${(stock.volume / 1e6).toFixed(1)}M` : stock.volume.toLocaleString()} />
              </div>

              <div className="mt-2 text-sm">
                <span className={stock.change >= 0 ? "text-green-400" : "text-red-400"}>
                  {stock.change >= 0 ? "+" : ""}{stock.change.toFixed(2)} ({stock.change_pct >= 0 ? "+" : ""}{stock.change_pct.toFixed(2)}%)
                </span>
              </div>
            </div>
            <div className="w-52">
              <SignalBadge analysis={stock.analysis} />
            </div>
          </div>

          {/* Fundamentals */}
          <button
            onClick={() => setShowFundamentals(!showFundamentals)}
            className="text-sm text-gray-400 hover:text-white mb-3 flex items-center gap-1"
          >
            <span>{showFundamentals ? "v" : ">"}</span> Fundamentals
          </button>
          {showFundamentals && (
            <div className="grid grid-cols-5 gap-3 mb-6">
              <Metric label="Market Cap" value={stock.market_cap ? fmt(stock.market_cap) : "N/A"} />
              <Metric label="P/E Ratio" value={stock.pe_ratio ? stock.pe_ratio.toFixed(1) : "N/A"} />
              <Metric label="EPS" value={stock.eps ? `$${stock.eps.toFixed(2)}` : "N/A"} />
              <Metric label="Div Yield" value={stock.dividend_yield ? `${(stock.dividend_yield * 100).toFixed(2)}%` : "N/A"} />
              <Metric label="52W Range" value={`$${stock.week52_low?.toFixed(0) ?? "?"}-$${stock.week52_high?.toFixed(0) ?? "?"}`} />
            </div>
          )}

          {/* Chart */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-2 mb-6">
            <StockChart data={stock.chart} ticker={stock.ticker} />
          </div>

          {/* Analysis breakdown */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <h3 className="font-semibold mb-3">Analysis Breakdown</h3>
            <ul className="space-y-1 text-sm">
              {stock.analysis.details.map((d, i) => {
                const bull = /Bullish|Buy|uptrend|bounce/i.test(d);
                const bear = /Bearish|Sell|downtrend|pullback/i.test(d);
                return (
                  <li key={i} className={bull ? "text-green-400" : bear ? "text-red-400" : "text-gray-400"}>
                    - {d}
                  </li>
                );
              })}
            </ul>
            <p className="text-xs text-gray-600 mt-4">
              Disclaimer: This is based on technical indicators only and is not financial advice.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
