"use client";

type TimeTravelSliderProps = {
  daysBack: number;
  onChange: (days: number) => void;
};

export function TimeTravelSlider({ daysBack, onChange }: TimeTravelSliderProps) {
  const ticks = [0, 3, 7, 14, 30];

  return (
    <section className="panel px-6 py-5 md:px-8 md:py-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="data-font text-xs uppercase tracking-[0.32em] text-[var(--muted)]">Time-Travel Dial</p>
          <h2 className="mt-1 text-xl font-semibold">Historical event window</h2>
        </div>
        <div className="rounded-full bg-[rgba(255,248,237,0.8)] px-4 py-2 shadow-[var(--shadow-inner)]">
          <span className="data-font text-sm">{daysBack === 0 ? "Live pulse" : `${daysBack}d rewind`}</span>
        </div>
      </div>

      <input
        aria-label="Time travel slider"
        className="range-track"
        type="range"
        min={0}
        max={30}
        step={1}
        value={daysBack}
        onChange={(event) => onChange(Number(event.target.value))}
      />

      <div className="mt-3 flex justify-between text-[11px] uppercase tracking-[0.22em] text-[var(--muted)]">
        {ticks.map((tick) => (
          <span key={tick}>{tick === 0 ? "Now" : `${tick}d`}</span>
        ))}
      </div>
    </section>
  );
}
