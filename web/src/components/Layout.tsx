/**
 * Layout — App shell with navigation bar + user menu.
 */
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import React from "react";
import { useAuthStore } from "../stores/authStore";

const navItems = [
  { to: "/", label: "🏠 Home" },
  { to: "/debate", label: "🎙️ Debate" },
  { to: "/history", label: "📋 History" },
];

export function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/auth");
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <nav style={styles.nav}>
        <div style={styles.brand}>⚡ Debate Coach</div>
        <div style={styles.right}>
          <div style={styles.links}>
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                style={({ isActive }) => ({
                  ...styles.link,
                  color: isActive ? "var(--accent)" : "var(--text-secondary)",
                })}
              >
                {item.label}
              </NavLink>
            ))}
          </div>
          {user && (
            <div style={styles.userMenu}>
              <span style={styles.userName}>{user.name}</span>
              <button onClick={handleLogout} style={styles.logoutBtn}>
                Logout
              </button>
            </div>
          )}
        </div>
      </nav>
      <main style={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  nav: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 32px",
    borderBottom: "1px solid var(--border)",
    background: "var(--bg-secondary)",
  },
  brand: {
    fontSize: "1.25rem",
    fontWeight: 700,
  },
  right: {
    display: "flex",
    alignItems: "center",
    gap: "24px",
  },
  links: {
    display: "flex",
    gap: "24px",
  },
  link: {
    fontSize: "0.95rem",
    fontWeight: 500,
    transition: "color 0.2s",
  },
  userMenu: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    paddingLeft: "24px",
    borderLeft: "1px solid var(--border)",
  },
  userName: {
    fontSize: "0.85rem",
    color: "var(--text-secondary)",
    fontWeight: 500,
  },
  logoutBtn: {
    background: "transparent",
    border: "1px solid var(--border)",
    color: "var(--text-secondary)",
    padding: "6px 14px",
    fontSize: "0.8rem",
    fontWeight: 500,
    borderRadius: "8px",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  main: {
    flex: 1,
    padding: "32px",
    maxWidth: "1000px",
    margin: "0 auto",
    width: "100%",
  },
};
