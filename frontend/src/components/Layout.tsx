import { useState, useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { getWatchlist, addToWatchlist, removeFromWatchlist } from "../api/client";
import { useAuth } from "./AuthProvider";

const navItems = [
  { to: "/market", label: "Market Analysis" },
  { to: "/trade", label: "Paper Trading" },
  { to: "/portfolio", label: "Portfolio" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [period, setPeriod] = useState("6mo");

  useEffect(() => {
    getWatchlist().then(setWatchlist);
  }, []);

  const handleAdd = async () => {
    const t = input.toUpperCase().trim();
    if (!t || watchlist.includes(t)) return;
    await addToWatchlist(t);
    setWatchlist((prev) => [...prev, t].sort());
    setInput("");
  };

  const handleRemove = async (t: string) => {
    await removeFromWatchlist(t);
    setWatchlist((prev) => prev.filter((x) => x !== t));
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-lg font-bold text-teal-400">Stock Trader</h1>
        </div>

        {/* Nav */}
        <nav className="p-3 space-y-1">
          {navItems.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? "bg-teal-600 text-white" : "text-gray-400 hover:bg-gray-800 hover:text-white"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-gray-800 p-3">
          <h2 className="text-xs font-semibold text-gray-500 uppercase mb-2">Watchlist</h2>
          <div className="flex gap-1 mb-3">
            <input
              className="flex-1 bg-gray-800 text-white text-sm rounded px-2 py-1.5 placeholder-gray-500 outline-none focus:ring-1 focus:ring-teal-500"
              placeholder="e.g. AMZN"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            />
            <button
              onClick={handleAdd}
              className="bg-teal-600 text-white text-sm px-2 py-1.5 rounded hover:bg-teal-500 transition-colors"
            >
              +
            </button>
          </div>
          <ul className="space-y-1 max-h-60 overflow-y-auto">
            {watchlist.map((t) => (
              <li key={t} className="flex items-center justify-between text-sm text-gray-300 px-2 py-1 rounded hover:bg-gray-800">
                <span>{t}</span>
                <button onClick={() => handleRemove(t)} className="text-gray-600 hover:text-red-400 text-xs">
                  X
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="border-t border-gray-800 p-3 mt-auto">
          <label className="text-xs text-gray-500 block mb-1">Chart Period</label>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="w-full bg-gray-800 text-white text-sm rounded px-2 py-1.5 outline-none"
          >
            {["1mo", "3mo", "6mo", "1y", "2y", "5y"].map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>

        {/* User */}
        {user && (
          <div className="border-t border-gray-800 p-3">
            <div className="flex items-center gap-2 mb-2">
              <img src={user.picture} alt="" className="w-8 h-8 rounded-full" referrerPolicy="no-referrer" />
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{user.name}</div>
                <div className="text-xs text-gray-500 truncate">{user.email}</div>
              </div>
            </div>
            <button
              onClick={logout}
              className="w-full text-xs text-gray-500 hover:text-red-400 transition-colors py-1"
            >
              Sign out
            </button>
          </div>
        )}
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto bg-gray-950 p-6">
        <Outlet context={{ watchlist, period }} />
      </main>
    </div>
  );
}
