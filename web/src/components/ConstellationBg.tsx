/**
 * ConstellationBg — Animated canvas with drifting stars and connecting lines.
 * Renders as a fixed, full-viewport backdrop behind all page content.
 * Reads data-theme attribute in real time so it reacts to dark/light switches.
 */
import { useEffect, useRef } from "react";

export function ConstellationBg() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf: number;
    let stars: {
      x: number; y: number; vx: number; vy: number;
      r: number; pulse: number; speed: number;
    }[] = [];

    const STAR_COUNT = 90;
    const CONNECT_DIST = 140;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();

    const seed = () => {
      stars = Array.from({ length: STAR_COUNT }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.15,
        vy: (Math.random() - 0.5) * 0.15,
        r: Math.random() * 1.5 + 0.5,
        pulse: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.008 + 0.004,
      }));
    };
    seed();

    const isLight = () =>
      document.documentElement.getAttribute("data-theme") === "light";

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const light = isLight();
      const dotColor = light ? "rgba(90,72,210," : "rgba(160,150,255,";
      const lineColor = light ? "rgba(90,72,210," : "rgba(124,111,239,";
      // Light backgrounds need higher opacity to stay visible
      const lineAlphaScale = light ? 0.35 : 0.12;
      const dotBaseAlpha = light ? 0.45 : 0.25;
      const dotSwing = light ? 0.2 : 0.15;

      for (const s of stars) {
        s.x += s.vx;
        s.y += s.vy;
        if (s.x < 0) s.x = canvas.width;
        if (s.x > canvas.width) s.x = 0;
        if (s.y < 0) s.y = canvas.height;
        if (s.y > canvas.height) s.y = 0;
        s.pulse += s.speed;
      }

      // Connecting lines
      for (let i = 0; i < stars.length; i++) {
        for (let j = i + 1; j < stars.length; j++) {
          const dx = stars[i].x - stars[j].x;
          const dy = stars[i].y - stars[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < CONNECT_DIST) {
            const alpha = (1 - dist / CONNECT_DIST) * lineAlphaScale;
            ctx.strokeStyle = `${lineColor}${alpha})`;
            ctx.lineWidth = light ? 0.7 : 0.5;
            ctx.beginPath();
            ctx.moveTo(stars[i].x, stars[i].y);
            ctx.lineTo(stars[j].x, stars[j].y);
            ctx.stroke();
          }
        }
      }

      // Star dots
      for (const s of stars) {
        const glow = dotBaseAlpha + Math.sin(s.pulse) * dotSwing;
        ctx.fillStyle = `${dotColor}${glow})`;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
      }

      raf = requestAnimationFrame(draw);
    };

    draw();

    const handleResize = () => { resize(); seed(); };
    window.addEventListener("resize", handleResize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
      }}
    />
  );
}
