"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";

import {
  analyzeImage,
  createPattern,
  critiquePattern,
  fetchPatternText,
  LANGUAGES,
  patternPdfUrl,
  patternSvgUrl,
  rewritePattern,
  type AnalysisResponse,
  type CritiqueResponse,
  type GarmentSpec,
  type Language,
  type PatternResponse,
} from "@/lib/api";
import { I18nProvider, LOCALES, UI_LANGUAGES, useT, type TKey } from "@/lib/i18n";

type Step = "upload" | "confirm" | "params" | "pattern";

// [valor de la API, clave de texto en web/lib/i18n.ts]
type Options = readonly (readonly [string, TKey])[];

const categories: Options = [
  ["pullover", "cat.pullover"],
  ["cardigan", "cat.cardigan"],
  ["vest", "cat.vest"],
  ["hat", "cat.hat"],
  ["scarf", "cat.scarf"],
  ["cowl", "cat.cowl"],
  ["mittens", "cat.mittens"],
  ["gloves", "cat.gloves"],
  ["socks", "cat.socks"],
  ["shawl", "cat.shawl"],
  ["blanket", "cat.blanket"],
  ["granny_square", "cat.granny_square"],
  ["bag", "cat.bag"],
  ["amigurumi", "cat.amigurumi"],
  ["other", "cat.other"],
];

const techniques: Options = [
  ["needles", "tech.needles"],
  ["circular", "tech.circular"],
  ["crochet", "tech.crochet"],
  ["machine", "tech.machine"],
];

// Toda categoria acepta toda tecnica: el servidor elige la familia mas
// cercana y lo avisa en las advertencias del patron (engine/garments/routing.py).
const supportedTechniques: Record<string, readonly string[]> = {};

const constructions: Options = [
  ["raglan_top_down", "cons.raglan_top_down"],
  ["drop_shoulder", "cons.drop_shoulder"],
  ["set_in_sleeve", "cons.set_in_sleeve"],
  ["yoke", "cons.yoke"],
  ["bottom_up", "cons.bottom_up"],
  ["in_one_piece", "cons.in_one_piece"],
  ["flat_panels", "cons.flat_panels"],
  ["round_tube", "cons.round_tube"],
  ["modules", "cons.modules"],
  ["other", "cons.other"],
];

const necklines: Options = [
  ["crew", "neck.crew"],
  ["v_neck", "neck.v_neck"],
  ["boat", "neck.boat"],
  ["turtleneck", "neck.turtleneck"],
  ["funnel", "neck.funnel"],
  ["hood", "neck.hood"],
  ["square", "neck.square"],
  ["none", "neck.none"],
];

const bodyLengths: Options = [
  ["cropped", "blen.cropped"],
  ["hip", "blen.hip"],
  ["tunic", "blen.tunic"],
  ["long", "blen.long"],
];

const sleeveLengths: Options = [
  ["sleeveless", "slen.sleeveless"],
  ["short", "slen.short"],
  ["three_quarter", "slen.three_quarter"],
  ["long", "slen.long"],
];

const fits: Options = [
  ["very_loose", "fit.very_loose"],
  ["loose", "fit.loose"],
  ["regular", "fit.regular"],
  ["fitted", "fit.fitted"],
];

const crochetStitches: Options = [
  ["crochet_sc", "cst.crochet_sc"],
  ["crochet_hdc", "cst.crochet_hdc"],
  ["crochet_dc", "cst.crochet_dc"],
];

const toyFigures: Options = [
  ["generic", "fig.generic"],
  ["bear", "fig.bear"],
  ["bunny", "fig.bunny"],
  ["cat", "fig.cat"],
];

const toyBodies: Options = [
  ["pieces", "toybody.pieces"],
  ["ball", "toybody.ball"],
];

const baseStitches: Options = [
  ["stockinette", "st.stockinette"],
  ["garter", "st.garter"],
  ["seed", "st.seed"],
  ["rib_1x1", "st.rib_1x1"],
  ["rib_2x2", "st.rib_2x2"],
  ["rib_3x1", "st.rib_3x1"],
  ["moss", "st.moss"],
  ["brioche", "st.brioche"],
  ["cables", "st.cables"],
  ["lace", "st.lace"],
  ["bobbles", "st.bobbles"],
  ["honeycomb", "st.honeycomb"],
];

const yarnWeights: Options = [
  ["lace", "yarn.lace"],
  ["fingering", "yarn.fingering"],
  ["sport", "yarn.sport"],
  ["dk", "yarn.dk"],
  ["worsted", "yarn.worsted"],
  ["bulky", "yarn.bulky"],
  ["super_bulky", "yarn.super_bulky"],
];

const sizes = ["XS", "S", "M", "L", "XL", "2XL", "3XL"] as const;

type DimensionField = readonly [key: string, label: TKey, placeholder: string];

const garmentCategories = new Set(["pullover", "cardigan", "vest"]);

const dimensionFields: Record<string, readonly DimensionField[]> = {
  pullover: [
    ["bust", "m.bust", "100"],
    ["body_length", "m.body_length", "58"],
    ["sleeve_length", "m.sleeve_length", "58"],
  ],
  cardigan: [
    ["bust", "m.bust", "100"],
    ["body_length", "m.body_length", "58"],
    ["sleeve_length", "m.sleeve_length", "58"],
  ],
  vest: [
    ["bust", "m.bust", "100"],
    ["body_length", "m.body_length", "58"],
  ],
  hat: [
    ["head", "m.head", "56"],
    ["length", "dim.hat_height", "22"],
  ],
  scarf: [
    ["width", "m.width", "25"],
    ["length", "m.length", "180"],
  ],
  cowl: [
    ["circumference", "m.circumference", "60"],
    ["length", "m.length", "30"],
  ],
  mittens: [
    ["palm", "m.palm", "20"],
    ["length", "dim.hand_length", "18"],
    ["thumb", "m.thumb", "6"],
  ],
  socks: [
    ["circumference", "m.circumference", "22"],
    ["foot_length", "m.foot_length", "24"],
    ["leg", "dim.leg_length", "10"],
  ],
  shawl: [
    ["width", "m.width", "60"],
    ["length", "m.length", "180"],
  ],
  blanket: [
    ["width", "m.width", "100"],
    ["length", "m.length", "120"],
  ],
  granny_square: [["size", "dim.square_side", "20"]],
  bag: [
    ["width", "m.width", "30"],
    ["length", "dim.height", "30"],
  ],
  other: [
    ["width", "m.width", "20"],
    ["length", "dim.height", "20"],
  ],
  amigurumi: [["height", "dim.toy_height", "22"]],
};

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

function optionKey(options: Options, value: string | null): TKey {
  return options.find(([key]) => key === value)?.[1] ?? "field.undefined";
}

function normalizeSpec(spec: GarmentSpec): GarmentSpec {
  return spec;
}

const MAX_PHOTOS = 4;

export default function HomePage() {
  return (
    <I18nProvider>
      <PatternApp />
    </I18nProvider>
  );
}

function PatternApp() {
  const { t, tx, lang, setLang } = useT();
  const [step, setStep] = useState<Step>("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [spec, setSpec] = useState<GarmentSpec | null>(null);
  const [result, setResult] = useState<PatternResponse | null>(null);
  const [imageId, setImageId] = useState<string | null>(null);
  const [imageIds, setImageIds] = useState<string[]>([]);
  // Opciones del PDF: se eligen en el ultimo paso, sin volver atras.
  // Por defecto sigue al idioma de la interfaz (ver efecto mas abajo).
  const [patternLang, setPatternLang] = useState<Language>(lang);
  const [designer, setDesigner] = useState("");
  const [coverPhotos, setCoverPhotos] = useState<number[]>([]);
  const [includeGuide, setIncludeGuide] = useState(true);
  const [paper, setPaper] = useState<"A4" | "Letter">("A4");
  const [patternText, setPatternText] = useState("");
  const [critique, setCritique] = useState<CritiqueResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [description, setDescription] = useState("");
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

  // Sin patron generado, el idioma del PDF acompana al de la interfaz.
  useEffect(() => {
    if (!result) setPatternLang(lang);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const numberFormat = useMemo(
    () => new Intl.NumberFormat(LOCALES[lang], { maximumFractionDigits: 1 }),
    [lang],
  );
  const formatCm = (value: number) => `${numberFormat.format(value)} cm`;
  const tr = (options: Options) =>
    options.map(([key, labelKey]) => [key, t(labelKey)] as const);
  const errorText = (caught: unknown, fallback: TKey) =>
    caught instanceof Error ? tx(caught.message) : t(fallback);

  const baseStitchOptions =
    spec?.tecnica === "crochet" ? crochetStitches : baseStitches;
  const isGarment = spec ? garmentCategories.has(spec.categoria) : false;
  const allowedTechniques = spec
    ? (supportedTechniques[spec.categoria] ?? techniques.map(([key]) => key))
    : [];
  const techniqueOptions = techniques.filter(([key]) =>
    allowedTechniques.includes(key),
  );
  const unsupportedCategory =
    spec !== null && allowedTechniques.length === 0;

  const activeDimensionFields = useMemo<readonly DimensionField[]>(() => {
    if (!spec) return [];
    if (spec.motivo && spec.tecnica === "crochet") {
      return [
        [
          "size",
          spec.motivo.forma === "square" ? "dim.motif_side" : "dim.motif_diameter",
          "20",
        ],
      ];
    }
    if (spec.categoria === "blanket" && spec.tecnica === "crochet") {
      return [["size", "dim.module_side", "15"]];
    }
    return dimensionFields[spec.categoria] ?? [];
  }, [spec]);

  const flatRows = useMemo(() => {
    if (!result) return [];
    return result.pattern.sections.flatMap((section) =>
      section.steps.map((step) => ({
        sectionId: section.id,
        sectionKey: section.name_key,
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
    const selected = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (selected.length === 0) return;
    // Se suman a las ya elegidas (hasta 4 fotos de la misma pieza).
    const next = [...files, ...selected].slice(0, MAX_PHOTOS);
    previews.forEach((url) => URL.revokeObjectURL(url));
    setFiles(next);
    setPreviews(next.map((item) => URL.createObjectURL(item)));
    setAnalysis(null);
    setSpec(null);
    setResult(null);
    setImageId(null);
    setImageIds([]);
    setPatternText("");
    setCritique(null);
    setError(null);
    setRowIndex(0);
    setStep("upload");
  }

  function removePhoto(index: number) {
    URL.revokeObjectURL(previews[index]);
    setFiles(files.filter((_, i) => i !== index));
    setPreviews(previews.filter((_, i) => i !== index));
  }

  async function onAnalyze() {
    if (files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const data = await analyzeImage(files, { descripcion: description.trim() });
      setAnalysis(data);
      setSpec(normalizeSpec(data.spec));
      // El grosor que se ve en la foto es mejor default que uno fijo.
      const seen = data.spec.hilo_aparente?.grosor_estimado;
      setYarnWeight(yarnWeights.some(([value]) => value === seen) ? (seen as string) : "dk");
      setImageId(data.image_id);
      const ids = data.image_ids ?? [data.image_id];
      setImageIds(ids);
      setCoverPhotos(ids.map((_, index) => index));
      setStep("confirm");
    } catch (caught) {
      setError(errorText(caught, "err.analyze"));
    } finally {
      setBusy(false);
    }
  }

  async function onGenerate(overrides: { talla?: string; peso_hilo?: string } = {}) {
    if (!spec) return;
    if (unsupportedCategory) {
      setError(t("err.unsupported_category"));
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
      talla: overrides.talla ?? size,
      peso_hilo: overrides.peso_hilo ?? yarnWeight,
      idioma: patternLang,
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
      setPatternText(data.text[patternLang] ?? data.text.es);
      setCritique(null);
      setRowIndex(0);
      setStep("pattern");
    } catch (caught) {
      setError(errorText(caught, "err.generate"));
    } finally {
      setBusy(false);
    }
  }

  function saveProject() {
    if (!result) return;
    const project: SavedProject = {
      id: result.id,
      savedAt: new Date().toISOString(),
      label: t(optionKey(categories, spec?.categoria ?? null)),
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
      setError(t("err.save"));
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
      setError(t("err.update_list"));
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
      setError(t("err.wake_unsupported"));
      return;
    }
    try {
      wakeLockRef.current = await nav.wakeLock.request("screen");
      setWakeLock(true);
    } catch {
      setError(t("err.wake_failed"));
    }
  }

  async function changeLanguage(lang: Language) {
    setPatternLang(lang);
    if (!result) return;
    setBusy(true);
    setError(null);
    try {
      setPatternText(await fetchPatternText(result.id, lang));
    } catch (caught) {
      setError(errorText(caught, "err.change_language"));
    } finally {
      setBusy(false);
    }
  }

  // Cambiar talle o hilo en el ultimo paso recalcula y verifica al instante.
  function adjust(key: "talla" | "peso_hilo", value: string) {
    if (key === "talla") setSize(value);
    else setYarnWeight(value);
    void onGenerate({ [key]: value });
  }

  async function onRewrite() {
    if (!result) return;
    setBusy(true);
    setError(null);
    try {
      const data = await rewritePattern(result.id, patternLang);
      setPatternText(data.text);
    } catch (caught) {
      setError(errorText(caught, "err.rewrite"));
    } finally {
      setBusy(false);
    }
  }

  async function onCritique() {
    if (!result || !imageId) return;
    setBusy(true);
    setError(null);
    try {
      setCritique(await critiquePattern(result.id, imageId, patternLang));
    } catch (caught) {
      setError(errorText(caught, "err.critique"));
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

  const qualityNotes = (analysis?.photo_quality ?? [])
    .filter((item) => item.issues.length > 0)
    .map(
      (item) =>
        t("quality.photo", {
          n: item.photo,
          issues: item.issues.map((code) => tx(`q.${code}`, code)).join(t("quality.and")),
        }),
    );

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
        {t("app.skip")}
      </a>
      <main
        id="main"
        aria-busy={busy}
        className="mx-auto min-h-screen w-full max-w-3xl px-5 pb-16 pt-8 sm:px-8"
      >
      <header className="mb-8">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-sage">
            {t("app.brand")}
          </p>
          <select
            value={lang}
            onChange={(event) => setLang(event.target.value as Language)}
            aria-label={t("app.language")}
            className="rounded-lg border border-ink/15 bg-white/70 px-2 py-1 text-sm"
          >
            {UI_LANGUAGES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <h1 className="mt-2 text-4xl font-bold leading-tight sm:text-5xl">
          {t("hero.title")}
        </h1>
        <p className="mt-3 max-w-xl text-lg leading-relaxed text-ink/75">
          {t("hero.lead")}
        </p>
      </header>

      <nav aria-label={t("steps.aria")} className="mb-8 flex flex-wrap gap-2 text-sm">
        {(
          [
            ["upload", t("steps.upload")],
            ["confirm", t("steps.confirm")],
            ["params", t("steps.params")],
            ["pattern", t("steps.pattern")],
          ] as const
        ).map(([key, label]) => (
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
          <strong className="block">{t("error.title")}</strong>
          <span className="mt-1 block break-words">{error}</span>
        </div>
      ) : null}
      <p role="status" aria-live="polite" className="sr-only">
        {busy ? t("status.busy") : ""}
      </p>

      {step === "upload" ? (
        <section className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
          <h2 className="text-2xl font-semibold">{t("upload.title")}</h2>
          <p className="mt-2 text-ink/70">{t("upload.lead", { max: MAX_PHOTOS })}</p>
          <label className="mt-6 flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-sage/50 bg-sage/5 p-6 text-center hover:bg-sage/10">
            <span className="text-lg font-semibold text-sage">
              {files.length > 0 ? t("upload.add_more") : t("upload.choose")}
            </span>
            <span className="mt-1 text-sm text-ink/60">
              {t("upload.formats")}
            </span>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={onFile}
              className="sr-only"
            />
          </label>

          {previews.length > 0 ? (
            <div className="mt-6 grid grid-cols-2 gap-3">
              {previews.map((url, index) => (
                <div
                  key={url}
                  className="relative overflow-hidden rounded-2xl border border-ink/10 bg-ink/5"
                >
                  <img
                    src={url}
                    alt={t("upload.photo_alt", { n: index + 1 })}
                    className="max-h-60 w-full object-contain"
                  />
                  <button
                    type="button"
                    onClick={() => removePhoto(index)}
                    aria-label={t("upload.remove_photo", { n: index + 1 })}
                    className="absolute right-2 top-2 min-h-9 min-w-9 rounded-full bg-white/90 text-lg font-semibold text-ink shadow"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          <label className="mt-6 block rounded-2xl border border-ink/10 bg-paper/60 p-4">
            <span className="text-sm font-semibold">{t("upload.describe_label")}</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={600}
              rows={3}
              placeholder={t("upload.describe_placeholder")}
              className="mt-2 w-full rounded-xl border border-ink/20 bg-white px-3 py-2 text-base"
            />
            <span className="mt-1 block text-xs text-ink/55">
              {t("upload.describe_hint")}
            </span>
          </label>

          <button
            type="button"
            onClick={onAnalyze}
            disabled={files.length === 0 || busy}
            className="mt-6 min-h-12 w-full rounded-xl bg-ink px-5 py-3 text-lg font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? t("upload.analyzing") : t("upload.analyze")}
          </button>

          {savedProjects.length > 0 ? (
            <div className="mt-8 border-t border-ink/10 pt-6">
              <h3 className="text-lg font-semibold">{t("saved.title")}</h3>
              <p className="mt-1 text-sm text-ink/60">{t("saved.lead")}</p>
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
                      {project.result.pattern.spec
                        ? t(optionKey(categories, project.result.pattern.spec.categoria))
                        : project.label}
                      {project.result.pattern.spec &&
                      garmentCategories.has(project.result.pattern.spec.categoria)
                        ? ` · ${project.size}`
                        : ""}
                      <span className="ml-2 text-xs font-normal text-ink/50">
                        {new Date(project.savedAt).toLocaleDateString(LOCALES[lang])}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteProject(project.id)}
                      className="self-start rounded-lg border border-ink/15 px-3 py-1 text-sm sm:self-auto"
                    >
                      {t("saved.delete")}
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
            <h2 className="text-2xl font-semibold">{t("confirm.title")}</h2>
            <p className="mt-2 text-ink/70">{t("confirm.lead")}</p>
            {spec.motivo && spec.tecnica === "crochet" ? (
              <p className="mt-3 rounded-xl bg-sage/10 p-3 text-sm text-ink/80">
                {t(
                  spec.motivo.forma === "square" ? "confirm.motif_square" : "confirm.motif_round",
                  { bands: spec.motivo.bandas.length, symmetry: spec.motivo.simetria },
                )}
              </p>
            ) : null}
            {qualityNotes.length > 0 ? (
              <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-ink/80">
                {qualityNotes.join(" ")} {t("confirm.quality_more")}
              </p>
            ) : null}

            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              <Field
                label={t("field.category")}
                confidence={confidenceFor("categoria")}
                value={spec.categoria}
                options={tr(categories)}
                onChange={updateCategory}
              />
              <Field
                label={t("field.technique")}
                confidence={confidenceFor("tecnica")}
                value={spec.tecnica}
                options={tr(techniqueOptions)}
                onChange={(value) => updateNullable("tecnica", value)}
              />
              {spec.categoria === "pullover" ? (
                <Field
                  label={t("field.construction")}
                  confidence={confidenceFor("construccion")}
                  value={spec.construccion ?? ""}
                  options={tr(constructions)}
                  onChange={(value) => updateNullable("construccion", value)}
                />
              ) : null}
              {isGarment ? (
                <>
                  <Field
                    label={t("field.neckline")}
                    confidence={confidenceFor("escote")}
                    value={spec.escote ?? ""}
                    options={tr(necklines)}
                    onChange={(value) => updateNullable("escote", value)}
                  />
                  <Field
                    label={t("field.body_length")}
                    confidence={confidenceFor("largo_cuerpo")}
                    value={spec.largo_cuerpo ?? ""}
                    options={tr(bodyLengths)}
                    onChange={(value) => updateNullable("largo_cuerpo", value)}
                  />
                  <Field
                    label={t("field.sleeve_length")}
                    confidence={confidenceFor("largo_manga")}
                    value={spec.largo_manga ?? ""}
                    options={tr(sleeveLengths)}
                    onChange={(value) => updateNullable("largo_manga", value)}
                  />
                  <Field
                    label={t("field.fit")}
                    confidence={confidenceFor("ajuste")}
                    value={spec.ajuste ?? ""}
                    options={tr(fits)}
                    onChange={(value) => updateNullable("ajuste", value)}
                  />
                </>
              ) : null}
              <Field
                label={t("field.base_stitch")}
                confidence={confidenceFor("punto_base")}
                value={spec.punto_base ?? ""}
                options={tr(baseStitchOptions)}
                onChange={(value) => updateNullable("punto_base", value)}
              />
              {spec.categoria === "amigurumi" ? (
                <Field
                  label={t("field.figure")}
                  confidence={confidenceFor("figura")}
                  value={spec.figura ?? "generic"}
                  options={tr(toyFigures)}
                  onChange={(value) => updateNullable("figura", value)}
                />
              ) : null}
              {spec.categoria === "amigurumi" ? (
                <Field
                  label={t("field.toy_body")}
                  confidence={confidenceFor("cuerpo_juguete")}
                  value={spec.cuerpo_juguete ?? "pieces"}
                  options={tr(toyBodies)}
                  onChange={(value) => updateNullable("cuerpo_juguete", value)}
                />
              ) : null}
            </div>

            {unsupportedCategory ? (
              <div className="mt-6 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-ink/75">
                <h3 className="font-semibold">{t("unsupported.title")}</h3>
                <p className="mt-1">{t("unsupported.body")}</p>
              </div>
            ) : null}

            {spec.incertidumbres.length > 0 || spec.no_visible.length > 0 ? (
              <div className="mt-6 rounded-2xl border border-amber-300 bg-amber-50 p-4">
                <h3 className="font-semibold">{t("uncertain.title")}</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink/75">
                  {[...spec.incertidumbres, ...spec.no_visible].map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {spec.texturas.length > 0 ? (
              <p className="mt-4 text-sm text-ink/70">
                {t("textures.hint")}
              </p>
            ) : null}
            {spec.texturas.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {spec.texturas.map((texture, index) => (
                  <span
                    key={`${texture.textura}-${texture.ubicacion ?? ""}-${index}`}
                    className="inline-flex items-center gap-2 rounded-full bg-sage/10 px-3 py-1 text-sm text-sage"
                  >
                    {tx(`tex.${texture.textura}`, texture.textura)}
                    {texture.ubicacion ? ` · ${texture.ubicacion}` : ""}
                    <button
                      type="button"
                      aria-label={t("texture.remove", {
                        name: tx(`tex.${texture.textura}`, texture.textura),
                      })}
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
              {t("confirm.change_photo")}
            </button>
            <button
              type="button"
              onClick={() => setStep("params")}
              disabled={unsupportedCategory}
              className="min-h-12 flex-1 rounded-xl bg-sage px-5 py-3 text-lg font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              {t("confirm.next")}
            </button>
          </div>
        </section>
      ) : null}

      {step === "params" ? (
        <section className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
          <h2 className="text-2xl font-semibold">
            {isGarment ? t("params.title_garment") : t("params.title_other")}
          </h2>
          <p className="mt-2 text-ink/70">
            {isGarment
              ? t("params.lead_garment")
              : t("params.lead_other")}
          </p>

          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            {isGarment ? (
              <label className="block">
                <span className="text-sm font-semibold">{t("params.size")}</span>
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
              <span className="text-sm font-semibold">{t("params.yarn")}</span>
              <select
                value={yarnWeight}
                onChange={(event) => setYarnWeight(event.target.value)}
                className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
              >
                {yarnWeights.map(([value, label]) => (
                  <option key={value} value={value}>
                    {t(label)}
                  </option>
                ))}
              </select>
              {spec?.hilo_aparente?.grosor_estimado === yarnWeight ? (
                <span className="mt-1 block text-xs text-ink/55">
                  {t("params.yarn_estimated")}
                </span>
              ) : null}
            </label>
          </div>

          <fieldset className="mt-6 rounded-2xl border border-ink/10 bg-paper/60 p-4">
            <legend className="px-1 text-sm font-semibold">
              {t("gauge.legend")}
            </legend>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm text-ink/70">{t("gauge.stitches")}</span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  step="0.5"
                  value={gaugeStitches}
                  onChange={(event) => setGaugeStitches(event.target.value)}
                  placeholder={t("common.eg", { value: 22 })}
                  className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                />
              </label>
              <label className="block">
                <span className="text-sm text-ink/70">{t("gauge.rows")}</span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  step="0.5"
                  value={gaugeRows}
                  onChange={(event) => setGaugeRows(event.target.value)}
                  placeholder={t("common.eg", { value: 30 })}
                  className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                />
              </label>
            </div>
            <p className="mt-2 text-xs text-ink/55">
              {t("gauge.hint")}
            </p>
            {spec && spec.texturas.length > 0 ? (
              <label className="mt-4 block">
                <span className="text-sm text-ink/70">
                  {t("panel.label")}
                </span>
                <input
                  type="number"
                  min="0.5"
                  max="30"
                  step="0.1"
                  value={panelUnitCm}
                  onChange={(event) => setPanelUnitCm(event.target.value)}
                  placeholder={t("common.eg", { value: numberFormat.format(2.4) })}
                  className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                />
                <span className="mt-1 block text-xs text-ink/55">
                  {t("panel.hint")}
                </span>
              </label>
            ) : null}
          </fieldset>

          {activeDimensionFields.length > 0 ? (
            <fieldset className="mt-6 rounded-2xl border border-ink/10 bg-paper/60 p-4">
              <legend className="px-1 text-sm font-semibold">
                {t("dims.legend")}
              </legend>
              <p className="mt-1 text-xs text-ink/55">
                {isGarment
                  ? t("dims.hint_garment")
                  : spec?.motivo && spec.tecnica === "crochet"
                    ? t("dims.hint_motif")
                    : t("dims.hint_other")}
              </p>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                {activeDimensionFields.map(([key, label, placeholder]) => (
                  <label key={key} className="block">
                    <span className="text-sm text-ink/70">{t(label)}</span>
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
                      placeholder={t("common.eg", { value: placeholder })}
                      className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                    />
                  </label>
                ))}
              </div>
            </fieldset>
          ) : null}

          {isGarment ? (
            <label className="mt-5 block">
              <span className="text-sm font-semibold">{t("ease.label")}</span>
              <input
                type="number"
                min="-10"
                max="40"
                step="0.5"
                value={ease}
                onChange={(event) => setEase(event.target.value)}
                placeholder={t("common.eg", { value: 8 })}
                className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
              />
              <span className="mt-1 block text-xs text-ink/55">
                {t("ease.hint")}
              </span>
            </label>
          ) : null}

          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => setStep("confirm")}
              className="min-h-12 rounded-xl border border-ink/20 px-5 py-3 font-semibold"
            >
              {t("common.back")}
            </button>
            <button
              type="button"
              onClick={() => void onGenerate()}
              disabled={busy}
              className="min-h-12 flex-1 rounded-xl bg-ink px-5 py-3 text-lg font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? t("params.generating") : t("params.generate")}
            </button>
          </div>
        </section>
      ) : null}

      {step === "pattern" && result ? (
        <section className="space-y-6">
          <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-sage/15 px-3 py-1 text-sm font-semibold text-sage">
                {t("pattern.verified")}
              </span>
              <span className="text-sm text-ink/60">
                {t(optionKey(categories, spec?.categoria ?? null))}
                {isGarment ? ` · ${t("pattern.size", { size })}` : ""}
              </span>
            </div>
            <h2 className="mt-4 text-3xl font-bold">{t("pattern.ready")}</h2>
            <p className="mt-2 text-ink/70">{t("pattern.lead")}</p>

            <fieldset className="mt-6 rounded-2xl border border-ink/10 bg-paper/60 p-4">
              <legend className="px-1 text-sm font-semibold">{t("pdf.legend")}</legend>
              <div className="mt-2 grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="text-sm text-ink/70">{t("pdf.lang")}</span>
                  <select
                    value={patternLang}
                    onChange={(event) => void changeLanguage(event.target.value as Language)}
                    disabled={busy}
                    className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                  >
                    {LANGUAGES.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                {isGarment ? (
                  <label className="block">
                    <span className="text-sm text-ink/70">{t("pdf.size")}</span>
                    <select
                      value={size}
                      onChange={(event) => adjust("talla", event.target.value)}
                      disabled={busy}
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
                  <span className="text-sm text-ink/70">{t("params.yarn")}</span>
                  <select
                    value={yarnWeight}
                    onChange={(event) => adjust("peso_hilo", event.target.value)}
                    disabled={busy}
                    className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                  >
                    {yarnWeights.map(([value, label]) => (
                      <option key={value} value={value}>
                        {t(label)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-sm text-ink/70">{t("pdf.designer")}</span>
                  <input
                    value={designer}
                    maxLength={80}
                    onChange={(event) => setDesigner(event.target.value)}
                    placeholder={t("pdf.designer_placeholder")}
                    className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                  />
                </label>
                <label className="block">
                  <span className="text-sm text-ink/70">{t("pdf.paper")}</span>
                  <select
                    value={paper}
                    onChange={(event) => setPaper(event.target.value as "A4" | "Letter")}
                    className="mt-1 min-h-12 w-full rounded-xl border border-ink/20 bg-white px-3"
                  >
                    <option value="A4">A4</option>
                    <option value="Letter">{t("pdf.letter")}</option>
                  </select>
                </label>
              </div>
              <label className="mt-4 flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={includeGuide}
                  onChange={(event) => setIncludeGuide(event.target.checked)}
                  className="mt-1 h-5 w-5"
                />
                <span className="text-sm">
                  {t("pdf.guide")}
                  <span className="block text-xs text-ink/55">{t("pdf.guide_hint")}</span>
                </span>
              </label>
              {imageIds.length > 0 && previews.length === imageIds.length ? (
                <div className="mt-4">
                  <span className="text-sm text-ink/70">{t("pdf.cover")}</span>
                  <div className="mt-2 flex flex-wrap gap-3">
                    {previews.map((url, index) => {
                      const chosen = coverPhotos.includes(index);
                      return (
                        <button
                          key={url}
                          type="button"
                          aria-pressed={chosen}
                          onClick={() =>
                            setCoverPhotos(
                              chosen
                                ? coverPhotos.filter((item) => item !== index)
                                : [...coverPhotos, index].sort((a, b) => a - b),
                            )
                          }
                          className={`relative overflow-hidden rounded-xl border-2 ${chosen ? "border-clay" : "border-transparent opacity-40"}`}
                        >
                          <img src={url} alt={t("pdf.photo_alt", { n: index + 1 })} className="h-20 w-20 object-cover" />
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}
              <p className="mt-3 text-xs text-ink/55">
                {t("pdf.recalc_before")}{" "}
                <button type="button" onClick={() => setStep("params")} className="underline">
                  {t("pdf.recalc_link")}
                </button>
                {t("pdf.recalc_after")}
              </p>
            </fieldset>

            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <a
                href={patternPdfUrl(result.id, {
                  photos: coverPhotos.map((index) => imageIds[index]).filter(Boolean),
                  lang: patternLang,
                  designer,
                  guide: includeGuide,
                  paper,
                })}
                className="min-h-12 rounded-xl bg-clay px-5 py-3 text-center text-lg font-semibold text-white"
              >
                {t("actions.download_pdf")}
              </a>
              <a
                href={patternSvgUrl(result.id)}
                target="_blank"
                rel="noreferrer"
                className="min-h-12 rounded-xl border border-ink/20 px-5 py-3 text-center font-semibold"
              >
                {t("actions.view_svg")}
              </a>
              <button
                type="button"
                onClick={saveProject}
                className="min-h-12 rounded-xl border border-sage px-5 py-3 font-semibold text-sage"
              >
                {t("actions.save")}
              </button>
            </div>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={onRewrite}
                disabled={busy}
                className="min-h-12 rounded-xl border border-sage px-5 py-3 font-semibold text-sage disabled:opacity-40"
              >
                {t("actions.rewrite")}
              </button>
              <button
                type="button"
                onClick={onCritique}
                disabled={busy || !imageId}
                className="min-h-12 rounded-xl border border-ink/20 px-5 py-3 font-semibold disabled:opacity-40"
              >
                {t("actions.critique")}
              </button>
            </div>
          </div>

          <div className="rounded-3xl border border-sage/30 bg-sage/5 p-5 shadow-sm sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-xl font-semibold">{t("knit.title")}</h3>
                <p className="mt-1 text-sm text-ink/60">{t("knit.lead")}</p>
              </div>
              <button
                type="button"
                onClick={toggleWakeLock}
                aria-pressed={wakeLock}
                className="rounded-xl border border-sage px-4 py-2 text-sm font-semibold text-sage"
              >
                {wakeLock ? t("knit.wake_on") : t("knit.wake_off")}
              </button>
            </div>
            {currentRow ? (
              <div
                className="mt-5 rounded-2xl bg-white/80 p-4"
                role="status"
                aria-live="polite"
              >
                <p className="text-sm font-semibold text-sage">
                  {t("knit.row_of", {
                    section: tx(currentRow.sectionKey),
                    n: currentSectionRowNumber,
                    total: currentRow.sectionStepCount,
                  })}
                </p>
                <p className="mt-2 text-3xl font-bold">
                  {t("knit.stitches", { n: currentRow.stitchCount })}
                </p>
                <p className="mt-1 text-sm text-ink/60">
                  {t("knit.pattern_row", { n: currentRow.stepNumber })}
                  {currentRow.noteKey ? ` · ${tx(currentRow.noteKey)}` : ""}
                </p>
              </div>
            ) : (
              <p className="mt-4 text-sm text-ink/60">{t("knit.empty")}</p>
            )}
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setRowIndex((index) => Math.max(0, index - 1))}
                disabled={rowIndex <= 0}
                className="min-h-12 rounded-xl border border-ink/20 px-4 py-2 font-semibold disabled:opacity-40"
              >
                {t("knit.prev")}
              </button>
              <button
                type="button"
                onClick={() =>
                  setRowIndex((index) => Math.min(flatRows.length - 1, index + 1))
                }
                disabled={rowIndex >= flatRows.length - 1}
                className="min-h-12 rounded-xl bg-sage px-4 py-2 font-semibold text-white disabled:opacity-40"
              >
                {t("knit.next")}
              </button>
              <button
                type="button"
                onClick={() => setRowIndex(0)}
                className="min-h-12 rounded-xl border border-ink/20 px-4 py-2 font-semibold"
              >
                {t("knit.reset")}
              </button>
            </div>
          </div>

          <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
            <h3 className="text-xl font-semibold">{t("measures.title")}</h3>
            <dl className="mt-4 grid gap-3 sm:grid-cols-2">
              {result.pattern.measurements.map((measurement) => (
                <div
                  key={measurement.key}
                  className="rounded-xl bg-paper/70 px-4 py-3"
                >
                  <dt className="text-sm text-ink/60">
                    {tx(`m.${measurement.key}`, measurement.key)}
                  </dt>
                  <dd className="text-lg font-semibold">
                    {formatCm(measurement.value_cm)}
                    {measurement.target_cm != null ? (
                      <span className="ml-2 text-sm font-normal text-ink/50">
                        {t("measures.target", { value: formatCm(measurement.target_cm) })}
                      </span>
                    ) : null}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="grid gap-6 sm:grid-cols-2">
            <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm">
              <h3 className="text-xl font-semibold">{t("materials.title")}</h3>
              <ul className="mt-3 space-y-2 text-sm text-ink/75">
                <li>
                  {t("materials.yarn", {
                    value: tx(
                      `yarn.${result.pattern.materials.yarn_weight}`,
                      result.pattern.materials.yarn_weight,
                    ),
                  })}
                </li>
                <li>
                  {t("materials.yardage", {
                    value: numberFormat.format(result.pattern.materials.meters),
                  })}
                  {result.pattern.materials.grams
                    ? ` (${numberFormat.format(result.pattern.materials.grams)} g)`
                    : ""}
                </li>
                {result.pattern.materials.needle_mm ? (
                  <li>
                    {t("materials.needles", {
                      value: numberFormat.format(result.pattern.materials.needle_mm),
                    })}
                  </li>
                ) : null}
                {result.pattern.materials.hook_mm ? (
                  <li>
                    {t("materials.hook", {
                      value: numberFormat.format(result.pattern.materials.hook_mm),
                    })}
                  </li>
                ) : null}
                {result.pattern.materials.notions.length > 0 ? (
                  <li>
                    {t("materials.notions", {
                      value: result.pattern.materials.notions.join(", "),
                    })}
                  </li>
                ) : null}
              </ul>
            </div>

            <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm">
              <h3 className="text-xl font-semibold">{t("warnings.title")}</h3>
              {result.pattern.warnings.length === 0 ? (
                <p className="mt-3 text-sm text-ink/60">{t("warnings.none")}</p>
              ) : (
                <ul className="mt-3 space-y-2 text-sm text-ink/75">
                  {result.pattern.warnings.map((warning) => (
                    <li key={warning.code} className="flex gap-2">
                      <span aria-hidden="true">•</span>
                      <span>
                        {warning.message ?? tx(warning.message_key, warning.message_key, warning.params)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-ink/10 bg-white/80 p-5 shadow-sm sm:p-8">
            <h3 className="text-xl font-semibold">{t("instructions.title")}</h3>
            <p className="mt-1 text-sm text-ink/60">{t("instructions.lead")}</p>
            <pre className="mt-4 max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-2xl bg-paper/80 p-4 font-mono text-sm leading-relaxed">
              {patternText}
            </pre>
          </div>

          {critique ? (
            <div className="rounded-3xl border border-sage/30 bg-sage/5 p-5 shadow-sm sm:p-8">
              <h3 className="text-xl font-semibold">{t("critique.title")}</h3>
              <p className="mt-1 text-sm text-ink/60">{t("critique.lead")}</p>
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
              setFiles([]);
              setPreviews([]);
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
            {t("restart")}
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
  const { t } = useT();
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
        <option value="">{t("field.undefined")}</option>
        {options.map(([key, option]) => (
          <option key={key} value={key}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
