import Plot from "react-plotly.js";
import type { ChartPoint } from "../types";

export default function StockChart({ data, ticker }: { data: ChartPoint[]; ticker: string }) {
  const dates = data.map((d) => d.date);
  const open = data.map((d) => d.Open);
  const high = data.map((d) => d.High);
  const low = data.map((d) => d.Low);
  const close = data.map((d) => d.Close);
  const volume = data.map((d) => d.Volume);
  const sma20 = data.map((d) => d.SMA_20);
  const sma50 = data.map((d) => d.SMA_50);
  const bbUpper = data.map((d) => d.BB_Upper);
  const bbLower = data.map((d) => d.BB_Lower);
  const rsi = data.map((d) => d.RSI);
  const macd = data.map((d) => d.MACD);
  const macdSignal = data.map((d) => d.MACD_Signal);
  const macdHist = data.map((d) => d.MACD_Hist);

  const volColors = data.map((d) => (d.Close >= d.Open ? "#26a69a" : "#ef5350"));
  const histColors = data.map((d) => ((d.MACD_Hist ?? 0) >= 0 ? "#26a69a" : "#ef5350"));

  return (
    <Plot
      data={[
        { type: "candlestick", x: dates, open, high, low, close, name: "Price", increasing: { line: { color: "#26a69a" } }, decreasing: { line: { color: "#ef5350" } }, xaxis: "x", yaxis: "y" },
        { type: "scatter", x: dates, y: bbUpper, name: "BB Upper", line: { color: "rgba(173,216,230,0.4)", width: 1 }, xaxis: "x", yaxis: "y" },
        { type: "scatter", x: dates, y: bbLower, name: "BB Lower", line: { color: "rgba(173,216,230,0.4)", width: 1 }, fill: "tonexty", fillcolor: "rgba(173,216,230,0.1)", xaxis: "x", yaxis: "y" },
        { type: "scatter", x: dates, y: sma20, name: "SMA 20", line: { color: "#ff9800", width: 1.5 }, xaxis: "x", yaxis: "y" },
        { type: "scatter", x: dates, y: sma50, name: "SMA 50", line: { color: "#2196f3", width: 1.5 }, xaxis: "x", yaxis: "y" },
        { type: "scatter", x: dates, y: rsi, name: "RSI", line: { color: "#ab47bc", width: 1.5 }, xaxis: "x", yaxis: "y2" },
        { type: "bar", x: dates, y: macdHist, name: "MACD Hist", marker: { color: histColors }, xaxis: "x", yaxis: "y3" },
        { type: "scatter", x: dates, y: macd, name: "MACD", line: { color: "#2196f3", width: 1.5 }, xaxis: "x", yaxis: "y3" },
        { type: "scatter", x: dates, y: macdSignal, name: "Signal", line: { color: "#ff9800", width: 1.5 }, xaxis: "x", yaxis: "y3" },
        { type: "bar", x: dates, y: volume, name: "Volume", marker: { color: volColors }, xaxis: "x", yaxis: "y4" },
      ]}
      layout={{
        height: 750,
        // @ts-expect-error plotly template string
        template: "plotly_dark",
        showlegend: false,
        margin: { t: 30, b: 30, l: 50, r: 20 },
        font: { size: 11 },
        xaxis: { rangeslider: { visible: false }, domain: [0, 1] },
        yaxis: { title: { text: "Price ($)" }, domain: [0.52, 1] },
        yaxis2: { title: { text: "RSI" }, domain: [0.36, 0.50], range: [0, 100] },
        yaxis3: { title: { text: "MACD" }, domain: [0.18, 0.34] },
        yaxis4: { title: { text: "Vol" }, domain: [0, 0.16] },
        annotations: [
          { xref: "paper", yref: "paper", x: 0, y: 1.02, text: `${ticker} Price`, showarrow: false, font: { size: 13 } },
        ],
        shapes: [
          { type: "line", xref: "paper", yref: "y2", x0: 0, x1: 1, y0: 70, y1: 70, line: { color: "red", dash: "dash", width: 1 } },
          { type: "line", xref: "paper", yref: "y2", x0: 0, x1: 1, y0: 30, y1: 30, line: { color: "green", dash: "dash", width: 1 } },
        ],
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
      }}
      useResizeHandler
      style={{ width: "100%", height: "750px" }}
      config={{ displayModeBar: false }}
    />
  );
}
