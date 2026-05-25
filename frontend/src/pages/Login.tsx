import { useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../components/AuthProvider";
import { googleLogin } from "../api/client";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

function getRedirectUri() {
  return `${window.location.origin}/login`;
}

function getGoogleAuthUrl() {
  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: getRedirectUri(),
    response_type: "code",
    scope: "openid email profile",
    access_type: "offline",
    prompt: "consent",
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
}

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const code = searchParams.get("code");

  const handleCallback = useCallback(async (authCode: string) => {
    try {
      const { token, user: u } = await googleLogin(authCode, getRedirectUri());
      login(token, u);
      navigate("/market", { replace: true });
    } catch {
      // Failed - show login button again
    }
  }, [login, navigate]);

  useEffect(() => {
    if (user) {
      navigate("/market", { replace: true });
      return;
    }
    if (code) {
      handleCallback(code);
    }
  }, [user, code, navigate, handleCallback]);

  if (code) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <p className="text-gray-400">Signing in...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-10 text-center max-w-md w-full">
        <h1 className="text-3xl font-bold text-teal-400 mb-2">Stock Trader</h1>
        <p className="text-gray-400 mb-8">Paper trading simulator with real-time analysis</p>

        <a
          href={getGoogleAuthUrl()}
          className="inline-flex items-center gap-3 bg-white text-gray-800 font-semibold px-6 py-3 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Sign in with Google
        </a>

        <p className="text-xs text-gray-600 mt-6">
          Get $100,000 virtual cash to practice trading with real market data.
        </p>
      </div>
    </div>
  );
}
