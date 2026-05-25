import { useState, useEffect } from "react";
import { useOutletContext } from "react-router-dom";
import { getPortfolio, getStock, getPrice, executeBuy, executeSell, getTransactions, resetPortfolio } from "../api/client";
import type { Portfolio, Transaction, Analysis } from "../types";
import SignalBadge from "../components/SignalBadge";

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800 text-center">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-lg font-bold">{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function PaperTrading() {
  const { watchlist } = useOutletContext<{ watchlist: string[]; period: string }>();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [suggestions, setSuggestions] = useState<{ ticker: string; price: number; analysis: Analysis }[]>([]);

  // Buy form
  const [buyTicker, setBuyTicker] = useState("");
  const [buyShares, setBuyShares] = useState(1);
  const [buyPrice, setBuyPrice] = useState<number | null>(null);
  const [buyMsg, setBuyMsg] = useState("");

  // Sell form
  const [sellTicker, setSellTicker] = useState("");
  const [sellShares, setSellShares] = useState(1);
  const [sellPrice, setSellPrice] = useState<number | null>(null);
  const [sellMsg, setSellMsg] = useState("");

  const refresh = () => {
    getPortfolio().then(setPortfolio);
    getTransactions(20).then(setTransactions);
  };

  useEffect(refresh, []);

  useEffect(() => {
    if (watchlist.length && !buyTicker) setBuyTicker(watchlist[0]);
  }, [watchlist, buyTicker]);

  useEffect(() => {
    if (portfolio?.holdings.length && !sellTicker) setSellTicker(portfolio.holdings[0].ticker);
  }, [portfolio, sellTicker]);

  // Fetch buy price
  useEffect(() => {
    if (!buyTicker) return;
    setBuyPrice(null);
    getPrice(buyTicker).then(setBuyPrice).catch(() => setBuyPrice(null));
  }, [buyTicker]);

  // Fetch sell price
  useEffect(() => {
    if (!sellTicker) return;
    setSellPrice(null);
    getPrice(sellTicker).then(setSellPrice).catch(() => setSellPrice(null));
  }, [sellTicker]);

  // AI suggestions
  useEffect(() => {
    Promise.all(
      watchlist.slice(0, 5).map(async (t) => {
        try {
          const s = await getStock(t, "6mo");
          return { ticker: t, price: s.price, analysis: s.analysis };
        } catch {
          return null;
        }
      })
    ).then((r) => setSuggestions(r.filter(Boolean) as typeof suggestions));
  }, [watchlist]);

  const handleBuy = async () => {
    try {
      setBuyMsg("");
      const res = await executeBuy(buyTicker, buyShares);
      setBuyMsg(res.message);
      refresh();
    } catch (e: unknown) {
      setBuyMsg(e instanceof Error ? e.message : "Buy failed");
    }
  };

  const handleSell = async () => {
    try {
      setSellMsg("");
      const res = await executeSell(sellTicker, sellShares);
      setSellMsg(res.message);
      refresh();
    } catch (e: unknown) {
      setSellMsg(e instanceof Error ? e.message : "Sell failed");
    }
  };

  const handleReset = async () => {
    await resetPortfolio();
    refresh();
  };

  const maxBuyShares = buyPrice && portfolio ? Math.floor(portfolio.cash / buyPrice) : 0;
  const sellHolding = portfolio?.holdings.find((h) => h.ticker === sellTicker);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Paper Trading</h1>
      <p className="text-sm text-gray-500 mb-6">Trade with $100,000 virtual cash. Prices are real-time from Yahoo Finance.</p>

      {/* Portfolio summary */}
      {portfolio && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <Metric label="Portfolio Value" value={`$${portfolio.portfolio_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
            sub={`${portfolio.total_pnl >= 0 ? "+" : ""}${portfolio.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })} (${portfolio.total_pnl_pct >= 0 ? "+" : ""}${portfolio.total_pnl_pct.toFixed(2)}%)`} />
          <Metric label="Cash Available" value={`$${portfolio.cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
          <Metric label="Invested" value={`$${(portfolio.portfolio_value - portfolio.cash).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
          <Metric label="Total Trades" value={String(transactions.length)} />
        </div>
      )}

      {/* Buy / Sell panels */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Buy */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-semibold mb-3">Buy Stock</h2>
          <select value={buyTicker} onChange={(e) => setBuyTicker(e.target.value)}
            className="w-full bg-gray-800 text-white rounded px-3 py-2 mb-3 outline-none text-sm">
            {watchlist.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>

          {buyPrice !== null && (
            <>
              <p className="text-sm text-teal-400 mb-2">Current price: ${buyPrice.toFixed(2)} | Max shares: {maxBuyShares}</p>
              <input type="number" min={1} max={maxBuyShares} value={buyShares}
                onChange={(e) => setBuyShares(Math.max(1, Number(e.target.value)))}
                className="w-full bg-gray-800 text-white rounded px-3 py-2 mb-2 outline-none text-sm" />
              <p className="text-sm text-gray-400 mb-3">Total cost: ${(buyShares * buyPrice).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
              <button onClick={handleBuy} className="w-full bg-green-600 hover:bg-green-500 text-white font-semibold py-2 rounded-lg transition-colors">
                Execute Buy
              </button>
            </>
          )}
          {buyMsg && <p className="text-sm mt-2 text-teal-400">{buyMsg}</p>}
        </div>

        {/* Sell */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-lg font-semibold mb-3">Sell Stock</h2>
          {portfolio?.holdings.length ? (
            <>
              <select value={sellTicker} onChange={(e) => setSellTicker(e.target.value)}
                className="w-full bg-gray-800 text-white rounded px-3 py-2 mb-3 outline-none text-sm">
                {portfolio.holdings.map((h) => <option key={h.ticker} value={h.ticker}>{h.ticker}</option>)}
              </select>

              {sellPrice !== null && sellHolding && (
                <>
                  <p className="text-sm text-teal-400 mb-1">
                    Price: ${sellPrice.toFixed(2)} | Own: {sellHolding.shares} shares | Avg: ${sellHolding.avg_price.toFixed(2)}
                  </p>
                  <p className={`text-sm mb-2 ${sellPrice - sellHolding.avg_price >= 0 ? "text-green-400" : "text-red-400"}`}>
                    P&L/share: ${(sellPrice - sellHolding.avg_price).toFixed(2)} ({((sellPrice - sellHolding.avg_price) / sellHolding.avg_price * 100).toFixed(1)}%)
                  </p>
                  <input type="number" min={1} max={sellHolding.shares} value={sellShares}
                    onChange={(e) => setSellShares(Math.max(1, Number(e.target.value)))}
                    className="w-full bg-gray-800 text-white rounded px-3 py-2 mb-2 outline-none text-sm" />
                  <p className="text-sm text-gray-400 mb-3">Revenue: ${(sellShares * sellPrice).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                  <button onClick={handleSell} className="w-full bg-red-600 hover:bg-red-500 text-white font-semibold py-2 rounded-lg transition-colors">
                    Execute Sell
                  </button>
                </>
              )}
              {sellMsg && <p className="text-sm mt-2 text-teal-400">{sellMsg}</p>}
            </>
          ) : (
            <p className="text-gray-500 text-sm">No holdings to sell. Buy some stocks first!</p>
          )}
        </div>
      </div>

      {/* AI Suggestions */}
      {suggestions.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">AI-Suggested Trades</h2>
          <div className="grid grid-cols-5 gap-3">
            {suggestions.map((s) => (
              <div key={s.ticker} className="text-center">
                <p className="text-sm font-medium mb-1">{s.ticker} ${s.price.toFixed(2)}</p>
                <SignalBadge analysis={s.analysis} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Transactions */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 mb-6">
        <h2 className="text-lg font-semibold mb-3">Recent Transactions</h2>
        {transactions.length ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-left border-b border-gray-800">
                <th className="pb-2">Date</th><th className="pb-2">Type</th><th className="pb-2">Ticker</th>
                <th className="pb-2 text-right">Shares</th><th className="pb-2 text-right">Price</th>
                <th className="pb-2 text-right">Total</th><th className="pb-2 text-right">Cash After</th>
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
                  <td className="text-right">${t.cash_after.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-gray-500 text-sm">No transactions yet. Start trading!</p>
        )}
      </div>

      <button onClick={handleReset} className="bg-gray-800 hover:bg-gray-700 text-gray-400 text-sm px-4 py-2 rounded-lg transition-colors">
        Reset Portfolio (Start Over with $100K)
      </button>
    </div>
  );
}
