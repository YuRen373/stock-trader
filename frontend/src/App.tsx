import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./components/AuthProvider";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import MarketAnalysis from "./pages/MarketAnalysis";
import PaperTrading from "./pages/PaperTrading";
import Portfolio from "./pages/Portfolio";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<Navigate to="/market" replace />} />
        <Route path="/market" element={<MarketAnalysis />} />
        <Route path="/trade" element={<PaperTrading />} />
        <Route path="/portfolio" element={<Portfolio />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
