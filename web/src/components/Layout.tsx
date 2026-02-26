/**
 * Layout — App shell with glassmorphism navigation bar + user menu.
 */
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import React from "react";
import { useAuthStore } from "../stores/authStore";

const navItems = [
  { to: "/", label: "Home" },
  { to: "/debate", label: "Debate" },
  { to: "/history", label: "History" },
];

export function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/auth");
  };

  const initials = user?.name
    ? user.name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .slice(0, 2)
      .toUpperCase()
    : "?";

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <nav style={styles.nav}>
        {/* Brand */}
        <div style={styles.brand}>
          <div style={styles.logoMark}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span style={styles.brandText}>Debate Coach</span>
        </div>

        {/* Nav links and user */}
        <div style={styles.right}>
          <div style={styles.links}>
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                style={({ isActive }) => ({
                  ...styles.link,
                  color: isActive ? "var(--accent)" : "var(--text-secondary)",
                  background: isActive ? "rgba(124,111,239,0.12)" : "transparent",
                  border: isActive ? "1px solid rgba(124,111,239,0.25)" : "1px solid transparent",
                })}
              >
                {item.label}
              </NavLink>
            ))}
          </div>

          {user && (
            <div style={styles.userMenu}>
              <div style={styles.avatar} title={user.name}>
                {initials}
              </div>
              <button onClick={handleLogout} style={styles.logoutBtn}>
                Sign out
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
    padding: "0 32px",
    height: "64px",
    borderBottom: "1px solid var(--border)",
    background: "rgba(7,7,15,0.8)",
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
    position: "sticky",
    top: 0,
    zIndex: 100,
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    textDecoration: "none",
  },
  logoMark: {
    width: 34,
    height: 34,
    borderRadius: "10px",
    background: "var(--gradient)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 0 18px var(--accent-glow)",
  },
  brandText: {
    fontSize: "1rem",
    fontWeight: 700,
    color: "var(--text-primary)",
    letterSpacing: "-0.01em",
  },
  right: {
    display: "flex",
    alignItems: "center",
    gap: "24px",
  },
  links: {
    display: "flex",
    gap: "4px",
  },
  link: {
    fontSize: "0.875rem",
    fontWeight: 500,
    padding: "6px 14px",
    borderRadius: "20px",
    transition: "all 0.2s",
    textDecoration: "none",
  },
  userMenu: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    paddingLeft: "20px",
    borderLeft: "1px solid var(--border)",
  },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: "50%",
    background: "var(--gradient)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.8rem",
    fontWeight: 700,
    color: "white",
    cursor: "default",
    boxShadow: "0 0 10px var(--accent-glow)",
  },
  logoutBtn: {
    background: "transparent",
    border: "1px solid var(--border)",
    color: "var(--text-secondary)",
    padding: "6px 14px",
    fontSize: "0.8rem",
    fontWeight: 500,
    borderRadius: "20px",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  main: {
    flex: 1,
    padding: "40px 32px",
    maxWidth: "1100px",
    margin: "0 auto",
    width: "100%",
  },
};
