"use client";

import { Cpu } from "lucide-react";

export function LoadingPanel() {
  return (
    <div className="flex h-[520px] w-full flex-col items-center justify-center rounded-[calc(var(--radius-xl)-6px)] bg-[var(--bg-deep)] shadow-[inset_6px_6px_20px_rgba(158,138,114,0.3)] md:h-[600px]">
      <div className="relative flex h-24 w-24 items-center justify-center">
        {/* Outer pulsating ring */}
        <div className="absolute inset-0 animate-[spin_4s_linear_infinite] rounded-full border-2 border-dashed border-[var(--teal-soft)] opacity-40" />
        
        {/* Inner solid ring */}
        <div className="absolute inset-2 animate-[spin_3s_linear_reverse_infinite] rounded-full border border-[var(--orange-soft)] opacity-50" />
        
        {/* Central core icon */}
        <div className="absolute inset-0 flex items-center justify-center">
          <Cpu className="animate-pulse-glow text-[var(--teal)] drop-shadow-md" size={32} />
        </div>
      </div>
      
      <div className="mt-8 flex flex-col items-center gap-2">
        <span className="data-font animate-pulse text-[11px] font-bold uppercase tracking-[0.4em] text-[var(--teal)]">
          Decrypting Coordinates
        </span>
        <span className="data-font text-[9px] uppercase tracking-widest text-[var(--muted)]">
          Initializing MapLibre 3D Core...
        </span>
      </div>
    </div>
  );
}
