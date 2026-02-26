import React from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAppStore } from "../stores/appStore";

export function OnboardingGuard() {
  const location = useLocation();
  const onboardingCompleted = useAppStore((s) => s.onboardingCompleted);

  if (!onboardingCompleted && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }

  if (onboardingCompleted && location.pathname === "/onboarding") {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
