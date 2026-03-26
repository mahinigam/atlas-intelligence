"use client";

import { Suspense, lazy, useEffect, useEffectEvent, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { fetchSituationReport } from "@/lib/api";
import { SituationReport } from "@/lib/types";
import { NewsCard } from "./NewsCard";
import { LoadingPanel } from "./LoadingPanel";
import { SentimentGauge } from "./SentimentGauge";
import { StatusBar } from "./StatusBar";
import { TimeTravelSlider } from "./TimeTravelSlider";
import { Radio } from "lucide-react";

// Lazy load map to keep initial client bundle tight
const WorldMap = lazy(async () => import("./WorldMap").then((m) => ({ default: m.WorldMap })));

function buildFromDate(daysBack: number) {
  const date = new Date();
  date.setDate(date.getDate() - daysBack);
  return date.toISOString().slice(0, 10);
}

export function CommandCenter() {
  const [selectedCountryCode, setSelectedCountryCode] = useState("IND");
  const [selectedCountryName, setSelectedCountryName] = useState("India");
  const [report, setReport] = useState<Partial<SituationReport> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [daysBack, setDaysBack] = useState(3);

  const fromDate = buildFromDate(daysBack);
  const handleCountrySelect = useEffectEvent((code: string, name: string) => {
    setSelectedCountryCode((currentCode) => (currentCode === code ? currentCode : code));
    setSelectedCountryName((currentName) => (currentName === name ? currentName : name));
  });

  useEffect(() => {
    let cancelled = false;

    setIsLoading(true);
    setReport(null);
    setError(null);

    void fetchSituationReport(selectedCountryCode, fromDate)
      .then((data) => {
        if (cancelled) {
          return;
        }
        setReport(data);
        setIsLoading(false);
      })
      .catch((err: Error) => {
        if (cancelled) {
          return;
        }
        setError(err.message);
        setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [fromDate, selectedCountryCode]);

  // Derived sentiment coloring for UI accents (must be Hex for WebGL MapLibre)
  const sentimentScore = report?.regional_sentiment ?? 0;
  const sentimentColor =
    sentimentScore >= 0.2
      ? "#218c68" // positive
      : sentimentScore <= -0.2
        ? "#b84136" // negative
        : "#e57c30"; // orange

  return (
    <>
      <main className="paper-grid min-h-screen px-4 pb-16 pt-4 md:px-6 md:pb-20 md:pt-6">
        <div className="mx-auto grid max-w-[1600px] gap-6 lg:grid-cols-[1.4fr_1fr]">
          
          {/* LEFT COLUMN: Map & Controls */}
          <div className="flex flex-col gap-6">
            <section className="panel flex-1 p-3 md:p-5">
              <div className="mb-4 flex flex-col md:flex-row md:items-center justify-between gap-4 rounded-3xl bg-[rgba(255,248,237,0.4)] px-5 py-4 border border-[rgba(23,49,58,0.04)] shadow-[var(--shadow-inner)]">
                <div>
                  <p className="data-font text-[10px] md:text-xs font-bold uppercase tracking-[0.38em] text-[var(--teal-soft)]">
                    Atlas // Core
                  </p>
                  <h1 className="mt-1 flex items-center gap-3 text-2xl font-bold tracking-tight text-[var(--text)] md:text-3xl">
                    <Radio className="text-[var(--teal)]" />
                    Global Command Center
                  </h1>
                </div>
                <div className="flex flex-wrap gap-2">
                  <div className="clay-btn hidden sm:block whitespace-nowrap rounded-full px-4 py-2">
                    <span className="data-font text-xs font-semibold text-[var(--text-soft)] uppercase tracking-[0.24em]">
                      Uplink: Active
                    </span>
                  </div>
                </div>
              </div>

              <Suspense fallback={<LoadingPanel />}>
                <WorldMap
                  selectedCountryCode={selectedCountryCode}
                  sentimentColor={sentimentColor}
                  onCountrySelect={handleCountrySelect}
                />
              </Suspense>
            </section>

            <TimeTravelSlider daysBack={daysBack} onChange={setDaysBack} />
          </div>

          {/* RIGHT COLUMN: Intelligence Streams */}
          <div className="flex flex-col gap-6">
            
            {/* Situation Report Panel */}
            <section className="panel flex-1 p-5 md:p-7">
              <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-[rgba(23,49,58,0.06)] pb-4">
                <div>
                  <p className="data-font text-[10px] sm:text-xs font-bold uppercase tracking-[0.32em] text-[var(--orange)]">
                    Region Lock
                  </p>
                  <h2 className="mt-1 text-2xl font-bold tracking-tight text-[var(--text)] md:text-3xl">
                    {selectedCountryName}
                  </h2>
                </div>
                
                {/* Visual Gauge */}
                <div className="flex-shrink-0">
                  <SentimentGauge score={report?.regional_sentiment ?? 0} />
                </div>
              </div>

              <div className="relative">
                {isLoading && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center rounded-[28px] bg-[rgba(255,248,237,0.7)] backdrop-blur-sm">
                    <span className="data-font animate-pulse text-xs font-bold uppercase tracking-widest text-[var(--teal)]">
                      Decrypting Stream...
                    </span>
                  </div>
                )}
                
                <AnimatePresence mode="popLayout">
                  <motion.div
                    key={`${selectedCountryCode}-${fromDate}`}
                    initial={{ opacity: 0, scale: 0.98, filter: "blur(4px)" }}
                    animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                    exit={{ opacity: 0, scale: 0.98, filter: "blur(4px)" }}
                    transition={{ duration: 0.3 }}
                  >
                    {/* Main Event Headline */}
                    <div 
                      className="mb-6 rounded-[28px] border-2 bg-[rgba(255,250,244,0.92)] p-5 shadow-[var(--shadow-inner)] transition-colors duration-500"
                      style={{ borderColor: `color-mix(in srgb, ${sentimentColor} 20%, transparent)` }}
                    >
                      <p className="data-font text-[10px] font-bold uppercase tracking-[0.28em] text-[var(--teal-soft)]">
                        Dominant Event
                      </p>
                      <p className="mt-2 text-lg font-bold leading-relaxed tracking-tight text-[var(--text)]">
                        {report?.main_event ?? (isLoading ? "Processing Intelligence..." : "Awaiting initial intelligence stream...")}
                      </p>
                    </div>

                    {/* Situation Bullets or Streaming Text */}
                    <div className="space-y-3">
                      {(report?.situation_report ?? [
                        "Country boundary map loaded. Atlas interface standing by.",
                        "Select a region to trigger the event summarization pipeline.",
                      ]).map((bullet, idx) => (
                        <motion.div
                          key={idx}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: idx * 0.1 + 0.2 }}
                          className="clay-card rounded-[24px] px-5 py-3"
                        >
                          <div className="flex gap-4">
                            <span className="data-font mt-1 shrink-0 text-xs font-bold text-[var(--orange)]">
                              0{idx + 1}
                            </span>
                            <p className="text-[14px] font-medium leading-[1.6] text-[var(--text)]">
                              {bullet}
                            </p>
                          </div>
                        </motion.div>
                      ))}
                    </div>

                    {!!report?.pipeline_status?.length && (
                      <div className="mt-6 grid gap-3">
                        {report.pipeline_status.map((status) => (
                          <div
                            key={status.code}
                            className="rounded-2xl border border-[rgba(23,49,58,0.08)] bg-[rgba(255,255,255,0.45)] px-4 py-3"
                          >
                            <p className="data-font text-[10px] font-bold uppercase tracking-[0.22em] text-[var(--teal-soft)]">
                              {status.code.replaceAll("_", " ")}
                            </p>
                            <p className="mt-1 text-sm leading-relaxed text-[var(--text-soft)]">
                              {status.message}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {!!report?.story_clusters?.length && (
                      <div className="mt-6 rounded-[28px] border border-[rgba(23,49,58,0.08)] bg-[rgba(255,255,255,0.45)] p-5">
                        <p className="data-font text-[10px] font-bold uppercase tracking-[0.28em] text-[var(--teal-soft)]">
                          Story Clusters
                        </p>
                        <div className="mt-4 grid gap-3">
                          {report.story_clusters.slice(0, 4).map((cluster) => (
                            <div key={cluster.cluster_id} className="rounded-2xl border border-[rgba(23,49,58,0.06)] px-4 py-3">
                              <p className="text-sm font-semibold text-[var(--text)]">{cluster.representative_title}</p>
                              <p className="mt-1 text-[12px] text-[var(--muted)]">
                                {cluster.article_count} reports • {cluster.providers.join(" + ")}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {error && (
                    <motion.div 
                      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                      className="mt-6 rounded-2xl bg-[var(--negative)]/10 px-4 py-3 border border-[var(--negative)]/20"
                    >
                        <p className="data-font text-xs font-bold uppercase tracking-widest text-[var(--negative)]">
                          Error: {error}
                        </p>
                      </motion.div>
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>
            </section>

            {/* Raw Feed Panel */}
            <section className="panel flex-1 p-5 md:p-7">
              <div className="mb-6">
                <p className="data-font text-[10px] sm:text-xs font-bold uppercase tracking-[0.32em] text-[var(--teal-soft)]">
                  Signal Intercept
                </p>
                <h2 className="mt-1 text-xl font-bold tracking-tight text-[var(--text)]">
                  Raw News Feed
                </h2>
              </div>

              <div className="grid gap-4">
                <AnimatePresence mode="popLayout">
                  {report?.articles?.length ? (
                    report.articles.map((article, idx) => (
                      <NewsCard
                        key={article.url + idx}
                        index={idx}
                        title={article.title}
                        source={article.source}
                        provider={article.provider}
                        providers={article.providers}
                        url={article.url}
                        snippet={article.snippet}
                        publishedAt={article.published_at}
                        isPreferredSource={article.is_preferred_source}
                        confidence={article.confidence}
                        category={article.category}
                        evidencePoints={article.evidence_points}
                      />
                    ))
                  ) : (
                    <motion.div 
                      key="empty"
                      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                      className="clay-card flex items-center justify-center p-8 text-center"
                    >
                      <p className="text-sm font-medium leading-relaxed text-[var(--text-soft)]">
                        No telemetry established.<br/>
                        Awaiting global sector selection.
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </section>

          </div>
        </div>
      </main>
      
      {/* Global Status Footer */}
      <StatusBar
        countryCode={selectedCountryCode}
        providerStatuses={report?.provider_statuses}
        summaryStatus={report?.summary_status ?? null}
        pipelineStatus={report?.pipeline_status}
        articleCacheHit={report?.cache?.article_cache_hit}
        summaryCacheHit={report?.cache?.summary_cache_hit}
      />
    </>
  );
}
