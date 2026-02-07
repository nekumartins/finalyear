/**
 * Layout — App shell with navigation bar.
 */
import { Outlet, NavLink } from "react-router-dom";
import React from "react";

const navItems = [
  { to: "/", label: "🏠 Home" },
  { to: "/debate", label: "🎙️ Debate" },
  { to: "/history", label: "📋 History" },
];

export function Layout() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <nav style={styles.nav}>
        <div style={styles.brand}>⚡ Debate Coach</div>
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
  links: {
    display: "flex",
    gap: "24px",
  },
  link: {
    fontSize: "0.95rem",
    fontWeight: 500,
    transition: "color 0.2s",
  },
  main: {
    flex: 1,
    padding: "32px",
    maxWidth: "1000px",
    margin: "0 auto",
    width: "100%",
  },
};
