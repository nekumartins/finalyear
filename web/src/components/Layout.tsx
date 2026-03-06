/**
 * Layout — App shell with glassmorphism navigation bar + user menu.
 */
import { Outlet, NavLink, useNavigate, useLocation } from "react-router-dom";
import React from "react";
import { useAuthStore } from "../stores/authStore";
import { useAppStore, type Theme } from "../stores/appStore";
import { ConstellationBg } from "./ConstellationBg";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/new-debate", label: "New Debate" },
  { to: "/history", label: "History" },
  { to: "/profile", label: "Profile" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const { user, logout } = useAuthStore();
  const profileName = useAppStore((s) => s.profileName);
  const theme = useAppStore((s) => s.theme);
  const setTheme = useAppStore((s) => s.setTheme);
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = React.useState(false);

  const cycleTheme = () => {
    const order: Theme[] = ["dark", "light", "system"];
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setTheme(next);
  };
  const themeIcon = theme === "dark" ? "🌙" : theme === "light" ? "☀️" : "🖥️";

  // Close mobile menu on route change
  React.useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate("/auth");
  };

  const name = profileName || user?.name || "User";
  const initials = name
    ? name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .slice(0, 2)
      .toUpperCase()
    : "?";

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <ConstellationBg />
      
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

        {/* Desktop: nav links and user */}
        <div style={styles.right} className="nav-desktop">
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
              <button
                onClick={cycleTheme}
                title={`Theme: ${theme}`}
                style={styles.themeBtn}
              >
                {themeIcon}
              </button>
              <div style={styles.avatar} title={name}>
                {initials}
              </div>
              <span style={styles.userName}>{name}</span>
              <button onClick={handleLogout} style={styles.logoutBtn}>
                Sign out
              </button>
            </div>
          )}
        </div>

        {/* Mobile: avatar + hamburger */}
        <div className="nav-mobile-actions">
          {user && <div style={styles.avatar} title={name}>{initials}</div>}
          <button
            className="hamburger"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="Toggle menu"
            aria-expanded={menuOpen}
          >
            {menuOpen ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            )}
          </button>
        </div>
      </nav>

      {/* Mobile menu drawer */}
      {menuOpen && (
        <div className="mobile-menu">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className="mobile-menu-link"
              style={({ isActive }) => ({
                color: isActive ? "var(--accent)" : "var(--text-primary)",
                background: isActive ? "rgba(124,111,239,0.1)" : "transparent",
              })}
            >
              {item.label}
            </NavLink>
          ))}
          <div className="mobile-menu-divider" />
          <button
            className="mobile-menu-link"
            onClick={cycleTheme}
            style={{ border: "none", cursor: "pointer", fontSize: "0.95rem", textAlign: "left" }}
          >
            {themeIcon} Theme: {theme.charAt(0).toUpperCase() + theme.slice(1)}
          </button>
          <button className="mobile-menu-signout" onClick={handleLogout}>Sign out</button>
        </div>
      )}

      <main style={styles.main} className="page-main">
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
    padding: "0 24px",
    height: "60px",
    borderBottom: "1px solid var(--border)",
    background: "var(--bg-nav, rgba(7,7,15,0.8))",
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
    flexShrink: 0,
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
    gap: "16px",
  },
  links: {
    display: "flex",
    gap: "4px",
  },
  link: {
    fontSize: "0.82rem",
    fontWeight: 500,
    padding: "6px 11px",
    borderRadius: "20px",
    transition: "all 0.2s",
    textDecoration: "none",
    whiteSpace: "nowrap",
  },
  userMenu: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    paddingLeft: "14px",
    borderLeft: "1px solid var(--border)",
  },
  userName: {
    color: "var(--text-secondary)",
    fontSize: "0.8rem",
    fontWeight: 600,
    maxWidth: "110px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
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
    padding: "6px 10px",
    fontSize: "0.75rem",
    fontWeight: 500,
    borderRadius: "20px",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  themeBtn: {
    background: "var(--bg-glass)",
    border: "1px solid var(--border)",
    borderRadius: "50%",
    width: 32,
    height: 32,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.9rem",
    cursor: "pointer",
    transition: "all 0.2s",
    padding: 0,
  },
  main: {
    flex: 1,
    padding: "32px 32px",
    maxWidth: "1100px",
    margin: "0 auto",
    width: "100%",
  },
};
