import { useState, useEffect } from "react";
import Plot from "react-plotly.js";
import { getPortfolio, getTransactions } from "../api/client";
import type { Portfolio as PortfolioType, Transaction } from "../types";

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800 text-center">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-lg font-bold">{value}</div>
      {sub && <div className="text-xs mt-0.5">{sub}</div>}
    </div>
  );
}

export default function Portfolio() {
  const [portfolio, setPortfolio] = useState<PortfolioType | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);

  useEffect(() => {
    getPortfolio().then(setPortfolio);
    getTransactions().then(setTransactions);
  }, []);

  if (!portfolio) return <p className="text-gray-500">Loading...</p>;

  const invested = portfolio.portfolio_value - portfolio.cash;
  const txnAsc = [...transactions].reverse();

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Portfolio Dashboard</h1>

      {/* Top metrics */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <Metric label="Total Value"
          value={`$${portfolio.portfolio_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          sub={`${portfolio.total_pnl_pct >= 0 ? "+" : ""}${portfolio.total_pnl_pct.toFixed(2)}%`} />
        <Metric label="Cash" value={`$${portfolio.cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
        <Metric label="Invested" value={`$${invested.toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
        <Metric label="Total P&L"
          value={`$${portfolio.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          sub={portfolio.total_pnl >= 0 ? "Profit" : "Loss"} />
      </div>

      {/* Portfolio value chart */}
      {txnAsc.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-2 mb-6">
          <Plot
            data={[{
              type: "scatter",
              x: txnAsc.map((t) => t.date),
              y: txnAsc.map((t) => t.portfolio_value),
              mode: "lines+markers",
              line: { color: "#26a69a", width: 2 },
              fill: "tozeroy",
              fillcolor: "rgba(38,166,154,0.1)",
            }]}
            layout={{
              title: { text: "Portfolio Value Over Time" },
              // @ts-expect-error plotly template string
              template: "plotly_dark",
              height: 300,
              margin: { t: 40, b: 30, l: 60, r: 20 },
              yaxis: { title: { text: "Value ($)" } },
              paper_bgcolor: "rgba(0,0,0,0)",
              plot_bgcolor: "rgba(0,0,0,0)",
              shapes: [{ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: 100000, y1: 100000, line: { color: "white", dash: "dash", width: 1 } }],
            }}
            useResizeHandler
            style={{ width: "100%" }}
            config={{ displayModeBar: false }}
          />
        </div>
      )}

      {/* Holdings */}
      <h2 className="text-lg font-semibold mb-3">Current Holdings</h2>
      {portfolio.holdings.length ? (
        <>
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 mb-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-left border-b border-gray-800">
                  <th className="pb-2">Ticker</th><th className="pb-2 text-right">Shares</th>
                  <th className="pb-2 text-right">Avg Cost</th><th className="pb-2 text-right">Current</th>
                  <th className="pb-2 text-right">Market Value</th><th className="pb-2 text-right">Cost Basis</th>
                  <th className="pb-2 text-right">P&L</th><th className="pb-2 text-right">P&L %</th>
                  <th className="pb-2 text-right">Alloc %</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.holdings.map((h) => (
                  <tr key={h.ticker} className="border-b border-gray-800/50">
                    <td className="py-1.5 font-medium">{h.ticker}</td>
                    <td className="text-right">{h.shares}</td>
                    <td className="text-right">${h.avg_price.toFixed(2)}</td>
                    <td className="text-right">${h.current_price.toFixed(2)}</td>
                    <td className="text-right">${h.market_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                    <td className="text-right">${h.cost_basis.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                    <td className={`text-right ${h.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      ${h.pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className={`text-right ${h.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct.toFixed(2)}%
                    </td>
                    <td className="text-right">{h.allocation_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Allocation pie */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-2 mb-6">
            <Plot
              data={[{
                type: "pie",
                labels: [...portfolio.holdings.map((h) => h.ticker), ...(portfolio.cash > 0 ? ["Cash"] : [])],
                values: [...portfolio.holdings.map((h) => h.market_value), ...(portfolio.cash > 0 ? [portfolio.cash] : [])],
                hole: 0.4,
              }]}
              layout={{
                title: { text: "Portfolio Allocation" },
                // @ts-expect-error plotly template string
                template: "plotly_dark",
                height: 400,
                margin: { t: 40, b: 20, l: 20, r: 20 },
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
              }}
              useResizeHandler
              style={{ width: "100%" }}
              config={{ displayModeBar: false }}
            />
          </div>
        </>
      ) : (
        <p className="text-gray-500 text-sm mb-6">No holdings yet. Go to Paper Trading to buy stocks!</p>
      )}

      {/* Performance stats + full history */}
      {transactions.length > 0 && (
        <>
          <h2 className="text-lg font-semibold mb-3">Performance Statistics</h2>
          <div className="grid grid-cols-4 gap-4 mb-6">
            <Metric label="Total Buys" value={String(transactions.filter((t) => t.type === "BUY").length)} />
            <Metric label="Total Sells" value={String(transactions.filter((t) => t.type === "SELL").length)} />
            <Metric label="Total Bought" value={`$${transactions.filter((t) => t.type === "BUY").reduce((s, t) => s + t.total, 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
            <Metric label="Total Sold" value={`$${transactions.filter((t) => t.type === "SELL").reduce((s, t) => s + t.total, 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
          </div>

          <h2 className="text-lg font-semibold mb-3">Full Transaction History</h2>
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-left border-b border-gray-800">
                  <th className="pb-2">Date</th><th className="pb-2">Type</th><th className="pb-2">Ticker</th>
                  <th className="pb-2 text-right">Shares</th><th className="pb-2 text-right">Price</th>
                  <th className="pb-2 text-right">Total</th><th className="pb-2 text-right">Portfolio Value</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t, i) => (
                  <tr key={i} className="border-b border-gray-800/50">
                    <td className="py-1.5 text-gray-400">{t.date}</td>
                    <td className={t.type === "BUY" ? "text-green-400" : "text-red-400"}>{t.type}</td>
                    <td>{t.ticker}</td>
                    <td className="text-right">{t.shares}</td>
                    <td className="text-right">${t.price.toFixed(2)}</td>
                    <td className="text-right">${t.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                    <td className="text-right">${t.portfolio_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
