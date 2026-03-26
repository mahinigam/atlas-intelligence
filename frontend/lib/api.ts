import { SituationReport } from "./types";

const backendBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchSituationReport(countryCode: string, fromDate: string): Promise<SituationReport> {
  const params = new URLSearchParams({
    country_code: countryCode,
    from_date: fromDate,
  });

  const response = await fetch(`${backendBaseUrl}/api/v1/intelligence?${params.toString()}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch intelligence for ${countryCode}`);
  }

  return response.json() as Promise<SituationReport>;
}
