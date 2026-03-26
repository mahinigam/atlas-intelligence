"use client";

import { motion } from "framer-motion";

type SentimentGaugeProps = {
  score: number; // -1 to 1
};

export function SentimentGauge({ score }: SentimentGaugeProps) {
  // Convert -1 to 1 into 0 to 180 degrees
  const clampedScore = Math.max(-1, Math.min(1, score));
  const rotation = ((clampedScore + 1) / 2) * 180;

  const getLabel = (s: number) => {
    if (s <= -0.5) return "CRITICAL";
    if (s < 0) return "TENSE";
    if (s === 0) return "NEUTRAL";
    if (s < 0.5) return "STABLE";
    return "OPTIMAL";
  };

  const getColor = (s: number) => {
    if (s < -0.2) return "var(--negative)";
    if (s > 0.2) return "var(--positive)";
    return "var(--orange)";
  };

  return (
    <div className="relative flex flex-col items-center">
      <div className="relative h-[60px] w-[120px] overflow-hidden">
        {/* The colored arc */}
        <div
          className="absolute left-0 top-0 h-[120px] w-[120px] rounded-full border-[12px] border-b-transparent border-l-transparent border-r-[var(--positive)] border-t-transparent"
          style={{
            borderTopColor: "var(--orange)",
            borderLeftColor: "var(--negative)",
            transform: "rotate(-45deg)",
          }}
        />
        {/* Track background */}
        <div className="absolute left-0 top-0 h-[120px] w-[120px] rounded-full border-[12px] border-[rgba(23,49,58,0.06)]" />

        {/* The needle */}
        <motion.div
          className="absolute bottom-0 left-1/2 h-[50px] w-1 origin-bottom bg-[var(--text)] rounded-full shadow-md"
          initial={{ rotate: 90 }}
          animate={{ rotate: rotation }}
          transition={{ type: "spring", stiffness: 60, damping: 12 }}
          style={{ transformOrigin: "bottom center", marginLeft: "-2px" }}
        >
          {/* Needle Center Pin */}
          <div className="absolute -bottom-2 -left-1.5 h-4 w-4 rounded-full bg-[var(--text)] border-2 border-[var(--bg)]" />
        </motion.div>
      </div>

      <div className="mt-4 flex flex-col items-center">
        <span
          className="data-font text-xl font-bold tracking-wider"
          style={{ color: getColor(clampedScore) }}
        >
          {clampedScore.toFixed(2)}
        </span>
        <span className="data-font text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">
          {getLabel(clampedScore)}
        </span>
      </div>
    </div>
  );
}
