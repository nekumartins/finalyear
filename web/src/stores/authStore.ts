/**
 * Auth Store (Zustand)
 *
 * Manages authentication state:
 * - Token persistence in localStorage
 * - Login / Register / Logout actions
 * - Auto-check on app init via checkAuth()
 */
import { create } from "zustand";

const API = "/api/auth";

export interface AuthUser {
    id: string;
    email: string;
    name: string;
    auth_provider: string;
}

interface AuthState {
    user: AuthUser | null;
    token: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    error: string | null;

    login: (email: string, password: string) => Promise<boolean>;
    register: (email: string, password: string, name: string) => Promise<boolean>;
    logout: () => void;
    checkAuth: () => Promise<void>;
    clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
    user: null,
    token: localStorage.getItem("token"),
    isAuthenticated: false,
    isLoading: true,
    error: null,

    login: async (email, password) => {
        set({ error: null, isLoading: true });
        try {
            const res = await fetch(`${API}/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });
            const data = await res.json();
            if (!res.ok) {
                set({ error: data.detail || "Login failed", isLoading: false });
                return false;
            }
            localStorage.setItem("token", data.access_token);
            set({
                token: data.access_token,
                user: data.user,
                isAuthenticated: true,
                isLoading: false,
            });
            return true;
        } catch {
            set({ error: "Network error", isLoading: false });
            return false;
        }
    },

    register: async (email, password, name) => {
        set({ error: null, isLoading: true });
        try {
            const res = await fetch(`${API}/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password, name }),
            });
            const data = await res.json();
            if (!res.ok) {
                set({ error: data.detail || "Registration failed", isLoading: false });
                return false;
            }
            localStorage.setItem("token", data.access_token);
            set({
                token: data.access_token,
                user: data.user,
                isAuthenticated: true,
                isLoading: false,
            });
            return true;
        } catch {
            set({ error: "Network error", isLoading: false });
            return false;
        }
    },

    logout: () => {
        localStorage.removeItem("token");
        set({ user: null, token: null, isAuthenticated: false, error: null });
    },

    checkAuth: async () => {
        const token = localStorage.getItem("token");
        if (!token) {
            set({ isLoading: false, isAuthenticated: false });
            return;
        }
        try {
            const res = await fetch(`${API}/me`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const user = await res.json();
                set({ user, token, isAuthenticated: true, isLoading: false });
            } else {
                localStorage.removeItem("token");
                set({ user: null, token: null, isAuthenticated: false, isLoading: false });
            }
        } catch {
            set({ isLoading: false });
        }
    },

    clearError: () => set({ error: null }),
}));
