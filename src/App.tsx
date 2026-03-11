import { useMemo, useState } from "react";
import Hero from "./components/Hero";
import { CROP_FEATURES, REGION_TOGGLES, REGION_CENTROIDS, FARMER_FIELDS } from "./lib/constants";
import { postRecommendToday } from "./lib/api";
import { Droplets } from "lucide-react";

type RegionKey = keyof typeof REGION_TOGGLES;
function toAskFields(crop: string, region: RegionKey): string[] {
  const cfg = CROP_FEATURES[crop];
  if (!cfg) return ["days_since_last_irrig","area_m2"];
  const toggles = REGION_TOGGLES[region];
  const core = [...cfg.core]; const opt  = [...cfg.optional];
  if (toggles.use_leaf_wetness === 0) {
    const ix1 = core.indexOf("leaf_wetness"); if (ix1 >= 0) core.splice(ix1, 1);
    const ix2 = opt.indexOf("leaf_wetness");  if (ix2 >= 0) opt.splice(ix2, 1);
  }
  return Array.from(new Set([...core, ...opt, "days_since_last_irrig", "area_m2"]));
}
export default function App() {
  const [crop, setCrop] = useState<string>("maize");
  const [region, setRegion] = useState<RegionKey>("asal");
  const [useManual, setUseManual] = useState(false);
  const [lat, setLat] = useState<number | "">(""); const [lon, setLon] = useState<number | "">("");
  const fields = useMemo(() => toAskFields(crop, region), [crop, region]);
  const [values, setValues] = useState<Record<string, number | "">>({});
  useMemo(() => {
    const next: Record<string, number | ""> = { ...values };
    fields.forEach(f => { if (next[f] === undefined) next[f] = FARMER_FIELDS[f]?.default ?? ""; });
    setValues(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fields.join("|")]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>("");
  const centroid = REGION_CENTROIDS[region];

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault(); setLoading(true); setError(""); setResult(null);
    try {
      const payload = {
        crop, region, use_manual: useManual,
        lat: useManual ? (lat === "" ? null : Number(lat)) : null,
        lon: useManual ? (lon === "" ? null : Number(lon)) : null,
        factors: Object.fromEntries(fields.map(f => [f, values[f] === "" ? null : Number(values[f])]))
      };
      const data = await postRecommendToday(payload);
      setResult(data);
    } catch (err: any) { setError(err.message || String(err)); }
    finally { setLoading(false); }
  }
  function setField(name: string, val: string) { setValues(v => ({ ...v, [name]: val === "" ? "" : Number(val) })); }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <Hero />
      <main className="relative -mt-16 sm:-mt-20 md:-mt-24">
        <div className="max-w-5xl mx-auto px-4 grid gap-6">
          <form onSubmit={onSubmit} className="glass p-5 sm:p-6 grid gap-6">
            <div className="flex items-center gap-2 text-slate-700">
              <Droplets className="w-5 h-5 text-sky-500" />
              <h2 className="text-lg font-semibold">Get Today’s Recommendation</h2>
            </div>
            <section className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm mb-1">Crop</label>
                <select className="w-full border rounded-lg p-2 bg-white" value={crop} onChange={e => setCrop(e.target.value)}>
                  {Object.keys(CROP_FEATURES).sort().map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm mb-1">Region</label>
                <select className="w-full border rounded-lg p-2 bg-white" value={region} onChange={e => setRegion(e.target.value as RegionKey)}>
                  {Object.keys(REGION_TOGGLES).map(r => <option key={r} value={r}>{r}</option>)}
                </select>
                <p className="text-xs text-slate-500 mt-1">Default centroid: ({centroid.lat.toFixed(2)}, {centroid.lon.toFixed(2)})</p>
              </div>
            </section>
            <section className="grid gap-3">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={useManual} onChange={e => setUseManual(e.target.checked)} />
                Enter latitude/longitude manually
              </label>
              {useManual && (
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm mb-1">Latitude</label>
                    <input type="number" step="0.0001" className="w-full border rounded-lg p-2"
                      value={lat} onChange={e => setLat(e.target.value === "" ? "" : Number(e.target.value))}/>
                  </div>
                  <div>
                    <label className="block text-sm mb-1">Longitude</label>
                    <input type="number" step="0.0001" className="w-full border rounded-lg p-2"
                      value={lon} onChange={e => setLon(e.target.value === "" ? "" : Number(e.target.value))}/>
                  </div>
                </div>
              )}
            </section>
            <section>
              <h3 className="text-base font-semibold mb-3">Factors for <span className="text-emerald-700">{crop}</span> in <span className="text-sky-700">{region}</span></h3>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {toAskFields(crop, region).map((f) => {
                  const meta = FARMER_FIELDS[f];
                  if (!meta) return <div key={f} className="text-sm text-amber-700">Unknown field: {f}</div>;
                  return (
                    <div key={f} className="rounded-lg border bg-white p-3">
                      <label className="block text-sm mb-1">{meta.label}</label>
                      <input type="number" min={meta.min} max={meta.max} step={meta.step}
                        className="w-full border rounded-lg p-2"
                        value={values[f] ?? ""} onChange={e => setField(f, e.target.value)} />
                      <p className="text-[11px] text-slate-500 mt-1">Default: {meta.default}</p>
                    </div>
                  );
                })}
              </div>
            </section>
            <div className="flex items-center gap-3">
              <button type="submit" disabled={loading} className="btn-primary">
                {loading ? "Calculating..." : "Get Recommendation"}
              </button>
              <span className="text-xs text-slate-500">API: {import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000"}</span>
            </div>
          </form>
          {error && (
            <div className="glass p-4 text-red-800 bg-red-50/70 border-red-200">
              <strong>Error:</strong> {error}
            </div>
          )}
          {result && (
            <div className="grid md:grid-cols-3 gap-4">
              <div className="glass p-4">
                <h4 className="font-semibold mb-1">Decision</h4>
                <div className="text-2xl">{result.decision ?? result.need ?? result.irrigate ?? "—"}</div>
              </div>
              <div className="glass p-4">
                <h4 className="font-semibold mb-1">Amount (mm)</h4>
                <div className="text-2xl">{(result.amount_mm ?? result.mm ?? 0).toFixed?.(2) ?? result.amount_mm}</div>
              </div>
              <div className="glass p-4">
                <h4 className="font-semibold mb-1">Liters</h4>
                <div className="text-2xl">{(result.amount_l ?? result.liters ?? 0).toFixed?.(1) ?? result.amount_l}</div>
              </div>
              {result.weather && (
                <div className="md:col-span-3 glass p-4">
                  <h4 className="font-semibold mb-2">Weather Snapshot</h4>
                  <div className="grid sm:grid-cols-3 gap-2 text-sm">
                    <div>Tmin: {fmt(result.weather.t_min)} °C</div>
                    <div>Tmax: {fmt(result.weather.t_max)} °C</div>
                    <div>RH: {fmt(result.weather.rh)} %</div>
                    <div>Wind: {fmt(result.weather.wind_ms)} m/s</div>
                    <div>Solar: {fmt(result.weather.solar_mj)} MJ</div>
                    <div>Rain: {fmt(result.weather.rain_mm)} mm</div>
                  </div>
                </div>
              )}
              {result.debug && (
                <div className="md:col-span-3 glass p-4">
                  <details>
                    <summary className="cursor-pointer font-semibold">Debug details</summary>
                    <pre className="text-xs mt-2 overflow-auto">{JSON.stringify(result.debug, null, 2)}</pre>
                  </details>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
      <footer className="mt-10 pb-10 text-center text-xs text-slate-500">
        © {new Date().getFullYear()} Smart Irrigation (Kenya) — Demo UI
      </footer>
    </div>
  );
}
function fmt(v: any) { if (v === null || v === undefined) return "—"; const n = Number(v); return Number.isFinite(n) ? n.toFixed(1) : String(v); }
