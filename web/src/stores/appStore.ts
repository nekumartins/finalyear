import { create } from "zustand";
import type { SessionMode } from "./debateStore";

type DebatePosition = "for" | "against";
type CoachingGoal = "confidence" | "speed" | "structure";
type TTSProvider = "edge-tts" | "gemini" | "gtts" | "none";

interface AppState {
  onboardingCompleted: boolean;
  preferredMode: SessionMode;
  preferredPosition: DebatePosition;
  coachingGoal: CoachingGoal;
  profileName: string;
  emailUpdates: boolean;
  compactMetrics: boolean;
  ttsProvider: TTSProvider;
  ttsVoice: string;
  completeOnboarding: (payload: {
    preferredMode: SessionMode;
    preferredPosition: DebatePosition;
    coachingGoal: CoachingGoal;
  }) => void;
  setPreferredMode: (mode: SessionMode) => void;
  setPreferredPosition: (position: DebatePosition) => void;
  setCoachingGoal: (goal: CoachingGoal) => void;
  setProfileName: (name: string) => void;
  setEmailUpdates: (enabled: boolean) => void;
  setCompactMetrics: (enabled: boolean) => void;
  setTtsProvider: (provider: TTSProvider) => void;
  setTtsVoice: (voice: string) => void;
  resetOnboarding: () => void;
}

const STORAGE_KEY = "debate_coach_app_prefs_v1";

type PersistedState = Pick<
  AppState,
  | "onboardingCompleted"
  | "preferredMode"
  | "preferredPosition"
  | "coachingGoal"
  | "profileName"
  | "emailUpdates"
  | "compactMetrics"
  | "ttsProvider"
  | "ttsVoice"
>;

const defaults: PersistedState = {
  onboardingCompleted: false,
  preferredMode: "cloud",
  preferredPosition: "for",
  coachingGoal: "confidence",
  profileName: "",
  emailUpdates: false,
  compactMetrics: false,
  ttsProvider: "edge-tts",
  ttsVoice: "en-US-GuyNeural",
};

function loadPrefs(): PersistedState {
  if (typeof window === "undefined") return defaults;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Partial<PersistedState>;
    return {
      ...defaults,
      ...parsed,
    };
  } catch {
    return defaults;
  }
}

function savePrefs(state: PersistedState): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function persistedFromState(state: AppState): PersistedState {
  return {
    onboardingCompleted: state.onboardingCompleted,
    preferredMode: state.preferredMode,
    preferredPosition: state.preferredPosition,
    coachingGoal: state.coachingGoal,
    profileName: state.profileName,
    emailUpdates: state.emailUpdates,
    compactMetrics: state.compactMetrics,
    ttsProvider: state.ttsProvider,
    ttsVoice: state.ttsVoice,
  };
}

export const useAppStore = create<AppState>((set, get) => ({
  ...loadPrefs(),

  completeOnboarding: (payload) =>
    set((s) => {
      const next = {
        ...s,
        onboardingCompleted: true,
        preferredMode: payload.preferredMode,
        preferredPosition: payload.preferredPosition,
        coachingGoal: payload.coachingGoal,
      };
      savePrefs(persistedFromState(next));
      return next;
    }),

  setPreferredMode: (preferredMode) =>
    set((s) => {
      const next = { ...s, preferredMode };
      savePrefs(persistedFromState(next));
      return next;
    }),

  setPreferredPosition: (preferredPosition) =>
    set((s) => {
      const next = { ...s, preferredPosition };
      savePrefs(persistedFromState(next));
      return next;
    }),

  setCoachingGoal: (coachingGoal) =>
    set((s) => {
      const next = { ...s, coachingGoal };
      savePrefs(persistedFromState(next));
      return next;
    }),

  setProfileName: (profileName) =>
    set((s) => {
      const next = { ...s, profileName };
      savePrefs(persistedFromState(next));
      return next;
    }),

  setEmailUpdates: (emailUpdates) =>
    set((s) => {
      const next = { ...s, emailUpdates };
      savePrefs(persistedFromState(next));
      return next;
    }),

  setCompactMetrics: (compactMetrics) =>
    set((s) => {
      const next = { ...s, compactMetrics };
      savePrefs(persistedFromState(next));
      return next;
    }),

  setTtsProvider: (ttsProvider) =>
    set((s) => {
      const next = { ...s, ttsProvider };
      savePrefs(persistedFromState(next));
      return next;
    }),

  setTtsVoice: (ttsVoice) =>
    set((s) => {
      const next = { ...s, ttsVoice };
      savePrefs(persistedFromState(next));
      return next;
    }),

  resetOnboarding: () =>
    set((s) => {
      const next = { ...s, onboardingCompleted: false };
      savePrefs(persistedFromState(next));
      return next;
    }),
}));
