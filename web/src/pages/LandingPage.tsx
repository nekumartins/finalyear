/**
 * LandingPage — Public marketing page for unauthenticated visitors.
 * Constellation-style animated background, hero, features, social proof, CTA.
 */
import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { useAppStore } from "../stores/appStore";
import { ConstellationBg } from "../components/ConstellationBg";

/* ── Feature Card ── */
function FeatureCard({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <div style={styles.featureCard} className="glass">
      <span style={styles.featureIcon}>{icon}</span>
      <h3 style={styles.featureTitle}>{title}</h3>
      <p style={styles.featureDesc}>{desc}</p>
    </div>
  );
}

/* ── Stat Pill ── */
function StatPill({ value, label }: { value: string; label: string }) {
  return (
    <div style={styles.statPill}>
      <span style={styles.statValue}>{value}</span>
      <span style={styles.statLabel}>{label}</span>
    </div>
  );
}

/* ── Main Page ── */
export function LandingPage() {
  const navigate = useNavigate();
  const { isAuthenticated, checkAuth } = useAuthStore();
  const { theme, setTheme } = useAppStore();

  useEffect(() => {
    checkAuth();
  }, []);

  // If already logged in, skip to dashboard
  useEffect(() => {
    if (isAuthenticated) navigate("/dashboard", { replace: true });
  }, [isAuthenticated, navigate]);

  return (
    <div style={styles.page}>
      <ConstellationBg />

      {/* Nav */}
      <nav style={styles.nav}>
        <div style={styles.brand}>
          <div style={styles.logoMark}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span style={styles.brandText}>Debate Coach</span>
        </div>
        <div style={styles.navActions}>
          <button
            style={styles.themeToggle}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title="Toggle theme"
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
          <button style={styles.navLink} onClick={() => navigate("/auth")}>Sign in</button>
          <button className="btn-primary" style={styles.navCta} onClick={() => navigate("/auth")}>Get Started</button>
        </div>
      </nav>

      {/* Hero */}
      <section style={styles.hero}>
        <div style={styles.heroBadge}>
          <span style={styles.heroPulse} />
          AI-Powered · Real-time Feedback
        </div>
        <h1 style={styles.heroTitle}>
          Become a Sharper<br />
          <span className="gradient-text">Debater, Faster.</span>
        </h1>
        <p style={styles.heroSub}>
          Practice against an adaptive AI opponent, get instant coaching on argument
          quality, pacing, and confidence — then watch yourself improve session after session.
        </p>
        <div style={styles.heroBtns}>
          <button className="btn-primary" style={styles.heroCtaPrimary} onClick={() => navigate("/auth")}>
            Start Practicing — Free
          </button>
          <button className="btn-secondary" style={styles.heroCtaSecondary} onClick={() => {
            document.getElementById("features")?.scrollIntoView({ behavior: "smooth" });
          }}>
            See How It Works ↓
          </button>
        </div>

        {/* Stats row */}
        <div style={styles.statsRow}>
          <StatPill value="Real-time" label="AI Voice Debates" />
          <StatPill value="Instant" label="Coaching Reports" />
          <StatPill value="3 Goals" label="Confidence · Pacing · Structure" />
        </div>
      </section>

      {/* Features */}
      <section id="features" style={styles.featuresSection}>
        <h2 style={styles.sectionTitle}>Everything you need to level up</h2>
        <p style={styles.sectionSub}>Practice debating anytime — no partner needed, no judgment, just growth.</p>
        <div style={styles.featuresGrid}>
          <FeatureCard
            icon="🎙️"
            title="Voice-to-Voice AI"
            desc="Speak naturally and your AI opponent responds in real-time with edge or cloud processing."
          />
          <FeatureCard
            icon="📊"
            title="Instant Metrics"
            desc="WPM, filler words, talk ratio, turn count — all tracked live and reviewed post-session."
          />
          <FeatureCard
            icon="🧠"
            title="Coaching Reports"
            desc="Get strengths, improvements, logical fallacy detection, and actionable tips after every round."
          />
          <FeatureCard
            icon="🎯"
            title="Adaptive Goals"
            desc="Focus on confidence, pacing, or argument structure — your AI adapts its coaching style."
          />
          <FeatureCard
            icon="📈"
            title="Progress Tracking"
            desc="Sparklines, streaks, personal bests, and score trends across all your sessions."
          />
          <FeatureCard
            icon="🌙"
            title="Dark & Light Modes"
            desc="Polished glassmorphism in dark mode, clean and readable in light — you choose."
          />
        </div>
      </section>

      {/* How it works */}
      <section style={styles.howSection}>
        <h2 style={styles.sectionTitle}>How It Works</h2>
        <div style={styles.stepsRow}>
          {[
            { num: "1", title: "Pick a topic", desc: "Choose from suggestions or type your own debate motion." },
            { num: "2", title: "Debate the AI", desc: "Speak your arguments — the AI responds, challenges, and adapts." },
            { num: "3", title: "Get your report", desc: "See scores, strengths, fallacies, and tips to improve next time." },
          ].map((step) => (
            <div key={step.num} style={styles.stepCard}>
              <div style={styles.stepNum}>{step.num}</div>
              <h3 style={styles.stepTitle}>{step.title}</h3>
              <p style={styles.stepDesc}>{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section style={styles.ctaSection}>
        <div className="glass" style={styles.ctaCard}>
          <h2 style={styles.ctaTitle}>Ready to sharpen your edge?</h2>
          <p style={styles.ctaSub}>Join for free. No credit card, no fluff — just practice and growth.</p>
          <button className="btn-primary" style={styles.ctaBtn} onClick={() => navigate("/auth")}>
            Create Free Account
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer style={styles.footer}>
        <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
          © {new Date().getFullYear()} Debate Coach · Built as a final-year project
        </span>
      </footer>
    </div>
  );
}

/* ── Styles ── */
const styles: Record<string, React.CSSProperties> = {
  page: {
    position: "relative",
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    overflow: "hidden",
  },

  /* Nav */
  nav: {
    width: "100%",
    maxWidth: 1100,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "18px 24px",
    position: "relative",
    zIndex: 10,
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  logoMark: {
    width: 34,
    height: 34,
    borderRadius: 10,
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
  },
  navActions: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  navLink: {
    background: "none",
    border: "none",
    color: "var(--text-secondary)",
    fontSize: "0.88rem",
    fontWeight: 600,
    cursor: "pointer",
    padding: "8px 12px",
  },
  navCta: {
    padding: "8px 20px",
    fontSize: "0.85rem",
  },
  themeToggle: {
    background: "none",
    border: "none",
    fontSize: "1.2rem",
    cursor: "pointer",
    padding: "8px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    opacity: 0.8,
    transition: "opacity 0.2s",
  },

  /* Hero */
  hero: {
    position: "relative",
    zIndex: 10,
    textAlign: "center",
    maxWidth: 720,
    padding: "80px 24px 40px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 20,
  },
  heroBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 16px",
    borderRadius: 999,
    background: "var(--bg-glass)",
    border: "1px solid var(--border)",
    fontSize: "0.78rem",
    fontWeight: 600,
    color: "var(--text-secondary)",
    backdropFilter: "blur(8px)",
  },
  heroPulse: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "var(--success)",
    boxShadow: "0 0 8px var(--success)",
    animation: "pulse 2s infinite",
  },
  heroTitle: {
    fontSize: "clamp(2.2rem, 6vw, 3.8rem)",
    fontWeight: 800,
    lineHeight: 1.08,
    letterSpacing: "-0.035em",
  },
  heroSub: {
    fontSize: "clamp(0.95rem, 2vw, 1.15rem)",
    color: "var(--text-secondary)",
    lineHeight: 1.6,
    maxWidth: 560,
  },
  heroBtns: {
    display: "flex",
    gap: 12,
    flexWrap: "wrap",
    justifyContent: "center",
    marginTop: 8,
  },
  heroCtaPrimary: {
    padding: "14px 32px",
    fontSize: "1rem",
  },
  heroCtaSecondary: {
    padding: "14px 28px",
    fontSize: "0.95rem",
  },
  statsRow: {
    display: "flex",
    gap: 14,
    flexWrap: "wrap",
    justifyContent: "center",
    marginTop: 32,
  },
  statPill: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 2,
    padding: "10px 20px",
    borderRadius: 12,
    background: "var(--bg-glass)",
    border: "1px solid var(--border)",
    backdropFilter: "blur(8px)",
    minWidth: 130,
  },
  statValue: {
    fontSize: "0.95rem",
    fontWeight: 800,
    color: "var(--accent)",
  },
  statLabel: {
    fontSize: "0.72rem",
    color: "var(--text-muted)",
    fontWeight: 500,
  },

  /* Features */
  featuresSection: {
    position: "relative",
    zIndex: 10,
    width: "100%",
    maxWidth: 1100,
    padding: "80px 24px 40px",
    textAlign: "center",
  },
  sectionTitle: {
    fontSize: "clamp(1.5rem, 3.5vw, 2.2rem)",
    fontWeight: 800,
    letterSpacing: "-0.02em",
    marginBottom: 10,
  },
  sectionSub: {
    color: "var(--text-secondary)",
    fontSize: "0.95rem",
    maxWidth: 480,
    margin: "0 auto 40px",
  },
  featuresGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: 16,
    textAlign: "left",
  },
  featureCard: {
    padding: "22px 20px",
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  featureIcon: {
    fontSize: "1.5rem",
  },
  featureTitle: {
    fontSize: "1rem",
    fontWeight: 700,
  },
  featureDesc: {
    fontSize: "0.85rem",
    color: "var(--text-secondary)",
    lineHeight: 1.5,
  },

  /* How it works */
  howSection: {
    position: "relative",
    zIndex: 10,
    width: "100%",
    maxWidth: 900,
    padding: "60px 24px 40px",
    textAlign: "center",
  },
  stepsRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: 20,
    marginTop: 36,
    textAlign: "center",
  },
  stepCard: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 10,
  },
  stepNum: {
    width: 44,
    height: 44,
    borderRadius: "50%",
    background: "var(--gradient)",
    color: "white",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "1.1rem",
    fontWeight: 800,
    boxShadow: "0 0 20px var(--accent-glow)",
  },
  stepTitle: {
    fontSize: "1rem",
    fontWeight: 700,
  },
  stepDesc: {
    fontSize: "0.85rem",
    color: "var(--text-secondary)",
    lineHeight: 1.5,
    maxWidth: 240,
  },

  /* CTA */
  ctaSection: {
    position: "relative",
    zIndex: 10,
    width: "100%",
    maxWidth: 700,
    padding: "60px 24px 40px",
  },
  ctaCard: {
    textAlign: "center",
    padding: "44px 32px",
  },
  ctaTitle: {
    fontSize: "clamp(1.4rem, 3vw, 1.9rem)",
    fontWeight: 800,
    letterSpacing: "-0.02em",
    marginBottom: 10,
  },
  ctaSub: {
    color: "var(--text-secondary)",
    fontSize: "0.9rem",
    marginBottom: 24,
  },
  ctaBtn: {
    padding: "14px 40px",
    fontSize: "1rem",
  },

  /* Footer */
  footer: {
    position: "relative",
    zIndex: 10,
    padding: "30px 24px 24px",
    textAlign: "center",
  },
};
