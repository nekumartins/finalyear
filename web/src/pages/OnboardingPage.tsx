import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "../stores/appStore";
import type { SessionMode } from "../stores/debateStore";

type DebatePosition = "for" | "against";
type CoachingGoal = "confidence" | "speed" | "structure";

const STEPS = ["Your Goal", "Practice Style", "AI Voice"] as const;

const goalOptions: Array<{ id: CoachingGoal; title: string; desc: string; icon: string; color: string }> = [
  {
    id: "confidence",
    title: "Confidence",
    desc: "Practice speaking assertively and holding your ground under pressure. Ideal if you tend to second-guess yourself.",
    icon: "🎯",
    color: "rgba(248,113,113,0.15)",
  },
  {
    id: "speed",
    title: "Pacing & Timing",
    desc: "Improve your speaking rhythm, reduce awkward pauses, and respond faster. Great for timed debates.",
    icon: "⏱️",
    color: "rgba(91,142,240,0.15)",
  },
  {
    id: "structure",
    title: "Argument Flow",
    desc: "Build tighter reasoning, stronger rebuttals, and more persuasive conclusions. Perfect for competitive debaters.",
    icon: "🧠",
    color: "rgba(124,111,239,0.15)",
  },
];

const voicePresets = [
  { provider: "edge-tts", voice: "en-US-GuyNeural", label: "Guy", desc: "Calm & clear", gender: "♂" },
  { provider: "edge-tts", voice: "en-US-JennyNeural", label: "Jenny", desc: "Warm & friendly", gender: "♀" },
  { provider: "edge-tts", voice: "en-GB-RyanNeural", label: "Ryan", desc: "British & polished", gender: "♂" },
  { provider: "edge-tts", voice: "en-US-AriaNeural", label: "Aria", desc: "Expressive & bold", gender: "♀" },
  { provider: "gemini", voice: "Kore", label: "Kore", desc: "Gemini native", gender: "✦" },
  { provider: "none", voice: "", label: "No voice", desc: "Text only", gender: "🔇" },
];

export function OnboardingPage() {
  const navigate = useNavigate();
  const onboardingCompleted = useAppStore((s) => s.onboardingCompleted);
  const completeOnboarding = useAppStore((s) => s.completeOnboarding);
  const setTtsProvider = useAppStore((s) => s.setTtsProvider);
  const setTtsVoice = useAppStore((s) => s.setTtsVoice);

  const [step, setStep] = useState(0);
  const [dir, setDir] = useState<"fwd" | "back">("fwd");
  const [preferredMode, setPreferredMode] = useState<SessionMode>("cloud");
  const [preferredPosition, setPreferredPosition] = useState<DebatePosition>("for");
  const [coachingGoal, setCoachingGoal] = useState<CoachingGoal>("confidence");
  const [selectedVoiceIdx, setSelectedVoiceIdx] = useState(0);

  useEffect(() => {
    if (onboardingCompleted) navigate("/dashboard");
  }, [onboardingCompleted, navigate]);

  const goNext = () => { setDir("fwd"); setStep((s) => Math.min(s + 1, 2)); };
  const goBack = () => { setDir("back"); setStep((s) => Math.max(s - 1, 0)); };

  const handleFinish = () => {
    const v = voicePresets[selectedVoiceIdx];
    setTtsProvider(v.provider as any);
    setTtsVoice(v.voice);
    completeOnboarding({ preferredMode, preferredPosition, coachingGoal });
    navigate("/dashboard");
  };

  return (
    <div style={styles.page}>
      <div className="glass" style={styles.card}>
        {/* Progress bar */}
        <div style={styles.progressBar}>
          {STEPS.map((label, i) => (
            <React.Fragment key={label}>
              <div style={{
                display: "flex", alignItems: "center", gap: 6,
                opacity: i <= step ? 1 : 0.4,
                transition: "opacity 0.3s",
              }}>
                <div style={{
                  width: 24, height: 24, borderRadius: "50%",
                  background: i < step ? "var(--success)" : i === step ? "var(--gradient)" : "var(--bg-secondary)",
                  color: i <= step ? "white" : "var(--text-muted)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "0.7rem", fontWeight: 700,
                  transition: "all 0.3s",
                }}>
                  {i < step ? "✓" : i + 1}
                </div>
                <span style={{
                  fontSize: "0.78rem", fontWeight: 600,
                  color: i <= step ? "var(--text-primary)" : "var(--text-muted)",
                }}>{label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div style={{
                  flex: 1, height: 2, borderRadius: 1,
                  background: i < step ? "var(--success)" : "var(--border)",
                  transition: "background 0.3s",
                }} />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Step content with slide animation */}
        <div
          key={step}
          style={{
            animation: `${dir === "fwd" ? "slideInRight" : "slideInLeft"} 0.3s ease`,
          }}
        >
          {step === 0 && <StepGoal goal={coachingGoal} setGoal={setCoachingGoal} />}
          {step === 1 && (
            <StepStyle
              mode={preferredMode} setMode={setPreferredMode}
              position={preferredPosition} setPosition={setPreferredPosition}
            />
          )}
          {step === 2 && (
            <StepVoice selectedIdx={selectedVoiceIdx} setSelectedIdx={setSelectedVoiceIdx} />
          )}
        </div>

        {/* Navigation */}
        <div style={styles.navRow}>
          {step > 0 ? (
            <button style={styles.backBtn} onClick={goBack}>← Back</button>
          ) : <div />}
          {step < 2 ? (
            <button className="btn-primary" style={styles.nextBtn} onClick={goNext}>
              Continue →
            </button>
          ) : (
            <button className="btn-primary" style={styles.nextBtn} onClick={handleFinish}>
              🚀 Start Debating
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Step 1: Coaching Goal ── */
function StepGoal({ goal, setGoal }: { goal: CoachingGoal; setGoal: (g: CoachingGoal) => void }) {
  return (
    <div style={styles.stepBody}>
      <div style={styles.stepHeader}>
        <h1 style={styles.stepTitle}>What brings you here?</h1>
        <p style={styles.stepSubtitle}>Pick the skill you want to sharpen most. Your AI coach will adapt to this.</p>
      </div>
      <div style={styles.goalGrid}>
        {goalOptions.map((g) => (
          <button
            key={g.id}
            style={{
              ...styles.goalCard,
              ...(goal === g.id ? styles.goalCardActive : {}),
              borderColor: goal === g.id ? "var(--accent)" : "var(--border)",
            }}
            onClick={() => setGoal(g.id)}
          >
            <div style={{ ...styles.goalIconCircle, background: g.color }}>
              <span style={{ fontSize: "1.4rem" }}>{g.icon}</span>
            </div>
            <span style={styles.goalTitle}>{g.title}</span>
            <span style={styles.goalDesc}>{g.desc}</span>
            {goal === g.id && <div style={styles.checkmark}>✓</div>}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ── Step 2: Mode + Stance ── */
function StepStyle({
  mode, setMode, position, setPosition,
}: {
  mode: SessionMode; setMode: (m: SessionMode) => void;
  position: DebatePosition; setPosition: (p: DebatePosition) => void;
}) {
  return (
    <div style={styles.stepBody}>
      <div style={styles.stepHeader}>
        <h1 style={styles.stepTitle}>How do you like to practice?</h1>
        <p style={styles.stepSubtitle}>These are your defaults — you can always change per session.</p>
      </div>

      <div style={{ marginBottom: 24 }}>
        <label style={styles.label}>Processing Mode</label>
        <div style={styles.choiceRow}>
          <button
            style={{ ...styles.choice, ...(mode === "cloud" ? styles.choiceAccent : {}) }}
            onClick={() => setMode("cloud")}
          >
            <span style={{ fontSize: "1.3rem" }}>☁️</span>
            <div>
              <div style={styles.choiceTitle}>Cloud</div>
              <div style={styles.choiceMeta}>Higher quality transcription & smarter AI responses</div>
            </div>
          </button>
          <button
            style={{ ...styles.choice, ...(mode === "edge" ? styles.choiceBlue : {}) }}
            onClick={() => setMode("edge")}
          >
            <span style={{ fontSize: "1.3rem" }}>⚡</span>
            <div>
              <div style={styles.choiceTitle}>Edge</div>
              <div style={styles.choiceMeta}>Lower latency, processes locally on device</div>
            </div>
          </button>
        </div>
      </div>

      <div>
        <label style={styles.label}>Default Stance</label>
        <div style={styles.choiceRow}>
          <button
            style={{ ...styles.choice, ...(position === "for" ? styles.choiceGreen : {}) }}
            onClick={() => setPosition("for")}
          >
            <span style={{ fontSize: "1.3rem" }}>👍</span>
            <div>
              <div style={styles.choiceTitle}>For the motion</div>
              <div style={styles.choiceMeta}>You defend and support the topic</div>
            </div>
          </button>
          <button
            style={{ ...styles.choice, ...(position === "against" ? styles.choiceRed : {}) }}
            onClick={() => setPosition("against")}
          >
            <span style={{ fontSize: "1.3rem" }}>👎</span>
            <div>
              <div style={styles.choiceTitle}>Against the motion</div>
              <div style={styles.choiceMeta}>You challenge and critique the topic</div>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Step 3: Voice ── */
function StepVoice({ selectedIdx, setSelectedIdx }: { selectedIdx: number; setSelectedIdx: (i: number) => void }) {
  return (
    <div style={styles.stepBody}>
      <div style={styles.stepHeader}>
        <h1 style={styles.stepTitle}>Pick your AI coach voice</h1>
        <p style={styles.stepSubtitle}>This is who you'll be debating. Choose a voice that feels right.</p>
      </div>
      <div style={styles.voiceGrid}>
        {voicePresets.map((v, i) => (
          <button
            key={v.label}
            style={{
              ...styles.voiceCard,
              ...(selectedIdx === i ? styles.voiceCardActive : {}),
            }}
            onClick={() => setSelectedIdx(i)}
          >
            <div style={styles.voiceAvatar}>{v.gender}</div>
            <span style={{ fontWeight: 700, fontSize: "0.9rem" }}>{v.label}</span>
            <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{v.desc}</span>
            {selectedIdx === i && <div style={styles.checkmark}>✓</div>}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ── Styles ── */
const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    padding: "40px 20px",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },
  card: {
    width: "100%",
    maxWidth: "740px",
    padding: "30px",
    display: "flex",
    flexDirection: "column",
    gap: "24px",
    overflow: "hidden",
  },
  progressBar: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "0 4px",
  },
  stepBody: {
    display: "flex",
    flexDirection: "column",
    gap: 20,
    minHeight: 320,
  },
  stepHeader: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  stepTitle: {
    fontSize: "clamp(1.3rem, 3vw, 1.8rem)",
    letterSpacing: "-0.02em",
    margin: 0,
  },
  stepSubtitle: {
    color: "var(--text-secondary)",
    fontSize: "0.9rem",
    maxWidth: 520,
    margin: 0,
  },
  label: {
    fontSize: "0.72rem",
    textTransform: "uppercase",
    letterSpacing: "0.07em",
    color: "var(--text-secondary)",
    fontWeight: 600,
    marginBottom: 8,
    display: "block",
  },

  /* Goal cards */
  goalGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: 12,
  },
  goalCard: {
    position: "relative" as const,
    border: "1.5px solid var(--border)",
    borderRadius: 14,
    background: "var(--bg-glass)",
    color: "var(--text-primary)",
    textAlign: "left" as const,
    padding: 18,
    display: "flex",
    flexDirection: "column" as const,
    gap: 10,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  goalCardActive: {
    background: "rgba(124,111,239,0.1)",
    boxShadow: "0 0 20px rgba(124,111,239,0.15)",
  },
  goalIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 12,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  goalTitle: {
    fontWeight: 700,
    fontSize: "0.95rem",
  },
  goalDesc: {
    color: "var(--text-secondary)",
    fontSize: "0.8rem",
    lineHeight: 1.45,
  },

  /* Choice buttons */
  choiceRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    gap: 10,
  },
  choice: {
    position: "relative" as const,
    border: "1.5px solid var(--border)",
    borderRadius: 12,
    background: "var(--bg-glass)",
    color: "var(--text-primary)",
    padding: "14px 16px",
    display: "flex",
    alignItems: "center",
    gap: 12,
    textAlign: "left" as const,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  choiceTitle: { fontWeight: 700, fontSize: "0.9rem" },
  choiceMeta: { fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 2 },
  choiceAccent: {
    borderColor: "rgba(124,111,239,0.5)",
    background: "rgba(124,111,239,0.1)",
  },
  choiceBlue: {
    borderColor: "rgba(91,142,240,0.5)",
    background: "rgba(91,142,240,0.1)",
  },
  choiceGreen: {
    borderColor: "rgba(52,211,153,0.5)",
    background: "rgba(52,211,153,0.1)",
  },
  choiceRed: {
    borderColor: "rgba(248,113,113,0.5)",
    background: "rgba(248,113,113,0.1)",
  },

  /* Voice cards */
  voiceGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
    gap: 10,
  },
  voiceCard: {
    position: "relative" as const,
    border: "1.5px solid var(--border)",
    borderRadius: 14,
    background: "var(--bg-glass)",
    color: "var(--text-primary)",
    padding: 16,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: 6,
    textAlign: "center" as const,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  voiceCardActive: {
    borderColor: "rgba(124,111,239,0.5)",
    background: "rgba(124,111,239,0.1)",
    boxShadow: "0 0 16px rgba(124,111,239,0.15)",
  },
  voiceAvatar: {
    width: 40, height: 40, borderRadius: "50%",
    background: "var(--bg-secondary)",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: "1.1rem",
  },

  /* Checkmark */
  checkmark: {
    position: "absolute" as const,
    top: 8, right: 10,
    width: 20, height: 20, borderRadius: "50%",
    background: "var(--success)", color: "white",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: "0.65rem", fontWeight: 700,
  },

  /* Navigation */
  navRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    borderTop: "1px solid var(--border)",
    paddingTop: 16,
  },
  backBtn: {
    background: "none",
    border: "none",
    color: "var(--text-secondary)",
    cursor: "pointer",
    fontSize: "0.9rem",
    padding: "8px 4px",
  },
  nextBtn: {
    minWidth: 160,
    padding: "10px 20px",
  },
};
