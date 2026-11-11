"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";

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
  ["granny_square", "Cuadrado / granny square"],
  ["bag", "Bolso"],
  ["amigurumi", "Amigurumi"],
  ["other", "Pieza plana / otra"],
] as const;

const techniques = [
  ["needles", "Dos agujas"],
  ["circular", "Circular"],
  ["crochet", "Crochet"],
] as const;

const supportedTechniques: Record<string, readonly string[]> = {
  pullover: ["needles", "circular"],
  cardigan: ["needles", "circular"],
  vest: ["needles", "circular"],
  hat: ["needles", "circular"],
  scarf: ["needles", "circular", "crochet"],
  cowl: ["needles", "circular"],
  mittens: ["needles", "circular"],
  socks: ["needles", "circular"],
  shawl: ["needles", "circular"],
  blanket: ["needles", "circular", "crochet"],
  granny_square: ["crochet"],
  bag: ["needles", "circular", "crochet"],
  amigurumi: ["crochet"],
  other: ["needles", "circular", "crochet"],
  gloves: [],
};

const garmentConstructions = new Set([
  "raglan_top_down",
  "drop_shoulder",
  "set_in_sleeve",
  "yoke",
]);

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

const crochetStitches = [
  ["crochet_sc", "Punto bajo"],
  ["crochet_hdc", "Medio punto alto"],
  ["crochet_dc", "Punto alto"],
] as const;

const amigurumiShapes = [
  ["straight", "Esfera"],
  ["boxy", "Cilindro"],
  ["a_line", "Cono"],
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

type DimensionField = readonly [key: string, label: string, placeholder: string];

const garmentCategories = new Set(["pullover", "cardigan", "vest"]);

const dimensionFields: Record<string, readonly DimensionField[]> = {
  pullover: [
    ["bust", "Contorno de busto", "Ej. 100"],
    ["body_length", "Largo del cuerpo", "Ej. 58"],
    ["sleeve_length", "Largo de manga", "Ej. 58"],
  ],
  cardigan: [
    ["bust", "Contorno de busto", "Ej. 100"],
    ["body_length", "Largo del cuerpo", "Ej. 58"],
    ["sleeve_length", "Largo de manga", "Ej. 58"],
  ],
  vest: [
    ["bust", "Contorno de busto", "Ej. 100"],
    ["body_length", "Largo del cuerpo", "Ej. 58"],
  ],
  hat: [
    ["head", "Contorno de cabeza", "Ej. 56"],
    ["length", "Alto del gorro", "Ej. 22"],
  ],
  scarf: [
    ["width", "Ancho", "Ej. 25"],
    ["length", "Largo", "Ej. 180"],
  ],
  cowl: [
    ["circumference", "Contorno", "Ej. 60"],
    ["length", "Largo", "Ej. 30"],
  ],
  mittens: [
    ["palm", "Contorno de palma", "Ej. 20"],
    ["length", "Largo de mano", "Ej. 18"],
    ["thumb", "Largo de pulgar", "Ej. 6"],
  ],
  socks: [
    ["circumference", "Contorno", "Ej. 22"],
    ["foot_length", "Largo del pie", "Ej. 24"],
    ["leg", "Largo de pierna", "Ej. 10"],
  ],
  shawl: [
    ["width", "Ancho", "Ej. 60"],
    ["length", "Largo", "Ej. 180"],
  ],
  blanket: [
    ["width", "Ancho", "Ej. 100"],
    ["length", "Largo", "Ej. 120"],
  ],
  granny_square: [["size", "Lado del cuadrado", "Ej. 20"]],
  bag: [
    ["width", "Ancho", "Ej. 30"],
    ["length", "Alto", "Ej. 30"],
  ],
  other: [
    ["width", "Ancho", "Ej. 20"],
    ["length", "Alto", "Ej. 20"],
  ],
  amigurumi: [
    ["diameter", "Diámetro", "Ej. 8"],
    ["height", "Altura", "Ej. 8"],
  ],
};

const sectionLabels: Record<string, string> = {
  "section.body": "Cuerpo",
  "section.yoke": "Canesú",
  "section.sleeve": "Manga",
  "section.sleeve_left": "Manga izquierda",
  "section.sleeve_right": "Manga derecha",
  "section.neckband": "Cuello",
  "section.hem": "Borde inferior",
  "section.cuff": "Puño",
  "section.crown": "Corona",
  "section.brim": "Borde",
  "section.foot": "Pie",
  "section.toe": "Puntera",
  "section.thumb": "Pulgar",
  "section.hand": "Mano",
  "section.scarf": "Bufanda",
  "section.cowl": "Cuello circular",
  "section.shawl": "Chal",
  "section.blanket": "Manta",
  "section.front": "Delantero",
  "section.back": "Espalda",
  "section.left_front": "Delantero izquierdo",
  "section.right_front": "Delantero derecho",
  "section.button_band": "Tapa de botones",
  "section.amigurumi": "Amigurumi",
  "section.granny_square": "Granny square",
  "section.bag": "Bolso",
  "section.flat_piece": "Pieza plana",
  "section.leg": "Pierna",
  "section.sphere": "Esfera",
  "section.cylinder": "Cilindro",
  "section.cone": "Cono",
};

const noteLabels: Record<string, string> = {
  "pattern.note.cast_on_panel": "Montá los puntos y tejé en plano.",
  "pattern.note.cuff": "Puño en elástico.",
  "pattern.note.hat_crown": "Disminuí 4 puntos repartidos por vuelta.",
  "pattern.note.toe": "Disminuí 4 puntos repartidos por vuelta.",
  "pattern.note.flat_panel": "Tejé en jersey, de ida y vuelta.",
  "pattern.note.crochet_foundation": "Hacé la cadena inicial.",
  "pattern.note.crochet_flat": "Tejé en crochet, de ida y vuelta.",
  "pattern.note.amigurumi_increase": "Aumentá 6 puntos repartidos.",
  "pattern.note.amigurumi_decrease": "Disminuí 6 puntos repartidos.",
  "pattern.note.plain": "Vuelta sin aumentos.",
  "pattern.magic_ring": "Anillo mágico con 6 puntos bajos.",
  "pattern.note.mittens_hand": "Hacé 2 piezas iguales para las manos y coselas.",
  "pattern.note.mittens_thumb": "Hacé 2 piezas iguales para los pulgares y coselos.",
};

const measurementLabels: Record<string, string> = {
  bust: "Contorno de busto",
  body_length: "Largo del cuerpo",
  sleeve_length: "Largo de manga",
  upper_arm: "Contorno de brazo",
  neck: "Contorno de cuello",
  wrist: "Contorno de puño",
  yoke_depth: "Profundidad del canesú",
  hem: "Contorno de ruedo",
  diameter: "Diámetro",
  height: "Altura",
  width: "Ancho",
  length: "Largo",
  circumference: "Contorno",
  palm: "Contorno de palma",
  foot_length: "Largo del pie",
  head: "Contorno de cabeza",
  thumb: "Largo del pulgar",
};

const textureLabels: Record<string, string> = {
  cables: "Trenzas",
  lace: "Calados",
  bobbles: "Bodoques",
  honeycomb: "Nido de abeja",
  ribbing: "Elástico",
  cabled_ribbing: "Elástico con trenzas",
  other: "Otra textura",
};

const warningLabels: Record<string, string> = {
  "warning.gauge_sample": "Tejé una muestra antes de empezar.",
  "warning.estimated_yardage": "El metraje es una estimación con margen.",
  "warning.assumption": "Hay supuestos de construcción en este patrón.",
  "warning.no_short_rows": "No se usan vueltas cortas en este diseño.",
  "warning.unsupported_variant": "La variante pedida no está soportada por completo.",
  "warning.fast_increases": "Los aumentos van en todas las vueltas para que el canesú cierre.",
  "warning.unsupported_stitch": "El punto base se simplificó a jersey.",
  "warning.bag_flat": "El bolso es un panel rectangular simplificado; no incluye asas, forro ni cierre.",
  "warning.flat_piece": "No se reconoció la prenda; se genera una pieza plana rectangular. Revisá si corresponde a una categoría más específica.",
  "warning.mittens_flat": "Los mitones son piezas planas simplificadas; el pulgar se cose aparte y el calce debe probarse.",
};

const numberFormat = new Intl.NumberFormat("es-AR", {
  maximumFractionDigits: 1,
});

type SavedProject = {
  id: string;
  savedAt: string;
  label: string;
  size: string;
  yarnWeight: string;
  patternText: string;
  rowIndex: number;
  result: PatternResponse;
};

type WakeLockSentinelLike = {
  release: () => Promise<void>;
};

const STORAGE_KEY = "tejedora:projects:v1";

function formatCm(value: number): string {
  return `${numberFormat.format(value)} cm`;
}

function optionLabel(
  options: readonly (readonly [string, string])[],
  value: string | null,
): string {
  return options.find(([key]) => key === value)?.[1] ?? "Sin definir";
}

function normalizeSpec(spec: GarmentSpec): GarmentSpec {
  const allowed = supportedTechniques[spec.categoria] ?? [];
  const tecnica = allowed.includes(spec.tecnica)
    ? spec.tecnica
    : (allowed[0] ?? spec.tecnica);
  if (
    spec.categoria === "pullover" &&
    spec.construccion &&
    !garmentConstructions.has(spec.construccion)
  ) {
    return { ...spec, tecnica, construccion: "raglan_top_down" };
  }
  return { ...spec, tecnica };
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
  const [panelUnitCm, setPanelUnitCm] = useState("");
  const [gaugeRows, setGaugeRows] = useState("");
  const [ease, setEase] = useState("");
  const [customDimensions, setCustomDimensions] = useState<Record<string, string>>({});
  const [rowIndex, setRowIndex] = useState(0);
  const [savedProjects, setSavedProjects] = useState<SavedProject[]>([]);
  const [wakeLock, setWakeLock] = useState(false);
  const wakeLockRef = useRef<WakeLockSentinelLike | null>(null);

  const baseStitchOptions =
    spec?.tecnica === "crochet" ? crochetStitches : baseStitches;
  const isGarment = spec ? garmentCategories.has(spec.categoria) : false;
  const allowedTechniques = spec
    ? (supportedTechniques[spec.categoria] ?? [])
    : [];
  const techniqueOptions = techniques.filter(([key]) =>
    allowedTechniques.includes(key),
  );
  const unsupportedCategory =
    spec !== null && allowedTechniques.length === 0;

  const activeDimensionFields = useMemo<readonly DimensionField[]>(() => {
    if (!spec) return [];
    if (spec.categoria === "blanket" && spec.tecnica === "crochet") {
      return [["size", "Lado del módulo", "Ej. 15"]];
    }
    return dimensionFields[spec.categoria] ?? [];
  }, [spec]);

  const flatRows = useMemo(() => {
    if (!result) return [];
    return result.pattern.sections.flatMap((section) =>
      section.steps.map((step) => ({
        sectionId: section.id,
        sectionLabel: sectionLabels[section.name_key] ?? section.name_key,
        stepNumber: step.number,
        stitchCount: step.stitch_count_end,
        noteKey: step.note_key,
        sectionStepCount: section.steps.length,
      })),
    );
  }, [result]);

  const currentRow =
    flatRows.length > 0
      ? flatRows[Math.min(rowIndex, flatRows.length - 1)]
      : null;
  const currentSectionRows = currentRow
    ? flatRows.filter((row) => row.sectionId === currentRow.sectionId)
    : [];
  const currentSectionRowNumber = currentRow
    ? currentSectionRows.findIndex(
        (row) => row.stepNumber === currentRow.stepNumber,
      ) + 1
    : 0;

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        setSavedProjects(parsed as SavedProject[]);
      }
    } catch {
      setSavedProjects([]);
    }
  }, []);

  useEffect(() => {
    return () => {
      void wakeLockRef.current?.release();
    };
  }, []);

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
    setRowIndex(0);
    setStep("upload");
  }

  async function onAnalyze() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const data = await analyzeImage(file);
      setAnalysis(data);
      setSpec(normalizeSpec(data.spec));
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
    if (unsupportedCategory) {
      setError(
        "Esta categoría todavía no tiene una familia de patrón. Probá con otra categoría o con “Pieza plana”.",
      );
      return;
    }
    const currentSpec = normalizeSpec(spec);
    if (currentSpec !== spec) setSpec(currentSpec);
    const stitches = Number(gaugeStitches);
    const rows = Number(gaugeRows);
    const easeValue = Number(ease);
    const custom: Record<string, number> = {};
    for (const [key] of activeDimensionFields) {
      const raw = customDimensions[key]?.trim() ?? "";
      const value = Number(raw);
      if (raw !== "" && Number.isFinite(value) && value > 0) {
        custom[key] = value;
      }
    }
    const params = {
      talla: size,
      peso_hilo: yarnWeight,
      densidad:
        stitches > 0 && rows > 0
          ? { stitches_per_10cm: stitches, rows_per_10cm: rows }
          : null,
      ease_cm: ease.trim() !== "" && Number.isFinite(easeValue) ? easeValue : null,
      panel_motivo_cm:
        Number(panelUnitCm) > 0 && spec.texturas.length > 0 ? Number(panelUnitCm) : null,
      ...(Object.keys(custom).length > 0
        ? garmentCategories.has(spec.categoria)
          ? { medidas_cm: custom }
          : { dimensiones_cm: custom }
        : {}),
    };
    setBusy(true);
    setError(null);
    try {
      const data = await createPattern(currentSpec, params);
      setResult(data);
      setPatternText(data.text.es);
      setCritique(null);
      setRowIndex(0);
      setStep("pattern");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo generar el patrón.");
    } finally {
      setBusy(false);
    }
  }

  function saveProject() {
    if (!result) return;
    const project: SavedProject = {
      id: result.id,
      savedAt: new Date().toISOString(),
      label: optionLabel(categories, spec?.categoria ?? null),
      size,
      yarnWeight,
      patternText,
      rowIndex,
      result,
    };
    const next = [
      project,
      ...savedProjects.filter((item) => item.id !== project.id),
    ].slice(0, 12);
    setSavedProjects(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      setError("No se pudo guardar el proyecto en este dispositivo.");
    }
  }

  function loadProject(project: SavedProject) {
    setResult(project.result);
    setSpec(project.result.pattern.spec ?? null);
    setPatternText(project.patternText);
    setSize(project.size);
    setYarnWeight(project.yarnWeight);
    setRowIndex(project.rowIndex);
    setCritique(null);
    setImageId(null);
    setError(null);
    setStep("pattern");
  }

  function deleteProject(projectId: string) {
    const next = savedProjects.filter((item) => item.id !== projectId);
    setSavedProjects(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      setError("No se pudo actualizar la lista de proyectos.");
    }
  }

  async function toggleWakeLock() {
    if (wakeLockRef.current) {
      await wakeLockRef.current.release();
      wakeLockRef.current = null;
      setWakeLock(false);
      return;
    }
    const nav = navigator as Navigator & {
      wakeLock?: {
        request: (type: "screen") => Promise<WakeLockSentinelLike>;
      };
    };
    if (!nav.wakeLock) {
      setError("Este navegador no permite mantener la pantalla encendida.");
      return;
    }
    try {
      wakeLockRef.current = await nav.wakeLock.request("screen");
      setWakeLock(true);
    } catch {
      setError("No se pudo mantener la pantalla encendida.");
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

  function updateCategory(value: string) {
    setSpec((current) =>
      current ? normalizeSpec({ ...current, categoria: value }) : current,
    );
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
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-4 focus:py-2 focus:text-white"
      >
        Saltar al contenido
      </a>
      <main
        id="main"
        aria-busy={busy}
        className="mx-auto min-h-screen w-full max-w-3xl px-5 pb-16 pt-8 sm:px-8"
      >
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
            aria-current={step === key ? "step" : undefined}
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
      <p role="status" aria-live="polite" className="sr-only">
        {busy ? "Procesando, esperá un momento." : ""}
      </p>

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

          {savedProjects.length > 0 ? (
            <div className="mt-8 border-t border-ink/10 pt-6">
              <h3 className="text-lg font-semibold">Proyectos guardados</h3>
              <p className="mt-1 text-sm text-ink/60">
                Se guardan en este dispositivo. Podés retomar el contador donde
                lo dejaste.
              </p>
              <ul className="mt-3 space-y-2">
                {savedProjects.map((project) => (
                  <li
                    key={project.id}
                    className="flex flex-col gap-2 rounded-xl bg-paper/70 p-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <button
                      type="button"
                      onClick={() => loadProject(project)}
                      className="text-left font-semibold text-sage underline-offset-4 hover:underline"
                    >
                      {project.label}
                      {project.result.pattern.spec &&
                      garmentCategories.has(project.result.pattern.spec.categoria)
                        ? ` · ${project.size}`
                        : ""}
                      <span className="ml-2 text-xs font-normal text-ink/50">
                        {new Date(project.savedAt).toLocaleDateString("es-AR")}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteProject(project.id)}
                      className="self-start rounded-lg border border-ink/15 px-3 py-1 text-sm sm:self-auto"
                    >
                      Borrar
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
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
                onChange={updateCategory}
              />
              <Field
                label="Técnica"
                confidence={confidenceFor("tecnica")}
                value={spec.tecnica}
                options={techniqueOptions}
                onChange={(value) => updateNullable("tecnica", value)}
              />
              {spec.categoria === "pullover" ? (
                <Field
                  label="Construcción"
                  confidence={confidenceFor("construccion")}
                  value={spec.construccion ?? ""}
                  options={constructions}
                  onChange={(value) => updateNullable("construccion", value)}
                />
              ) : null}
              {isGarment ? (
                <>
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
                </>
              ) : null}
              <Field
                label="Punto base"
                confidence={confidenceFor("punto_base")}
                value={spec.punto_base ?? ""}
                options={baseStitchOptions}
                onChange={(value) => updateNullable("punto_base", value)}
              />
              {spec.categoria === "amigurumi" ? (
                <Field
                  label="Forma"
                  confidence={confidenceFor("forma")}
                  value={spec.forma ?? "straight"}
                  options={amigurumiShapes}
                  onChange={(value) => updateNullable("forma", value)}
                />
              ) : null}
            </div>

            {unsupportedCategory ? (
              <div className="mt-6 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-ink/75">
                <h3 className="font-semibold">Categoría todavía no disponible</h3>
                <p className="mt-1">
                  Esta categoría no tiene una familia de patrón todavía. Elegí
                  otra categoría compatible para continuar.
                </p>
              </div>
            ) : null}

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
              <p className="mt-4 text-sm text-ink/70">
                Texturas detectadas. En pulóveres se tejen como un panel en el cuerpo; quitá
                las que no estén en la prenda.
              </p>
            ) : null}
            {spec.texturas.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {spec.texturas.map((texture, index) => (
                  <span
                    key={`${texture.textura}-${texture.ubicacion ?? ""}-${index}`}
                    className="inline-flex items-center gap-2 rounded-full bg-sage/10 px-3 py-1 text-sm text-sage"
                  >
                    {textureLabels[texture.textura] ?? texture.textura}
                    {texture.ubicacion ? ` · ${texture.ubicacion}` : ""}
                    <button
                      type="button"
                      aria-label={`Quitar ${textureLabels[texture.textura] ?? texture.textura}`}
                      onClick={() =>
                        setSpec({
                          ...spec,
                          texturas: spec.texturas.filter((_, i) => i !== index),
                        })
                      }
                      className="rounded-full px-1 font-bold leading-none hover:bg-sage/20"
                    >
                      ×
                    </button>
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
              disabled={unsupportedCategory}
              className="min-h-12 flex-1 rounded-xl bg-sage px-5 py-3 text-lg font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              Confirmar y elegir medidas
            </button>
          </div>
        </section>
      ) : null}

      {step === "params" ? (
        <section className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
          <h2 className="text-2xl font-semibold">
            {isGarment ? "Tu hilo y tu talle" : "Tu hilo y tus medidas"}
          </h2>
          <p className="mt-2 text-ink/70">
            {isGarment
              ? "Con esto calculamos los puntos. Si ya tejiste una muestra, ingresá tu densidad real: es la opción más precisa."
              : "Este proyecto no se calcula por talle: usamos las medidas de abajo. Si ya tejiste una muestra, ingresá tu densidad real."}
          </p>

          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            {isGarment ? (
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
            ) : null}
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
            {spec && spec.texturas.length > 0 ? (
              <label className="mt-4 block">
                <span className="text-sm text-ink/70">
                  Ancho de una repetición del panel de textura en tu muestra (cm, opcional)
                </span>
                <input
                  type="number"
                  min="0.5"
                  max="30"
                  step="0.1"
                  value={panelUnitCm}
                  onChange={(event) => setPanelUnitCm(event.target.value)}
                  placeholder="Ej. 2.4"
                  className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                />
                <span className="mt-1 block text-xs text-ink/55">
                  Las trenzas cierran el tejido. Si medís una repetición del gráfico en tu muestra
                  lavada, compensamos el ancho para que la prenda mida lo de la tabla.
                </span>
              </label>
            ) : null}
          </fieldset>

          {activeDimensionFields.length > 0 ? (
            <fieldset className="mt-6 rounded-2xl border border-ink/10 bg-paper/60 p-4">
              <legend className="px-1 text-sm font-semibold">
                Medidas propias (opcional)
              </legend>
              <p className="mt-1 text-xs text-ink/55">
                {isGarment
                  ? "Si no las completás, usamos las medidas típicas del talle y de la categoría."
                  : "Si no las completás, usamos medidas típicas de la categoría."}
              </p>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                {activeDimensionFields.map(([key, label, placeholder]) => (
                  <label key={key} className="block">
                    <span className="text-sm text-ink/70">{label}</span>
                    <input
                      type="number"
                      min="0.5"
                      max="400"
                      step="0.5"
                      value={customDimensions[key] ?? ""}
                      onChange={(event) =>
                        setCustomDimensions((current) => ({
                          ...current,
                          [key]: event.target.value,
                        }))
                      }
                      placeholder={placeholder}
                      className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                    />
                  </label>
                ))}
              </div>
            </fieldset>
          ) : null}

          {isGarment ? (
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
          ) : null}

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
                {optionLabel(categories, spec?.categoria ?? null)}
                {isGarment ? ` · Talle ${size}` : ""}
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
              <button
                type="button"
                onClick={saveProject}
                className="min-h-12 rounded-xl border border-sage px-5 py-3 font-semibold text-sage"
              >
                Guardar proyecto
              </button>
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

          <div className="rounded-3xl border border-sage/30 bg-sage/5 p-5 shadow-sm sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-xl font-semibold">Modo tejiendo</h3>
                <p className="mt-1 text-sm text-ink/60">
                  Una vuelta a la vez. El contador no cambia los números del patrón.
                </p>
              </div>
              <button
                type="button"
                onClick={toggleWakeLock}
                aria-pressed={wakeLock}
                className="rounded-xl border border-sage px-4 py-2 text-sm font-semibold text-sage"
              >
                {wakeLock ? "Pantalla encendida" : "Mantener pantalla encendida"}
              </button>
            </div>
            {currentRow ? (
              <div
                className="mt-5 rounded-2xl bg-white/80 p-4"
                role="status"
                aria-live="polite"
              >
                <p className="text-sm font-semibold text-sage">
                  {currentRow.sectionLabel} · vuelta {currentSectionRowNumber} de{" "}
                  {currentRow.sectionStepCount}
                </p>
                <p className="mt-2 text-3xl font-bold">
                  {currentRow.stitchCount} puntos
                </p>
                <p className="mt-1 text-sm text-ink/60">
                  Vuelta {currentRow.stepNumber} del patrón
                  {currentRow.noteKey
                    ? ` · ${noteLabels[currentRow.noteKey] ?? currentRow.noteKey}`
                    : ""}
                </p>
              </div>
            ) : (
              <p className="mt-4 text-sm text-ink/60">Sin vueltas para mostrar.</p>
            )}
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setRowIndex((index) => Math.max(0, index - 1))}
                disabled={rowIndex <= 0}
                className="min-h-12 rounded-xl border border-ink/20 px-4 py-2 font-semibold disabled:opacity-40"
              >
                Vuelta anterior
              </button>
              <button
                type="button"
                onClick={() =>
                  setRowIndex((index) => Math.min(flatRows.length - 1, index + 1))
                }
                disabled={rowIndex >= flatRows.length - 1}
                className="min-h-12 rounded-xl bg-sage px-4 py-2 font-semibold text-white disabled:opacity-40"
              >
                Siguiente vuelta
              </button>
              <button
                type="button"
                onClick={() => setRowIndex(0)}
                className="min-h-12 rounded-xl border border-ink/20 px-4 py-2 font-semibold"
              >
                Reiniciar contador
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
                        {warning.message ?? warningLabels[warning.message_key] ?? warning.message_key}
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
              setRowIndex(0);
            }}
            className="min-h-12 w-full rounded-xl border border-ink/20 px-5 py-3 font-semibold"
          >
            Empezar con otra foto
          </button>
        </section>
      ) : null}
      </main>
    </>
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
