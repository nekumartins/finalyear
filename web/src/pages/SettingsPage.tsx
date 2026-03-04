import React from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "../stores/appStore";

export function SettingsPage() {
  const navigate = useNavigate();
  const {
    preferredMode,
    preferredPosition,
    coachingGoal,
    emailUpdates,
    compactMetrics,
    ttsProvider,
    ttsVoice,
    setPreferredMode,
    setPreferredPosition,
    setCoachingGoal,
    setEmailUpdates,
    setCompactMetrics,
    setTtsProvider,
    setTtsVoice,
    resetOnboarding,
  } = useAppStore();

  return (
    <div style={styles.page}>
      <section className="glass" style={styles.panel}>
        <h1 style={styles.title}>Settings</h1>
        <p style={styles.subtitle}>Control your default coaching and app behavior.</p>
      </section>

      <section className="glass" style={styles.panel}>
        <h2 style={styles.heading}>Debate Defaults</h2>
        <div style={styles.rowGroup}>
          <label style={styles.label}>Preferred Mode</label>
          <div style={styles.inlineChoices}>
            <button
              style={{ ...styles.pillBtn, ...(preferredMode === "cloud" ? styles.activePill : {}) }}
              onClick={() => setPreferredMode("cloud")}
            >
              ☁️ Cloud
            </button>
            <button
              style={{ ...styles.pillBtn, ...(preferredMode === "edge" ? styles.activePill2 : {}) }}
              onClick={() => setPreferredMode("edge")}
            >
              ⚡ Edge
            </button>
          </div>
        </div>

        <div style={styles.rowGroup}>
          <label style={styles.label}>Default Stance</label>
          <div style={styles.inlineChoices}>
            <button
              style={{ ...styles.pillBtn, ...(preferredPosition === "for" ? styles.successPill : {}) }}
              onClick={() => setPreferredPosition("for")}
            >
              👍 For
            </button>
            <button
              style={{ ...styles.pillBtn, ...(preferredPosition === "against" ? styles.dangerPill : {}) }}
              onClick={() => setPreferredPosition("against")}
            >
              👎 Against
            </button>
          </div>
        </div>

        <div style={styles.rowGroup}>
          <label style={styles.label}>Coaching Goal</label>
          <select value={coachingGoal} onChange={(e) => setCoachingGoal(e.target.value as "confidence" | "speed" | "structure")}> 
            <option value="confidence">Confidence</option>
            <option value="speed">Pacing</option>
            <option value="structure">Argument Flow</option>
          </select>
        </div>
      </section>

      <section className="glass" style={styles.panel}>
        <h2 style={styles.heading}>AI Voice (TTS)</h2>
        <p style={styles.subtitle}>Choose how the AI debate coach speaks back to you.</p>

        <div style={styles.rowGroup}>
          <label style={styles.label}>TTS Engine</label>
          <div style={styles.inlineChoices}>
            <button
              style={{ ...styles.pillBtn, ...(ttsProvider === "edge-tts" ? styles.activePill : {}) }}
              onClick={() => { setTtsProvider("edge-tts"); setTtsVoice("en-US-GuyNeural"); }}
            >
              🎙️ Edge TTS
            </button>
            <button
              style={{ ...styles.pillBtn, ...(ttsProvider === "gemini" ? styles.geminiPill : {}) }}
              onClick={() => { setTtsProvider("gemini"); setTtsVoice("Kore"); }}
            >
              ✨ Gemini
            </button>
            <button
              style={{ ...styles.pillBtn, ...(ttsProvider === "gtts" ? styles.activePill2 : {}) }}
              onClick={() => { setTtsProvider("gtts"); setTtsVoice("en-us"); }}
            >
              🌐 Google TTS
            </button>
            <button
              style={{ ...styles.pillBtn, ...(ttsProvider === "none" ? { border: "1px solid var(--border)", background: "var(--bg-secondary)" } : {}) }}
              onClick={() => { setTtsProvider("none"); setTtsVoice("silent"); }}
            >
              🔇 Off
            </button>
          </div>
        </div>

        {ttsProvider === "edge-tts" && (
          <div style={styles.rowGroup}>
            <label style={styles.label}>Voice</label>
            <select
              value={ttsVoice}
              onChange={(e) => setTtsVoice(e.target.value)}
            >
              <optgroup label="🇺🇸 US English">
                <option value="en-US-GuyNeural">Guy (Male)</option>
                <option value="en-US-DavisNeural">Davis (Male)</option>
                <option value="en-US-JasonNeural">Jason (Male)</option>
                <option value="en-US-TonyNeural">Tony (Male)</option>
                <option value="en-US-JennyNeural">Jenny (Female)</option>
                <option value="en-US-AriaNeural">Aria (Female)</option>
                <option value="en-US-SaraNeural">Sara (Female)</option>
                <option value="en-US-NancyNeural">Nancy (Female)</option>
              </optgroup>
              <optgroup label="🇬🇧 UK English">
                <option value="en-GB-RyanNeural">Ryan (Male)</option>
                <option value="en-GB-ThomasNeural">Thomas (Male)</option>
                <option value="en-GB-SoniaNeural">Sonia (Female)</option>
              </optgroup>
              <optgroup label="🇦🇺 Australian">
                <option value="en-AU-WilliamNeural">William (Male)</option>
                <option value="en-AU-NatashaNeural">Natasha (Female)</option>
              </optgroup>
              <optgroup label="🇿🇦 South African">
                <option value="en-ZA-LukeNeural">Luke (Male)</option>
                <option value="en-ZA-LeahNeural">Leah (Female)</option>
              </optgroup>
            </select>
          </div>
        )}

        {ttsProvider === "gemini" && (
          <div style={styles.rowGroup}>
            <label style={styles.label}>Voice</label>
            <select
              value={ttsVoice}
              onChange={(e) => setTtsVoice(e.target.value)}
            >
              <optgroup label="🎯 Authoritative">
                <option value="Kore">Kore — Firm</option>
                <option value="Orus">Orus — Firm</option>
                <option value="Alnilam">Alnilam — Firm</option>
                <option value="Charon">Charon — Informative</option>
                <option value="Rasalgethi">Rasalgethi — Informative</option>
                <option value="Sadaltager">Sadaltager — Knowledgeable</option>
              </optgroup>
              <optgroup label="☀️ Bright & Upbeat">
                <option value="Zephyr">Zephyr — Bright</option>
                <option value="Puck">Puck — Upbeat</option>
                <option value="Autonoe">Autonoe — Bright</option>
                <option value="Laomedeia">Laomedeia — Upbeat</option>
                <option value="Sadachbia">Sadachbia — Lively</option>
                <option value="Fenrir">Fenrir — Excitable</option>
              </optgroup>
              <optgroup label="🌊 Smooth & Gentle">
                <option value="Algieba">Algieba — Smooth</option>
                <option value="Despina">Despina — Smooth</option>
                <option value="Achernar">Achernar — Soft</option>
                <option value="Vindemiatrix">Vindemiatrix — Gentle</option>
                <option value="Sulafat">Sulafat — Warm</option>
                <option value="Achird">Achird — Friendly</option>
              </optgroup>
              <optgroup label="🍃 Relaxed & Clear">
                <option value="Aoede">Aoede — Breezy</option>
                <option value="Callirrhoe">Callirrhoe — Easy-going</option>
                <option value="Umbriel">Umbriel — Easy-going</option>
                <option value="Zubenelgenubi">Zubenelgenubi — Casual</option>
                <option value="Iapetus">Iapetus — Clear</option>
                <option value="Erinome">Erinome — Clear</option>
              </optgroup>
              <optgroup label="🎭 Character">
                <option value="Leda">Leda — Youthful</option>
                <option value="Enceladus">Enceladus — Breathy</option>
                <option value="Algenib">Algenib — Gravelly</option>
                <option value="Gacrux">Gacrux — Mature</option>
                <option value="Schedar">Schedar — Even</option>
                <option value="Pulcherrima">Pulcherrima — Forward</option>
              </optgroup>
            </select>
            <p style={styles.voiceHint}>
              Gemini voices are expressive AI voices powered by Google's latest model.
            </p>
          </div>
        )}

        {ttsProvider === "gtts" && (
          <div style={styles.rowGroup}>
            <label style={styles.label}>Accent</label>
            <select
              value={ttsVoice}
              onChange={(e) => setTtsVoice(e.target.value)}
            >
              <option value="en-us">English (US)</option>
              <option value="en-gb">English (UK)</option>
              <option value="en-au">English (AU)</option>
              <option value="en-za">English (ZA)</option>
              <option value="en-in">English (IN)</option>
            </select>
          </div>
        )}
      </section>

      <section className="glass" style={styles.panel}>
        <h2 style={styles.heading}>App Preferences</h2>
        <div style={styles.toggleRow}>
          <div>
            <strong style={styles.toggleTitle}>Email Updates</strong>
            <p style={styles.toggleDesc}>Receive feature update summaries.</p>
          </div>
          <button style={styles.toggleBtn} onClick={() => setEmailUpdates(!emailUpdates)}>
            {emailUpdates ? "On" : "Off"}
          </button>
        </div>

        <div style={styles.toggleRow}>
          <div>
            <strong style={styles.toggleTitle}>Compact Metrics</strong>
            <p style={styles.toggleDesc}>Prefer denser layout on metrics and history pages.</p>
          </div>
          <button style={styles.toggleBtn} onClick={() => setCompactMetrics(!compactMetrics)}>
            {compactMetrics ? "On" : "Off"}
          </button>
        </div>
      </section>

      <section className="glass" style={styles.panel}>
        <h2 style={styles.heading}>Onboarding</h2>
        <p style={styles.subtitle}>Restart the onboarding wizard to redefine your defaults.</p>
        <button
          className="btn-secondary"
          onClick={() => {
            resetOnboarding();
            navigate("/onboarding");
          }}
        >
          Restart Onboarding
        </button>
      </section>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    animation: "fadeSlideUp 0.35s ease",
  },
  panel: {
    padding: "18px",
  },
  title: {
    fontSize: "1.45rem",
    letterSpacing: "-0.02em",
  },
  heading: {
    fontSize: "1rem",
    marginBottom: "12px",
  },
  subtitle: {
    color: "var(--text-secondary)",
    fontSize: "0.88rem",
  },
  rowGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    marginBottom: "14px",
  },
  label: {
    color: "var(--text-secondary)",
    fontSize: "0.75rem",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 600,
  },
  inlineChoices: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
  },
  pillBtn: {
    border: "1px solid var(--border)",
    background: "var(--bg-glass)",
    color: "var(--text-primary)",
    borderRadius: "999px",
    padding: "8px 13px",
    fontSize: "0.85rem",
    fontWeight: 600,
  },
  activePill: {
    border: "1px solid rgba(124,111,239,0.45)",
    color: "var(--accent)",
    background: "rgba(124,111,239,0.14)",
  },
  activePill2: {
    border: "1px solid rgba(91,142,240,0.45)",
    color: "var(--accent-2)",
    background: "rgba(91,142,240,0.14)",
  },
  geminiPill: {
    border: "1px solid rgba(251,188,5,0.50)",
    color: "#fbbf24",
    background: "rgba(251,188,5,0.12)",
  },
  successPill: {
    border: "1px solid rgba(52,211,153,0.45)",
    color: "var(--success)",
    background: "rgba(52,211,153,0.14)",
  },
  dangerPill: {
    border: "1px solid rgba(248,113,113,0.45)",
    color: "var(--danger)",
    background: "rgba(248,113,113,0.14)",
  },
  toggleRow: {
    border: "1px solid var(--border)",
    borderRadius: "10px",
    background: "var(--bg-glass)",
    padding: "10px 12px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "10px",
    gap: "12px",
  },
  toggleTitle: {
    fontSize: "0.9rem",
  },
  toggleDesc: {
    fontSize: "0.8rem",
    color: "var(--text-secondary)",
    marginTop: "2px",
  },
  toggleBtn: {
    minWidth: "58px",
    borderRadius: "999px",
    padding: "8px 10px",
    border: "1px solid var(--border)",
    background: "var(--bg-secondary)",
    color: "var(--text-primary)",
    fontSize: "0.8rem",
    fontWeight: 700,
  },
  voiceHint: {
    color: "var(--text-secondary)",
    fontSize: "0.78rem",
    marginTop: "2px",
  },
};
