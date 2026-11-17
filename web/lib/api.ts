export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type GarmentSpec = {
  categoria: string;
  tecnica: string;
  construccion: string | null;
  escote: string | null;
  largo_cuerpo: string | null;
  largo_manga: string | null;
  ajuste: string | null;
  forma: string | null;
  punto_base: string | null;
  texturas: Array<{
    textura: string;
    ubicacion: string | null;
    repeticion_estimada: string | null;
  }>;
  colorwork: {
    tipo: string;
    zona: string | null;
    colores: number;
    paleta: string[];
  } | null;
  acabados: string[];
  hilo_aparente: {
    grosor_estimado: string | null;
    aspecto: string | null;
  } | null;
  // Motivo radial de crochet descripto por la IA (capa de diseño).
  motivo?: {
    forma: string;
    simetria: number;
    bandas: Array<{ punto: string; color: number | null; peso: number }>;
    cuadrar_en_banda: number | null;
  } | null;
  // Plantilla de juguete (solo amigurumi): bear | bunny | cat | generic.
  figura?: string | null;
  cuerpo_juguete?: string | null;
  incertidumbres: string[];
  no_visible: string[];
  confianza: Record<string, number>;
  observaciones: string;
};

export type PatternParams = {
  talla: string;
  peso_hilo: string;
  medidas_cm?: Record<string, number>;
  dimensiones_cm?: Record<string, number>;
  densidad?: {
    stitches_per_10cm: number;
    rows_per_10cm: number;
  } | null;
  ease_cm?: number | null;
  panel_motivo_cm?: number | null;
  idioma?: Language;
  nivel?: "principiante" | "experta";
  unidades?: "cm" | "in";
};

export const LANGUAGES = [
  ["en", "English"],
  ["es", "Español"],
  ["fr", "Français"],
  ["de", "Deutsch"],
  ["it", "Italiano"],
] as const;
export type Language = (typeof LANGUAGES)[number][0];

export type AnalysisResponse = {
  image_id: string;
  image_ids?: string[];
  spec: GarmentSpec;
  confidence: Record<string, number>;
  disagreements: Record<string, string[]>;
  prompt_version: string;
  photo_quality?: { photo: number; issues: string[] }[];
  cached: boolean;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost_usd: number;
  };
};

export type Measurement = {
  key: string;
  value_cm: number;
  target_cm: number | null;
  tolerance_cm: number;
  kind: "circumference" | "width" | "length";
};

export type PatternWarning = {
  code: string;
  message_key: string;
  message?: string;
  params: Record<string, string | number>;
  severity: "info" | "warning" | "error";
};

export type PatternStep = {
  number: number;
  items: unknown[];
  stitch_count_end: number;
  note_key: string | null;
};

export type PatternSection = {
  id: string;
  name_key: string;
  mode: "flat" | "round";
  start_stitches: number;
  end_stitches: number;
  steps: PatternStep[];
  bind_off?: boolean;
};

export type Pattern = {
  meta: {
    id: string;
    family: string;
    title_key: string;
    size: string;
    created_at: string;
    engine_version: string;
  };
  spec?: GarmentSpec;
  params?: PatternParams;
  sections: PatternSection[];
  measurements: Measurement[];
  materials: {
    yarn_weight: string;
    needle_mm: number | null;
    hook_mm: number | null;
    meters: number;
    grams: number | null;
    notions: string[];
    colors: string[];
  };
  warnings: PatternWarning[];
};

export type PatternResponse = {
  id: string;
  pattern: Pattern;
  text: Partial<Record<Language, string>> & { es: string; en: string };
  simulation: { ok: boolean; issues: unknown[] };
};

// Errores conocidos del motor: se devuelve el codigo y la interfaz lo
// traduce (web/lib/i18n.ts, claves "error.*").
const FRIENDLY_ERRORS = new Set([
  "error.unsupported_technique",
  "error.unsupported_garment",
  "error.unsupported_sleeve",
  "error.impossible_proportions",
]);

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
    if (data?.detail?.error) {
      if (FRIENDLY_ERRORS.has(data.detail.error)) return data.detail.error;
      const params = data.detail.params
        ? ` ${JSON.stringify(data.detail.params)}`
        : "";
      return `${data.detail.error}${params}`;
    }
    if (Array.isArray(data?.detail)) {
      return data.detail.map((item: { msg?: string }) => item.msg).join("; ");
    }
    return JSON.stringify(data?.detail ?? data);
  } catch {
    return `Error ${response.status}`;
  }
}

export async function analyzeImage(
  files: File[],
  hints: { tejido?: string; categoria?: string; descripcion?: string } = {},
): Promise<AnalysisResponse> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  // Lo que la persona ya sabe de la pieza; vacío = "no sé".
  for (const [key, value] of Object.entries(hints)) if (value) form.append(key, value);
  const response = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as AnalysisResponse;
}

export async function createPattern(
  spec: GarmentSpec,
  params: PatternParams,
): Promise<PatternResponse> {
  const response = await fetch(`${API_URL}/pattern`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spec, params }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as PatternResponse;
}

export type PdfOptions = {
  photos?: string[]; // ids de imagen, en el orden de la portada (hasta 4)
  lang?: Language;
  designer?: string;
  guide?: boolean;
  paper?: "A4" | "Letter";
};

export function patternPdfUrl(id: string, options: PdfOptions = {}): string {
  const query = new URLSearchParams();
  for (const photo of options.photos ?? []) query.append("foto", photo);
  if (options.lang) query.set("lang", options.lang);
  if (options.designer?.trim()) query.set("disenio", options.designer.trim());
  if (options.guide === false) query.set("guia", "false");
  if (options.paper && options.paper !== "A4") query.set("papel", options.paper);
  const text = query.toString();
  return `${API_URL}/pattern/${id}/pdf` + (text ? `?${text}` : "");
}

/** El texto del patron en otro idioma (mismos numeros, sin IA). */
export async function fetchPatternText(id: string, lang: Language): Promise<string> {
  const response = await fetch(`${API_URL}/pattern/${id}?lang=${lang}`);
  if (!response.ok) throw new Error("err.change_language"); // clave de i18n
  const data = (await response.json()) as PatternResponse;
  return data.text[lang] ?? data.text.es;
}

export function patternSvgUrl(id: string): string {
  return `${API_URL}/pattern/${id}/svg`;
}

export type RewriteResponse = {
  text: string;
  fallback_used: boolean;
  attempts: number;
  validation_errors: string[];
  prompt_version: string;
};

export type CritiqueResponse = {
  observations: string[];
  risks: string[];
  fallback_used: boolean;
  prompt_version: string;
};

export async function rewritePattern(
  id: string,
  lang: Language = "es",
): Promise<RewriteResponse> {
  const response = await fetch(`${API_URL}/pattern/${id}/rewrite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lang }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as RewriteResponse;
}

export async function critiquePattern(
  id: string,
  imageId: string,
  lang: Language = "es",
): Promise<CritiqueResponse> {
  const response = await fetch(`${API_URL}/pattern/${id}/critique`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_id: imageId, lang }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as CritiqueResponse;
}
