"use client";

import { motion } from "framer-motion";

type SentimentGaugeProps = {
  score: number; // -1 to 1
};

export function SentimentGauge({ score }: SentimentGaugeProps) {
  // Clamp score between -1 and 1
  const clampedScore = Math.max(-1, Math.min(1, score));
  
  // Map score (-1 to +1) to rotation (-90deg to +90deg)
  const rotation = clampedScore * 90;

  const getLabel = (s: number) => {
    if (s <= -0.5) return "CRITICAL";
    if (s < -0.1) return "TENSE";
    if (s <= 0.1) return "NEUTRAL";
    if (s < 0.5) return "STABLE";
    return "OPTIMAL";
  };

  const getColor = (s: number) => {
    if (s < -0.2) return "var(--negative)";
    if (s > 0.2) return "var(--positive)";
    return "var(--orange)";
  };

  const currentColor = getColor(clampedScore);
  const label = getLabel(clampedScore);

  return (
    <div className="flex flex-col items-center">
      {/* Premium Claymorphic Gauge Housing */}
      <div className="relative flex items-center justify-center rounded-[32px] bg-[rgba(248,242,234,0.6)] px-6 pt-6 pb-4 shadow-[inset_6px_6px_16px_rgba(158,138,114,0.15),inset_-6px_-6px_16px_rgba(255,255,255,0.9)] border border-[rgba(23,49,58,0.03)]">
        
        {/* The SVG Speedometer */}
        <div className="relative h-[85px] w-[170px] overflow-hidden">
          <svg viewBox="0 0 200 110" className="absolute left-0 top-0 h-full w-full overflow-visible">
            <defs>
              <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="var(--negative)" />
                <stop offset="50%" stopColor="var(--orange)" />
                <stop offset="100%" stopColor="var(--positive)" />
              </linearGradient>
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Background Track Arc */}
            <path
              d="M 20 100 A 80 80 0 0 1 180 100"
              fill="none"
              stroke="rgba(23,49,58,0.06)"
              strokeWidth="14"
              strokeLinecap="round"
            />

            {/* Colored Gradient Arc */}
            <path
              d="M 20 100 A 80 80 0 0 1 180 100"
              fill="none"
              stroke="url(#gaugeGradient)"
              strokeWidth="14"
              strokeLinecap="round"
              opacity="0.9"
            />

            {/* Tick Marks */}
            <g stroke="rgba(23,49,58,0.2)" strokeWidth="2" strokeLinecap="round">
              <line x1="20" y1="100" x2="30" y2="100" />    {/* -1.0 */}
              <line x1="46" y1="43" x2="55" y2="52" />      {/* -0.5 */}
              <line x1="100" y1="20" x2="100" y2="30" />    {/*  0.0 */}
              <line x1="154" y1="43" x2="145" y2="52" />    {/* +0.5 */}
              <line x1="180" y1="100" x2="170" y2="100" />  {/* +1.0 */}
            </g>

            {/* Animated Needle Group */}
            <motion.g
              initial={{ rotate: 0 }}
              animate={{ rotate: rotation }}
              transition={{ type: "spring", stiffness: 60, damping: 12, mass: 1 }}
              style={{ originX: 100, originY: 100 }}
            >
              {/* Outer Glow behind the needle */}
              <line
                x1="100" y1="100" x2="100" y2="28"
                stroke={currentColor}
                strokeWidth="6"
                strokeLinecap="round"
                opacity="0.3"
                filter="url(#glow)"
              />
              {/* Main Needle Line */}
              <line
                x1="100" y1="100" x2="100" y2="28"
                stroke="var(--bg-deep)"
                strokeWidth="4"
                strokeLinecap="round"
              />
              {/* Inner Pivot Base */}
              <circle cx="100" cy="100" r="8" fill="var(--bg-deep)" />
              <circle cx="100" cy="100" r="4" fill={currentColor} />
            </motion.g>
          </svg>
        </div>

        {/* Floating Metrics Badge */}
        <div className="absolute -bottom-5 flex flex-col items-center rounded-2xl bg-[rgba(255,255,255,0.85)] px-5 py-1.5 shadow-[grid_glow_shadow] backdrop-blur-md border border-[rgba(23,49,58,0.06)]">
          <span
            className="data-font text-[22px] font-bold tracking-widest leading-none drop-shadow-sm"
            style={{ color: currentColor }}
          >
            {clampedScore > 0 ? "+" : ""}{clampedScore.toFixed(2)}
          </span>
          <span className="data-font mt-1 text-[9px] uppercase tracking-[0.25em] font-extrabold text-[var(--muted)]">
            {label}
          </span>
        </div>
      </div>
    </div>
  );
}
