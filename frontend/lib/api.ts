import { Country, SituationReport } from "./types";

const backendBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchCountries(): Promise<Country[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/countries`, {
    next: { revalidate: 3600 },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch supported countries list");
  }

  return response.json() as Promise<Country[]>;
}

export async function fetchSituationReport(countryCode: string): Promise<SituationReport> {
  const params = new URLSearchParams({ country_code: countryCode });

  const response = await fetch(`${backendBaseUrl}/api/v1/intelligence?${params.toString()}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    // Attempt to extract the detail message from FastAPI
    let errorMessage = `Failed to fetch intelligence for ${countryCode}`;
    try {
      const errorData = await response.json();
      if (errorData?.detail) {
        // Handle validation errors (array) or standard detail message (string)
        errorMessage = Array.isArray(errorData.detail)
          ? errorData.detail.map((e: any) => e.msg).join(", ")
          : errorData.detail;
      }
    } catch {
      // Ignored if response isn't JSON
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<SituationReport>;
}
