"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, session, type User } from "./api";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  isAdmin: boolean;
  /** admin or security staff - the viewer role is read-only */
  canWrite: boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // restore the session, then confirm the token is still valid on the server
    const stored = session.user();
    if (stored && session.token()) {
      setUser(stored);
      api.get<User>("/api/auth/me").then(setUser).catch(() => setUser(null));
    }
    setReady(true);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.post<{ access_token: string; user: User }>("/api/auth/login", { username, password });
    session.save(res.access_token, res.user);
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } catch {
      /* token may already be expired */
    }
    session.clear();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, ready, login, logout, isAdmin: user?.role === "admin", canWrite: user?.role === "admin" || user?.role === "security" }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
