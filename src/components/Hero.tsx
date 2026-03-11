import { Smartphone, Sprout, Droplets } from "lucide-react";
export default function Hero() {
  return (
    <section
      className="relative h-[320px] sm:h-[420px] md:h-[500px] w-full bg-center bg-cover"
      style={{ backgroundImage: "url('/hero.jpg')" }}
      aria-label="Hero banner"
    >
      <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/30 to-black/60" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(59,130,246,0.35),transparent_60%),radial-gradient(ellipse_at_bottom_left,rgba(16,185,129,0.35),transparent_55%)]" />
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="spray left-10 bottom-10 hidden sm:block" />
        <div className="spray right-10 bottom-16 hidden md:block delay-300" />
      </div>
      <div className="relative h-full flex items-end">
        <div className="max-w-4xl mx-auto w-full px-4 pb-6 sm:pb-8 md:pb-10 text-white">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/15 backdrop-blur px-3 py-1 text-xs">
            <Droplets className="w-4 h-4" /> Smart Irrigation • Kenya
          </div>
          <h1 className="mt-3 text-3xl sm:text-4xl md:text-5xl font-semibold leading-tight">
            Precise irrigation, <span className="text-emerald-300">for every crop</span> and{" "}
            <span className="text-sky-300">every region</span>
          </h1>
          <p className="mt-2 text-sm sm:text-base text-white/90 max-w-2xl">
            Region-aware, crop-aware recommendations you can trust. Works even with low bandwidth and minimal inputs.
          </p>
          <div className="mt-4 flex items-center gap-3 text-sm">
            <span className="inline-flex items-center gap-2 rounded-lg bg-emerald-400/90 text-emerald-950 px-3 py-1.5">
              <Sprout className="w-4 h-4" /> 25+ crops
            </span>
            <span className="inline-flex items-center gap-2 rounded-lg bg-sky-400/90 text-sky-950 px-3 py-1.5">
              <Smartphone className="w-4 h-4" /> USSD/SMS ready
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
