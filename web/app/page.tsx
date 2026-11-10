"use client";

import { useState, type ChangeEvent } from "react";

import {
  analyzeImage,
  createPattern,
  critiquePattern,
  patternPdfUrl,
  patternSvgUrl,
  rewritePattern,
  type AnalysisResponse,
  type CritiqueResponse,
  type GarmentSpec,
  type PatternResponse,
} from "@/lib/api";

type Step = "upload" | "confirm" | "params" | "pattern";

const categories = [
  ["pullover", "Pullover / suéter"],
  ["cardigan", "Cardigan"],
  ["vest", "Chaleco"],
  ["hat", "Gorro"],
  ["scarf", "Bufanda"],
  ["cowl", "Cuello"],
  ["mittens", "Mitones"],
  ["gloves", "Guantes"],
  ["socks", "Medias"],
  ["shawl", "Chal"],
  ["blanket", "Manta"],
  ["bag", "Bolso"],
  ["amigurumi", "Amigurumi"],
  ["other", "Otra prenda"],
] as const;

const techniques = [
  ["needles", "Dos agujas"],
  ["circular", "Circular"],
  ["crochet", "Crochet"],
  ["machine", "Máquina"],
] as const;

const constructions = [
  ["raglan_top_down", "Raglán de arriba hacia abajo"],
  ["drop_shoulder", "Hombro caído"],
  ["set_in_sleeve", "Manga encajada"],
  ["yoke", "Canesú circular"],
  ["bottom_up", "De abajo hacia arriba"],
  ["in_one_piece", "En una pieza"],
  ["flat_panels", "Piezas planas"],
  ["other", "Otra"],
] as const;

const necklines = [
  ["crew", "Redondo"],
  ["v_neck", "En V"],
  ["boat", "Barco"],
  ["turtleneck", "Cuello alto"],
  ["funnel", "Cuello embudo"],
  ["hood", "Capucha"],
  ["square", "Cuadrado"],
  ["none", "Sin escote definido"],
] as const;

const bodyLengths = [
  ["cropped", "Corto"],
  ["hip", "A la cadera"],
  ["tunic", "Túnica"],
  ["long", "Largo"],
] as const;

const sleeveLengths = [
  ["sleeveless", "Sin mangas"],
  ["short", "Manga corta"],
  ["three_quarter", "Tres cuartos"],
  ["long", "Manga larga"],
] as const;

const fits = [
  ["very_loose", "Muy holgado"],
  ["loose", "Holgado"],
  ["regular", "Regular"],
  ["fitted", "Entallado"],
] as const;

const baseStitches = [
  ["stockinette", "Jersey"],
  ["garter", "Musgo"],
  ["seed", "Arroz"],
  ["rib_1x1", "Elástico 1x1"],
  ["rib_2x2", "Elástico 2x2"],
  ["rib_3x1", "Elástico 3x1"],
  ["moss", "Punto musgo doble"],
  ["brioche", "Canalé inglés"],
  ["cables", "Trenzas"],
  ["lace", "Calados"],
  ["bobbles", "Bobos"],
  ["honeycomb", "Nido de abeja"],
] as const;

const yarnWeights = [
  ["lace", "Lace / hilo muy fino"],
  ["fingering", "Fingering"],
  ["sport", "Sport"],
  ["dk", "DK"],
  ["worsted", "Worsted"],
  ["bulky", "Bulky"],
  ["super_bulky", "Súper bulky"],
] as const;

const sizes = ["XS", "S", "M", "L", "XL", "2XL", "3XL"] as const;

const measurementLabels: Record<string, string> = {
  bust: "Contorno de busto",
  body_length: "Largo del cuerpo",
  sleeve_length: "Largo de manga",
  upper_arm: "Contorno de brazo",
  neck: "Contorno de cuello",
  wrist: "Contorno de puño",
  yoke_depth: "Profundidad del canesú",
  hem: "Contorno de ruedo",
};

const warningLabels: Record<string, string> = {
  "warning.gauge_sample": "Tejé una muestra antes de empezar.",
  "warning.estimated_yardage": "El metraje es una estimación con margen.",
  "warning.assumption": "Hay supuestos de construcción en este patrón.",
  "warning.no_short_rows": "No se usan vueltas cortas en este diseño.",
  "warning.unsupported_variant": "La variante pedida no está soportada por completo.",
  "warning.fast_increases": "Los aumentos van en todas las vueltas para que el canesú cierre.",
  "warning.unsupported_stitch": "El punto base se simplificó a jersey.",
};

const numberFormat = new Intl.NumberFormat("es-AR", {
  maximumFractionDigits: 1,
});

function formatCm(value: number): string {
  return `${numberFormat.format(value)} cm`;
}

function optionLabel(
  options: readonly (readonly [string, string])[],
  value: string | null,
): string {
  return options.find(([key]) => key === value)?.[1] ?? "Sin definir";
}

export default function HomePage() {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [spec, setSpec] = useState<GarmentSpec | null>(null);
  const [result, setResult] = useState<PatternResponse | null>(null);
  const [imageId, setImageId] = useState<string | null>(null);
  const [patternText, setPatternText] = useState("");
  const [critique, setCritique] = useState<CritiqueResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [size, setSize] = useState("M");
  const [yarnWeight, setYarnWeight] = useState("dk");
  const [gaugeStitches, setGaugeStitches] = useState("");
  const [gaugeRows, setGaugeRows] = useState("");
  const [ease, setEase] = useState("");

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0];
    if (!selected) return;
    if (preview) URL.revokeObjectURL(preview);
    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setAnalysis(null);
    setSpec(null);
    setResult(null);
    setImageId(null);
    setPatternText("");
    setCritique(null);
    setError(null);
    setStep("upload");
  }

  async function onAnalyze() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const data = await analyzeImage(file);
      setAnalysis(data);
      setSpec(data.spec);
      setImageId(data.image_id);
      setStep("confirm");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo analizar la foto.");
    } finally {
      setBusy(false);
    }
  }

  async function onGenerate() {
    if (!spec) return;
    const stitches = Number(gaugeStitches);
    const rows = Number(gaugeRows);
    const easeValue = Number(ease);
    setBusy(true);
    setError(null);
    try {
      const data = await createPattern(spec, {
        talla: size,
        peso_hilo: yarnWeight,
        densidad:
          stitches > 0 && rows > 0
            ? { stitches_per_10cm: stitches, rows_per_10cm: rows }
            : null,
        ease_cm: ease.trim() !== "" && Number.isFinite(easeValue) ? easeValue : null,
      });
      setResult(data);
      setPatternText(data.text.es);
      setCritique(null);
      setStep("pattern");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo generar el patrón.");
    } finally {
      setBusy(false);
    }
  }

  async function onRewrite() {
    if (!result) return;
    setBusy(true);
    setError(null);
    try {
      const data = await rewritePattern(result.id, "es");
      setPatternText(data.text);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo reescribir.");
    } finally {
      setBusy(false);
    }
  }

  async function onCritique() {
    if (!result || !imageId) return;
    setBusy(true);
    setError(null);
    try {
      setCritique(await critiquePattern(result.id, imageId, "es"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo revisar.");
    } finally {
      setBusy(false);
    }
  }

  function updateSpec<K extends keyof GarmentSpec>(key: K, value: GarmentSpec[K]) {
    setSpec((current) => (current ? { ...current, [key]: value } : current));
  }

  function updateNullable(key: keyof GarmentSpec, value: string) {
    setSpec((current) =>
      current ? ({ ...current, [key]: value === "" ? null : value } as GarmentSpec) : current,
    );
  }

  function confidenceFor(key: string): number | null {
    const value = analysis?.confidence[key] ?? spec?.confianza[key];
    return typeof value === "number" ? value : null;
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-5 pb-16 pt-8 sm:px-8">
      <header className="mb-8">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-sage">
          Tejedora
        </p>
        <h1 className="mt-2 text-4xl font-bold leading-tight sm:text-5xl">
          De la foto al patrón.
        </h1>
        <p className="mt-3 max-w-xl text-lg leading-relaxed text-ink/75">
          Subí una foto de una prenda tejida. La IA interpreta la imagen; el motor
          calcula y verifica cada número antes de mostrártelo.
        </p>
      </header>

      <nav aria-label="Pasos" className="mb-8 flex flex-wrap gap-2 text-sm">
        {[
          ["upload", "1. Foto"],
          ["confirm", "2. Confirmar"],
          ["params", "3. Medidas"],
          ["pattern", "4. Patrón"],
        ].map(([key, label]) => (
          <span
            key={key}
            className={`rounded-full border px-3 py-1 ${
              step === key
                ? "border-sage bg-sage text-white"
                : "border-ink/15 bg-white/60 text-ink/60"
            }`}
          >
            {label}
          </span>
        ))}
      </nav>

      {error ? (
        <div
          role="alert"
          className="mb-6 rounded-2xl border border-clay/40 bg-clay/10 p-4 text-base text-ink"
        >
          <strong className="block">No pudimos continuar</strong>
          <span className="mt-1 block break-words">{error}</span>
        </div>
      ) : null}

      {step === "upload" ? (
        <section className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
          <h2 className="text-2xl font-semibold">Empezá con una foto clara</h2>
          <p className="mt-2 text-ink/70">
            Se ve mejor la prenda completa, de frente, con buena luz. También podés
            usar una foto de Instagram o de tu galería.
          </p>
          <label className="mt-6 flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-sage/50 bg-sage/5 p-6 text-center hover:bg-sage/10">
            <span className="text-lg font-semibold text-sage">
              Elegir o sacar una foto
            </span>
            <span className="mt-1 text-sm text-ink/60">
              JPG, PNG o WebP · hasta 12 MB
            </span>
            <input
              type="file"
              accept="image/*"
              capture="environment"
              onChange={onFile}
              className="sr-only"
            />
          </label>

          {preview ? (
            <div className="mt-6 overflow-hidden rounded-2xl border border-ink/10 bg-ink/5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview}
                alt="Foto de la prenda elegida"
                className="max-h-96 w-full object-contain"
              />
            </div>
          ) : null}

          <button
            type="button"
            onClick={onAnalyze}
            disabled={!file || busy}
            className="mt-6 min-h-12 w-full rounded-xl bg-ink px-5 py-3 text-lg font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Analizando la foto…" : "Analizar foto"}
          </button>
        </section>
      ) : null}

      {step === "confirm" && spec ? (
        <section className="space-y-6">
          <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
            <h2 className="text-2xl font-semibold">Esto es lo que detecté</h2>
            <p className="mt-2 text-ink/70">
              Revisá y corregí lo que haga falta. La confianza baja está marcada en
              ámbar.
            </p>

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              <Field
                label="Categoría"
                confidence={confidenceFor("categoria")}
                value={spec.categoria}
                options={categories}
                onChange={(value) => updateNullable("categoria", value)}
              />
              <Field
                label="Técnica"
                confidence={confidenceFor("tecnica")}
                value={spec.tecnica}
                options={techniques}
                onChange={(value) => updateNullable("tecnica", value)}
              />
              <Field
                label="Construcción"
                confidence={confidenceFor("construccion")}
                value={spec.construccion ?? ""}
                options={constructions}
                onChange={(value) => updateNullable("construccion", value)}
              />
              <Field
                label="Escote"
                confidence={confidenceFor("escote")}
                value={spec.escote ?? ""}
                options={necklines}
                onChange={(value) => updateNullable("escote", value)}
              />
              <Field
                label="Largo del cuerpo"
                confidence={confidenceFor("largo_cuerpo")}
                value={spec.largo_cuerpo ?? ""}
                options={bodyLengths}
                onChange={(value) => updateNullable("largo_cuerpo", value)}
              />
              <Field
                label="Largo de manga"
                confidence={confidenceFor("largo_manga")}
                value={spec.largo_manga ?? ""}
                options={sleeveLengths}
                onChange={(value) => updateNullable("largo_manga", value)}
              />
              <Field
                label="Ajuste"
                confidence={confidenceFor("ajuste")}
                value={spec.ajuste ?? ""}
                options={fits}
                onChange={(value) => updateNullable("ajuste", value)}
              />
              <Field
                label="Punto base"
                confidence={confidenceFor("punto_base")}
                value={spec.punto_base ?? ""}
                options={baseStitches}
                onChange={(value) => updateNullable("punto_base", value)}
              />
            </div>

            {spec.incertidumbres.length > 0 || spec.no_visible.length > 0 ? (
              <div className="mt-6 rounded-2xl border border-amber-300 bg-amber-50 p-4">
                <h3 className="font-semibold">Lo que la foto no alcanza a mostrar</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink/75">
                  {[...spec.incertidumbres, ...spec.no_visible].map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {spec.texturas.length > 0 ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {spec.texturas.map((texture) => (
                  <span
                    key={`${texture.textura}-${texture.ubicacion ?? ""}`}
                    className="rounded-full bg-sage/10 px-3 py-1 text-sm text-sage"
                  >
                    {texture.textura}
                    {texture.ubicacion ? ` · ${texture.ubicacion}` : ""}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => setStep("upload")}
              className="min-h-12 rounded-xl border border-ink/20 px-5 py-3 font-semibold"
            >
              Cambiar foto
            </button>
            <button
              type="button"
              onClick={() => setStep("params")}
              className="min-h-12 flex-1 rounded-xl bg-sage px-5 py-3 text-lg font-semibold text-white"
            >
              Confirmar y elegir medidas
            </button>
          </div>
        </section>
      ) : null}

      {step === "params" ? (
        <section className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
          <h2 className="text-2xl font-semibold">Tu hilo y tu talle</h2>
          <p className="mt-2 text-ink/70">
            Con esto calculamos los puntos. Si ya tejiste una muestra, ingresá tu
            densidad real: es la opción más precisa.
          </p>

          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <label className="block">
              <span className="text-sm font-semibold">Talle</span>
              <select
                value={size}
                onChange={(event) => setSize(event.target.value)}
                className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
              >
                {sizes.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-semibold">Grosor del hilo</span>
              <select
                value={yarnWeight}
                onChange={(event) => setYarnWeight(event.target.value)}
                className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
              >
                {yarnWeights.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <fieldset className="mt-6 rounded-2xl border border-ink/10 bg-paper/60 p-4">
            <legend className="px-1 text-sm font-semibold">
              Muestra (opcional): puntos y vueltas en 10 cm
            </legend>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm text-ink/70">Puntos</span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  step="0.5"
                  value={gaugeStitches}
                  onChange={(event) => setGaugeStitches(event.target.value)}
                  placeholder="Ej. 22"
                  className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                />
              </label>
              <label className="block">
                <span className="text-sm text-ink/70">Vueltas</span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  step="0.5"
                  value={gaugeRows}
                  onChange={(event) => setGaugeRows(event.target.value)}
                  placeholder="Ej. 30"
                  className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                />
              </label>
            </div>
            <p className="mt-2 text-xs text-ink/55">
              Si los dejás vacíos, usamos una densidad típica para el grosor elegido.
            </p>
          </fieldset>

          <label className="mt-5 block">
            <span className="text-sm font-semibold">Holgura extra (opcional)</span>
            <input
              type="number"
              min="-10"
              max="40"
              step="0.5"
              value={ease}
              onChange={(event) => setEase(event.target.value)}
              placeholder="Ej. 8"
              className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
            />
            <span className="mt-1 block text-xs text-ink/55">
              En centímetros, además de la holgura del ajuste elegido.
            </span>
          </label>

          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => setStep("confirm")}
              className="min-h-12 rounded-xl border border-ink/20 px-5 py-3 font-semibold"
            >
              Volver
            </button>
            <button
              type="button"
              onClick={onGenerate}
              disabled={busy}
              className="min-h-12 flex-1 rounded-xl bg-ink px-5 py-3 text-lg font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? "Calculando y verificando…" : "Generar patrón"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "pattern" && result ? (
        <section className="space-y-6">
          <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-sage/15 px-3 py-1 text-sm font-semibold text-sage">
                Patrón verificado
              </span>
              <span className="text-sm text-ink/60">
                {optionLabel(categories, spec?.categoria ?? null)} · Talle {size}
              </span>
            </div>
            <h2 className="mt-4 text-3xl font-bold">Tu patrón está listo</h2>
            <p className="mt-2 text-ink/70">
              El simulador revisó los conteos, las uniones y las medidas. Igual,
              tejé una muestra antes de empezar.
            </p>

            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <a
                href={patternPdfUrl(result.id)}
                className="min-h-12 rounded-xl bg-clay px-5 py-3 text-center text-lg font-semibold text-white"
              >
                Descargar PDF
              </a>
              <a
                href={patternSvgUrl(result.id)}
                target="_blank"
                rel="noreferrer"
                className="min-h-12 rounded-xl border border-ink/20 px-5 py-3 text-center font-semibold"
              >
                Ver esquema SVG
              </a>
            </div>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={onRewrite}
                disabled={busy}
                className="min-h-12 rounded-xl border border-sage px-5 py-3 font-semibold text-sage disabled:opacity-40"
              >
                Mejorar redacción
              </button>
              <button
                type="button"
                onClick={onCritique}
                disabled={busy || !imageId}
                className="min-h-12 rounded-xl border border-ink/20 px-5 py-3 font-semibold disabled:opacity-40"
              >
                Revisar con IA
              </button>
            </div>
          </div>

          <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
            <h3 className="text-xl font-semibold">Medidas calculadas</h3>
            <dl className="mt-4 grid gap-3 sm:grid-cols-2">
              {result.pattern.measurements.map((measurement) => (
                <div
                  key={measurement.key}
                  className="rounded-xl bg-paper/70 px-4 py-3"
                >
                  <dt className="text-sm text-ink/60">
                    {measurementLabels[measurement.key] ?? measurement.key}
                  </dt>
                  <dd className="text-lg font-semibold">
                    {formatCm(measurement.value_cm)}
                    {measurement.target_cm != null ? (
                      <span className="ml-2 text-sm font-normal text-ink/50">
                        objetivo {formatCm(measurement.target_cm)}
                      </span>
                    ) : null}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="grid gap-6 sm:grid-cols-2">
            <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm">
              <h3 className="text-xl font-semibold">Materiales</h3>
              <ul className="mt-3 space-y-2 text-sm text-ink/75">
                <li>Hilo: {result.pattern.materials.yarn_weight}</li>
                <li>
                  Metraje estimado:{" "}
                  {numberFormat.format(result.pattern.materials.meters)} m
                  {result.pattern.materials.grams
                    ? ` (${numberFormat.format(result.pattern.materials.grams)} g)`
                    : ""}
                </li>
                {result.pattern.materials.needle_mm ? (
                  <li>Agujas: {result.pattern.materials.needle_mm} mm</li>
                ) : null}
                {result.pattern.materials.hook_mm ? (
                  <li>Ganchillo: {result.pattern.materials.hook_mm} mm</li>
                ) : null}
                {result.pattern.materials.notions.length > 0 ? (
                  <li>Otros: {result.pattern.materials.notions.join(", ")}</li>
                ) : null}
              </ul>
            </div>

            <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm">
              <h3 className="text-xl font-semibold">Advertencias</h3>
              {result.pattern.warnings.length === 0 ? (
                <p className="mt-3 text-sm text-ink/60">Sin advertencias.</p>
              ) : (
                <ul className="mt-3 space-y-2 text-sm text-ink/75">
                  {result.pattern.warnings.map((warning) => (
                    <li key={warning.code} className="flex gap-2">
                      <span aria-hidden="true">•</span>
                      <span>
                        {warningLabels[warning.message_key] ?? warning.message_key}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
            <h3 className="text-xl font-semibold">Instrucciones</h3>
            <p className="mt-1 text-sm text-ink/60">
              Texto generado desde los números ya verificados.
            </p>
            <pre className="mt-4 max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-2xl bg-paper/80 p-4 font-mono text-sm leading-relaxed">
              {patternText}
            </pre>
          </div>

          {critique ? (
            <div className="rounded-3xl border border-sage/30 bg-sage/5 p-5 shadow-sm sm:p-8">
              <h3 className="text-xl font-semibold">Revisión de la IA</h3>
              <p className="mt-1 text-sm text-ink/60">
                Observaciones informativas: no cambian el patrón.
              </p>
              <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-ink/75">
                {[...critique.observations, ...critique.risks].map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <button
            type="button"
            onClick={() => {
              setStep("upload");
              setFile(null);
              setPreview(null);
              setAnalysis(null);
              setSpec(null);
              setResult(null);
              setImageId(null);
              setPatternText("");
              setCritique(null);
              setError(null);
            }}
            className="min-h-12 w-full rounded-xl border border-ink/20 px-5 py-3 font-semibold"
          >
            Empezar con otra foto
          </button>
        </section>
      ) : null}
    </main>
  );
}

function Field({
  label,
  value,
  options,
  confidence,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly (readonly [string, string])[];
  confidence: number | null;
  onChange: (value: string) => void;
}) {
  const uncertain = confidence != null && confidence < 0.6;
  return (
    <label className="block">
      <span className="flex items-center justify-between gap-2 text-sm font-semibold">
        {label}
        {confidence != null ? (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              uncertain ? "bg-amber-100 text-amber-800" : "bg-sage/10 text-sage"
            }`}
          >
            {Math.round(confidence * 100)}%
          </span>
        ) : null}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
      >
        <option value="">Sin definir</option>
        {options.map(([key, option]) => (
          <option key={key} value={key}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
