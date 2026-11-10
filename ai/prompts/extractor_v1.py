"""Prompt versionado del extractor de atributos (IA #1).

Primero observaciones concretas; despues clasificacion contra listas cerradas.
El modelo nunca devuelve medidas ni conteos de puntos.
"""

from __future__ import annotations

from typing import Any

from engine.spec import GarmentSpec

EXTRACTOR_PROMPT_VERSION = "extractor-v1"

EXTRACTOR_SYSTEM_PROMPT = """Eres una analista de prendas tejidas. Tu unica tarea es describir y clasificar lo que se ve en las fotos.

Reglas obligatorias:
1. Primero observa y describe hechos concretos (que se ve, donde, que textura, que colores).
2. Despues clasifica usando SOLO los valores permitidos por el esquema JSON.
3. Si un dato no se ve o no estas segura, usa null (o "other" si el campo es obligatorio) y anotalo en "incertidumbres" o "no_visible".
4. No inventes medidas, talles, numero de puntos, vueltas ni metraje. No des instrucciones de tejido.
5. No confundas una prenda con otra: si no es tejido, usa "other".
6. Responde solo con un objeto JSON valido, sin texto extra ni bloques de codigo."""

EXTRACTOR_USER_PROMPT = """Analiza la foto principal y los recortes de detalle adjuntos.

Foto principal: vista general de la prenda.
Recortes: {crops}.

Devuelve un objeto JSON con esta forma:
{{
  "observaciones": "descripcion breve de lo que se ve",
  "categoria": "pullover|cardigan|vest|hat|scarf|cowl|mittens|gloves|socks|shawl|blanket|bag|amigurumi|other",
  "tecnica": "needles|circular|crochet|machine",
  "construccion": null o "raglan_top_down|drop_shoulder|set_in_sleeve|yoke|bottom_up|in_one_piece|flat_panels|round_tube|modules|other",
  "escote": null o "crew|v_neck|boat|turtleneck|funnel|hood|square|none",
  "largo_cuerpo": null o "cropped|hip|tunic|long",
  "largo_manga": null o "sleeveless|short|three_quarter|long",
  "ajuste": null o "very_loose|loose|regular|fitted",
  "forma": null o "straight|a_line|boxy|curved",
  "punto_base": null o "stockinette|garter|seed|rib_1x1|rib_2x2|rib_3x1|moss|brioche|cables|lace|bobbles|honeycomb|crochet_sc|crochet_hdc|crochet_dc|other",
  "texturas": [{{"textura": "cables|lace|bobbles|honeycomb|ribbing|cabled_ribbing|other", "ubicacion": null, "repeticion_estimada": null}}],
  "colorwork": null o {{"tipo": "none|stripes|fair_isle|intarsia|mosaic", "zona": null, "colores": 2, "paleta": []}},
  "acabados": ["cuffs|hem_band|neckband|button_band|pockets|fringe|hood|lining"],
  "hilo_aparente": null o {{"grosor_estimado": null o "lace|fingering|sport|dk|worsted|bulky|super_bulky|unknown", "aspecto": null o "smooth|mohair|boucle|marled|chenille|unknown"}},
  "incertidumbres": ["..."],
  "no_visible": ["..."],
  "confianza": {{"campo": 0.0}}
}}

Los recortes disponibles son: {crop_names}.
No agregues campos fuera del esquema."""

EXTRACTOR_REPAIR_PROMPT = """Tu respuesta anterior no valido contra el esquema. Corrige el JSON.
Error de validacion: {error}

Reglas: responde solo el objeto JSON corregido, con los mismos campos y valores permitidos. No inventes datos que no se vean."""


def extractor_response_format() -> dict[str, Any]:
    schema = GarmentSpec.model_json_schema()
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "garment_spec",
            "schema": schema,
        },
    }
