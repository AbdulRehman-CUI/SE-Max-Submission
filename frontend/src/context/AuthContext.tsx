import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { auth } from "../api";
import { session } from "../lib/api";
import type { User } from "../types/api";
const Context = createContext<{
  user: User | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => void;
} | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    const clear = () => {
      setUser(null);
      setLoading(false);
    };
    window.addEventListener("spendsense:unauthorized", clear);
    if (session.get())
      auth
        .me()
        .then((value) => {
          if (active) setUser(value);
        })
        .catch(() => {
          if (active) session.clear();
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    else setLoading(false);
    return () => {
      active = false;
      window.removeEventListener("spendsense:unauthorized", clear);
    };
  }, []);
  async function login(identifier: string, password: string) {
    const result = await auth.login(identifier, password);
    session.set(result.access_token);
    try {
      setUser(await auth.me());
    } catch (error) {
      session.clear();
      throw error;
    }
  }
  function logout() {
    session.clear();
    setUser(null);
  }
  return (
    <Context.Provider value={{ user, loading, login, logout }}>
      {children}
    </Context.Provider>
  );
}
export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("AuthProvider missing");
  return value;
}
