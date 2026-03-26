export type SituationReport = {
  main_event: string;
  regional_sentiment: number;
  situation_report: string[];
  country_code: string;
  country_name: string;
  updated_at: string;
  from_date: string;
  articles: Array<{
    title: string;
    source: string;
    url: string;
    published_at?: string | null;
  }>;
};
