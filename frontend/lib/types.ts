export type Article = {
  title: string;
  source: string;
  provider: string;
  providers: string[];
  url: string;
  canonical_url?: string | null;
  snippet?: string | null;
  published_at?: string | null;
  matched_terms: string[];
  relevance_score: number;
  quality_score: number;
  freshness_score: number;
  headline_score: number;
  feed_score: number;
  is_preferred_source: boolean;
  confidence: string;
  category: string;
  cluster_id?: string | null;
  evidence_points: string[];
  entities: string[];
  source_trust_score: number;
  provider_performance_score: number;
  languages_considered: string[];
};

export type ProviderStatus = {
  provider: string;
  status: string;
  message: string;
  articles_returned: number;
  cache_hit: boolean;
  healthy: boolean;
  cooldown_until?: string | null;
  last_http_status?: number | null;
};

export type SummaryStatus = {
  status: string;
  message: string;
  used_ai: boolean;
  cache_hit: boolean;
};

export type PipelineStatus = {
  code: string;
  level: string;
  message: string;
};

export type CacheStatus = {
  article_cache_hit: boolean;
  summary_cache_hit: boolean;
};

export type StoryCluster = {
  cluster_id: string;
  label: string;
  article_count: number;
  representative_title: string;
  providers: string[];
  evidence_points: string[];
};

export type ProviderMetric = {
  provider: string;
  success_rate: number;
  average_articles: number;
  average_latency_ms: number;
  last_status: string;
};

export type HistoricalMetric = {
  timestamp: string;
  provider: string;
  latency_ms: number;
  articles_returned: number;
  status: string;
  country_code: string;
};

export type CountryQualitySnapshot = {
  country_code: string;
  country_name: string;
  avg_relevance: number;
  avg_freshness: number;
  usable_yield: number;
  provider_count: number;
  last_updated?: string | null;
};

export type ObservabilitySnapshot = {
  generated_at: string;
  provider_metrics: ProviderMetric[];
  ranked_article_count: number;
  cluster_count: number;
  historical_metrics: HistoricalMetric[];
  country_quality: CountryQualitySnapshot[];
  stale_cache_warnings: string[];
};

export type SituationReport = {
  main_event: string;
  regional_sentiment: number;
  situation_report: string[];
  country_code: string;
  country_name: string;
  updated_at: string;
  from_date: string;
  articles: Article[];
  headline_articles: Article[];
  provider_statuses: ProviderStatus[];
  summary_status: SummaryStatus;
  pipeline_status: PipelineStatus[];
  cache: CacheStatus;
  story_clusters: StoryCluster[];
  observability: ObservabilitySnapshot;
};

export type Country = {
  iso_a3: string;
  name: string;
  iso_a2: string;
};
