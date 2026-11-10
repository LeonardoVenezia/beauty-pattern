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
  idioma?: "es" | "en";
  nivel?: "principiante" | "experta";
  unidades?: "cm" | "in";
};

export type AnalysisResponse = {
  image_id: string;
  spec: GarmentSpec;
  confidence: Record<string, number>;
  disagreements: Record<string, string[]>;
  prompt_version: string;
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
  text: { es: string; en: string };
  simulation: { ok: boolean; issues: unknown[] };
};

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
    if (data?.detail?.error) {
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

export async function analyzeImage(file: File): Promise<AnalysisResponse> {
  const form = new FormData();
  form.append("file", file);
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

export function patternPdfUrl(id: string): string {
  return `${API_URL}/pattern/${id}/pdf`;
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
  lang: "es" | "en" = "es",
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
  lang: "es" | "en" = "es",
): Promise<CritiqueResponse> {
  const response = await fetch(`${API_URL}/pattern/${id}/critique`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_id: imageId, lang }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as CritiqueResponse;
}
