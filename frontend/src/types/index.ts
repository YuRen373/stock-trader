export interface User {
  id: string;
  email: string;
  name: string;
  picture: string;
}

export interface Analysis {
  signal: "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL";
  score: number;
  details: string[];
}

export interface ChartPoint {
  date: string;
  Open: number;
  High: number;
  Low: number;
  Close: number;
  Volume: number;
  SMA_20: number | null;
  SMA_50: number | null;
  BB_Upper: number | null;
  BB_Lower: number | null;
  RSI: number | null;
  MACD: number | null;
  MACD_Signal: number | null;
  MACD_Hist: number | null;
}

export interface StockData {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  price: number;
  change: number;
  change_pct: number;
  high: number;
  low: number;
  volume: number;
  market_cap: number | null;
  pe_ratio: number | null;
  eps: number | null;
  dividend_yield: number | null;
  week52_low: number | null;
  week52_high: number | null;
  analysis: Analysis;
  chart: ChartPoint[];
}

export interface Holding {
  ticker: string;
  shares: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  cost_basis: number;
  pnl: number;
  pnl_pct: number;
  allocation_pct: number;
}

export interface Portfolio {
  cash: number;
  portfolio_value: number;
  initial_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  holdings: Holding[];
}

export interface Transaction {
  date: string;
  type: "BUY" | "SELL";
  ticker: string;
  shares: number;
  price: number;
  total: number;
  cash_after: number;
  portfolio_value: number;
}
