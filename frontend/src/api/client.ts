import axios from "axios";
import type { StockData, Portfolio, Transaction, User } from "../types";

const api = axios.create({ baseURL: "/api" });

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401, clear token and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  },
);

// --- Auth ---
export async function googleLogin(code: string, redirectUri: string): Promise<{ token: string; user: User }> {
  const { data } = await api.post("/auth/google", { code, redirect_uri: redirectUri });
  return data;
}

export async function getMe(): Promise<User> {
  const { data } = await api.get("/auth/me");
  return data;
}

// --- Watchlist ---
export async function getWatchlist(): Promise<string[]> {
  const { data } = await api.get<{ tickers: string[] }>("/watchlist");
  return data.tickers;
}

export async function addToWatchlist(ticker: string): Promise<void> {
  await api.post(`/watchlist/${ticker}`);
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  await api.delete(`/watchlist/${ticker}`);
}

// --- Stock ---
export async function getStock(ticker: string, period = "6mo"): Promise<StockData> {
  const { data } = await api.get<StockData>(`/stock/${ticker}`, { params: { period } });
  return data;
}

export async function getPrice(ticker: string): Promise<number> {
  const { data } = await api.get<{ price: number }>(`/stock/${ticker}/price`);
  return data.price;
}

// --- Portfolio ---
export async function getPortfolio(): Promise<Portfolio> {
  const { data } = await api.get<Portfolio>("/portfolio");
  return data;
}

export async function executeBuy(ticker: string, shares: number) {
  const { data } = await api.post("/trade/buy", { ticker, shares });
  return data;
}

export async function executeSell(ticker: string, shares: number) {
  const { data } = await api.post("/trade/sell", { ticker, shares });
  return data;
}

export async function getTransactions(limit = 200): Promise<Transaction[]> {
  const { data } = await api.get<{ transactions: Transaction[] }>("/transactions", { params: { limit } });
  return data.transactions;
}

export async function resetPortfolio() {
  const { data } = await api.post("/portfolio/reset");
  return data;
}
