export function LoadingPanel() {
  return (
    <div className="panel flex h-[560px] items-center justify-center p-8">
      <div className="space-y-4 text-center">
        <div className="mx-auto h-16 w-16 animate-pulse rounded-full bg-[rgba(61,123,120,0.22)] shadow-[var(--shadow-inner)]" />
        <p className="data-font text-sm uppercase tracking-[0.35em] text-[var(--muted)]">Booting command center</p>
      </div>
    </div>
  );
}
