"use client";

import { Suspense, lazy, useEffect, useMemo, useState, useTransition } from "react";
import { motion } from "framer-motion";
import { fetchSituationReport } from "@/lib/api";
import { SituationReport } from "@/lib/types";
import { NewsCard } from "./NewsCard";
import { LoadingPanel } from "./LoadingPanel";
import { TimeTravelSlider } from "./TimeTravelSlider";

const WorldMap = lazy(async () => import("./WorldMap").then((module) => ({ default: module.WorldMap })));

const initialDate = new Date().toISOString().slice(0, 10);

function buildFromDate(daysBack: number) {
  const date = new Date();
  date.setDate(date.getDate() - daysBack);
  return date.toISOString().slice(0, 10);
}

export function CommandCenter() {
  const [selectedCountryCode, setSelectedCountryCode] = useState("USA");
  const [selectedCountryName, setSelectedCountryName] = useState("United States");
  const [daysBack, setDaysBack] = useState(0);
  const [report, setReport] = useState<SituationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const fromDate = useMemo(() => buildFromDate(daysBack), [daysBack]);

  useEffect(() => {
    let cancelled = false;

    const loadReport = async () => {
      try {
        setError(null);
        const nextReport = await fetchSituationReport(selectedCountryCode, fromDate);

        if (!cancelled) {
          startTransition(() => {
            setReport(nextReport);
            setSelectedCountryName(nextReport.country_name);
          });
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "Unknown intelligence error");
        }
      }
    };

    void loadReport();

    return () => {
      cancelled = true;
    };
  }, [fromDate, selectedCountryCode]);

  const sentimentColor = report
    ? report.regional_sentiment >= 0.2
      ? "var(--positive)"
      : report.regional_sentiment <= -0.2
        ? "var(--negative)"
        : "var(--orange)"
    : "var(--teal)";

  return (
    <main className="paper-grid min-h-screen px-4 py-4 md:px-6 md:py-6">
      <div className="mx-auto grid max-w-[1600px] gap-5 lg:grid-cols-[1.4fr_0.85fr]">
        <section className="panel overflow-hidden p-4 md:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4 rounded-[28px] bg-[rgba(255,248,237,0.58)] px-5 py-4 shadow-[var(--shadow-inner)]">
            <div>
              <p className="data-font text-xs uppercase tracking-[0.34em] text-[var(--muted)]">Atlas.Intelligence</p>
              <h1 className="mt-1 text-3xl font-semibold md:text-4xl">Global Event Command Center</h1>
            </div>
            <div className="flex gap-3">
              <div className="rounded-full px-4 py-3 shadow-[var(--shadow-inner)]">
                <span className="data-font text-xs uppercase tracking-[0.24em]">Feed From {report?.from_date ?? initialDate}</span>
              </div>
              <div className="rounded-full px-4 py-3 shadow-[var(--shadow-inner)]">
                <span className="data-font text-xs uppercase tracking-[0.24em]">Updated {report?.updated_at ? new Date(report.updated_at).toLocaleTimeString() : "--:--"}</span>
              </div>
            </div>
          </div>

          <Suspense fallback={<LoadingPanel />}>
            <WorldMap
              selectedCountryCode={selectedCountryCode}
              sentimentColor={sentimentColor}
              onCountrySelect={(countryCode, countryName) => {
                setSelectedCountryCode(countryCode);
                setSelectedCountryName(countryName);
              }}
            />
          </Suspense>
        </section>

        <div className="grid gap-5">
          <section className="panel p-6">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <p className="data-font text-xs uppercase tracking-[0.32em] text-[var(--muted)]">Region Lock</p>
                <h2 className="mt-1 text-2xl font-semibold">{selectedCountryName}</h2>
              </div>
              <div
                className="rounded-full px-4 py-2 text-sm font-semibold shadow-[var(--shadow-inner)]"
                style={{ color: sentimentColor }}
              >
                Sentiment {report ? report.regional_sentiment.toFixed(2) : "--"}
              </div>
            </div>

            <div className="mb-5 rounded-[30px] border border-[rgba(23,49,58,0.07)] bg-[rgba(255,250,244,0.92)] p-5 shadow-[var(--shadow-inner)]">
              <p className="data-font text-xs uppercase tracking-[0.28em] text-[var(--muted)]">Main Event</p>
              <p className="mt-2 text-lg font-medium leading-7">{report?.main_event ?? "Select a region to generate a situation report."}</p>
            </div>

            <div className="space-y-3">
              {(report?.situation_report ?? ["Awaiting intelligence uplink.", "Vector tiles and AI summaries will render here.", "Historical sweep updates with the time-travel dial."]).map((bullet) => (
                <motion.div
                  key={bullet}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-[28px] bg-[rgba(255,248,237,0.9)] p-4 shadow-[var(--shadow-inner)]"
                >
                  <p className="text-sm leading-6">{bullet}</p>
                </motion.div>
              ))}
            </div>

            {error ? <p className="mt-4 text-sm text-[var(--negative)]">{error}</p> : null}
            {isPending ? <p className="mt-4 data-font text-xs uppercase tracking-[0.28em] text-[var(--muted)]">Refreshing intelligence...</p> : null}
          </section>

          <TimeTravelSlider daysBack={daysBack} onChange={setDaysBack} />

          <section className="panel p-6">
            <div className="mb-4">
              <p className="data-font text-xs uppercase tracking-[0.32em] text-[var(--muted)]">Local Sources</p>
              <h2 className="mt-1 text-xl font-semibold">Raw article signal</h2>
            </div>

            <div className="grid gap-3">
              {report?.articles?.length ? (
                report.articles.map((article) => (
                  <NewsCard
                    key={article.url}
                    title={article.title}
                    source={article.source}
                    url={article.url}
                    publishedAt={article.published_at}
                  />
                ))
              ) : (
                <div className="rounded-[28px] bg-[rgba(255,248,237,0.85)] p-5 shadow-[var(--shadow-inner)]">
                  <p className="text-sm leading-6">No article set yet. Select a country to trigger the news pipeline.</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
