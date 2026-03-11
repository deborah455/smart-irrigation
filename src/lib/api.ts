export type RecommendPayload = {
  crop: string;
  region: "asal"|"coastal"|"highlands"|"western"|"rift";
  use_manual?: boolean;
  lat?: number|null;
  lon?: number|null;
  factors: Record<string, number|null>;
};

export async function postRecommendToday(payload: RecommendPayload) {
  const base = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
  const res = await fetch(`${base}/recommend/today`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(()=> "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}
