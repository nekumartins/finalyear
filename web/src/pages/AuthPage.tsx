/**
 * AuthPage — Login / Register with tab toggle.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

type AuthTab = "login" | "register";

export function AuthPage() {
    const navigate = useNavigate();
    const { login, register, error, isLoading, clearError } = useAuthStore();

    const [tab, setTab] = useState<AuthTab>("login");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [name, setName] = useState("");

    const switchTab = (t: AuthTab) => {
        setTab(t);
        clearError();
        setEmail("");
        setPassword("");
        setName("");
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        let ok = false;
        if (tab === "login") {
            ok = await login(email, password);
        } else {
            ok = await register(email, password, name);
        }
        if (ok) navigate("/");
    };

    return (
        <div style={styles.page}>
            <div style={styles.container}>
                {/* Header */}
                <div style={styles.header}>
                    <div style={styles.logo}>⚡</div>
                    <h1 style={styles.title}>Debate Coach</h1>
                    <p style={styles.subtitle}>Sharpen your arguments with AI</p>
                </div>

                {/* Tabs */}
                <div style={styles.tabs}>
                    <button
                        onClick={() => switchTab("login")}
                        style={{
                            ...styles.tab,
                            ...(tab === "login" ? styles.tabActive : {}),
                        }}
                    >
                        Sign In
                    </button>
                    <button
                        onClick={() => switchTab("register")}
                        style={{
                            ...styles.tab,
                            ...(tab === "register" ? styles.tabActive : {}),
                        }}
                    >
                        Create Account
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} style={styles.form}>
                    {tab === "register" && (
                        <div style={styles.field}>
                            <label style={styles.label}>Name</label>
                            <input
                                id="auth-name"
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="Your name"
                                required
                                style={styles.input}
                            />
                        </div>
                    )}

                    <div style={styles.field}>
                        <label style={styles.label}>Email</label>
                        <input
                            id="auth-email"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="you@example.com"
                            required
                            autoComplete="email"
                            style={styles.input}
                        />
                    </div>

                    <div style={styles.field}>
                        <label style={styles.label}>Password</label>
                        <input
                            id="auth-password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            required
                            minLength={6}
                            autoComplete={tab === "login" ? "current-password" : "new-password"}
                            style={styles.input}
                        />
                    </div>

                    {error && <div style={styles.error}>{error}</div>}

                    <button
                        type="submit"
                        className="btn-primary"
                        disabled={isLoading}
                        style={styles.submit}
                    >
                        {isLoading
                            ? "Please wait..."
                            : tab === "login"
                                ? "Sign In"
                                : "Create Account"}
                    </button>
                </form>

                <p style={styles.footer}>
                    {tab === "login" ? "Don't have an account? " : "Already have an account? "}
                    <button
                        onClick={() => switchTab(tab === "login" ? "register" : "login")}
                        style={styles.footerLink}
                    >
                        {tab === "login" ? "Create one" : "Sign in"}
                    </button>
                </p>
            </div>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    page: {
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        background: "var(--bg-primary)",
    },
    container: {
        width: "100%",
        maxWidth: "420px",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
    },
    header: {
        textAlign: "center",
        marginBottom: "8px",
    },
    logo: {
        fontSize: "3rem",
        marginBottom: "8px",
    },
    title: {
        fontSize: "1.75rem",
        fontWeight: 700,
        color: "var(--text-primary)",
    },
    subtitle: {
        color: "var(--text-secondary)",
        fontSize: "0.95rem",
        marginTop: "4px",
    },
    tabs: {
        display: "flex",
        background: "var(--bg-secondary)",
        borderRadius: "var(--radius)",
        padding: "4px",
        border: "1px solid var(--border)",
    },
    tab: {
        flex: 1,
        padding: "10px 16px",
        fontSize: "0.9rem",
        fontWeight: 600,
        background: "transparent",
        color: "var(--text-secondary)",
        borderRadius: "calc(var(--radius) - 4px)",
        transition: "all 0.2s",
        border: "none",
        cursor: "pointer",
    },
    tabActive: {
        background: "var(--accent)",
        color: "white",
    },
    form: {
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "24px",
    },
    field: {
        display: "flex",
        flexDirection: "column",
        gap: "6px",
    },
    label: {
        fontSize: "0.8rem",
        color: "var(--text-secondary)",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        fontWeight: 600,
    },
    input: {
        background: "var(--bg-secondary)",
        border: "1px solid var(--border)",
        borderRadius: "calc(var(--radius) - 4px)",
        padding: "12px 14px",
        fontSize: "0.95rem",
        color: "var(--text-primary)",
        outline: "none",
        width: "100%",
        transition: "border-color 0.2s",
        fontFamily: "var(--font)",
    },
    error: {
        background: "rgba(248, 113, 113, 0.1)",
        border: "1px solid var(--danger)",
        borderRadius: "calc(var(--radius) - 4px)",
        padding: "10px 14px",
        fontSize: "0.85rem",
        color: "var(--danger)",
    },
    submit: {
        width: "100%",
        padding: "14px",
        fontSize: "1rem",
        marginTop: "4px",
    },
    footer: {
        textAlign: "center",
        fontSize: "0.85rem",
        color: "var(--text-secondary)",
    },
    footerLink: {
        background: "none",
        border: "none",
        color: "var(--accent)",
        fontSize: "0.85rem",
        fontWeight: 600,
        cursor: "pointer",
        padding: 0,
    },
};
