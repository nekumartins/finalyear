/**
 * ProtectedRoute — Redirects unauthenticated users to /auth.
 * Shows a loading spinner while checkAuth() resolves.
 */
import React, { useEffect } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

export function ProtectedRoute() {
    const { isAuthenticated, isLoading, checkAuth } = useAuthStore();

    useEffect(() => {
        checkAuth();
    }, []);

    if (isLoading) {
        return (
            <div style={styles.loader}>
                <div style={styles.spinner} />
                <p style={{ color: "var(--text-secondary)", marginTop: "16px" }}>Loading...</p>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/auth" replace />;
    }

    return <Outlet />;
}

const styles: Record<string, React.CSSProperties> = {
    loader: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
    },
    spinner: {
        width: "40px",
        height: "40px",
        border: "3px solid var(--border)",
        borderTopColor: "var(--accent)",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
    },
};
