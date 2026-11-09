# Decisiones

Bitacora de decisiones tomadas por el agente. Formato: decision, alternativas,
motivo. Las marcadas **ASUNCION** son convenciones no respaldadas por una
fuente publica verificada.

## D001 — Formato de API de Refuseless (2026-11-09)

- **Decision:** adaptador compatible con OpenAI Chat Completions.
- **Evidencia:** documentacion oficial de Refuseless
  (`https://docs.refuseless.com/api/chat-completions`): `POST
  https://api.refuseless.com/v1/chat/completions`, mensajes OpenAI,
  `response_format` pasado tal cual, `Authorization: Bearer`. La pagina del
  modelo confirma el id `deepseek-v4.1-flash-fast`.
- **Alternativas:** SDK de Anthropic (`/v1/messages`), SDK OpenAI. Se eligio
  HTTP directo para no agregar una dependencia pesada y controlar timeouts,
  cache y reintentos.
- **Nota:** la documentacion no afirma explicitamente que
  `deepseek-v4.1-flash-fast` acepte imagenes. Por eso el sondeo
  (`ai/probe.py`) lo verifica con una imagen sintetica y el sistema falla con
  un mensaje claro si no las acepta. No se asume vision.

## D002 — Python 3.12 con uv

- **Decision:** `uv` administra Python 3.12 y el entorno virtual.
- **Motivo:** el stack fijado lo pide. `uv` no estaba instalado; se instalo con
  el instalador oficial en `~/.local/bin`.

## D003 — IR como salida final estructurada

- **Decision:** el simulador consume `engine.ir.Pattern`, la misma estructura
  que alimenta texto, SVG y PDF. No existen dos representaciones.
- **Alternativa:** serializar el patron a un formato aparte solo para el
  simulador. Se descarto por duplicacion y riesgo de divergencia.
- **Consecuencia:** la IR debe declarar el conteo final de cada vuelta y los
  objetivos de medida; el simulador los verifica de forma independiente.

## D004 — Redondeos

- **Decision:** redondeo half-up explicito (`engine.rounding.round_half_up`).
- **Motivo:** el redondeo bancario de Python sorprende y no es el esperado en
  tejido. Toda conversion puntos<->cm documenta su redondeo.

## D005 — Medidas y holguras

- **ASUNCION:** los valores de la tabla de talles son puntos medios de los
  rangos de Craft Yarn Council; los largos, contornos de brazo/cuello/espalda
  y las holguras por ajuste (entallado -2 cm, regular +6, holgado +12, muy
  holgado +20) son valores de trabajo de este motor, no una tabla publicada.
- **Motivo:** se necesitaba una base determinista para generar patrones. Se
  documentan en `docs/fuentes.md` y son editables via medidas propias.

## D006 — Raglan sin hileras cortas

- **ASUNCION:** la version inicial del raglan top-down no incluye hileras
  cortas para el escote. Se genera un escote circular parejo y se advierte en
  el patron. Las variantes V, barco y cuello alto se manejan cambiando el
  contorno de montado y el borde, no la geometria del canesu.
- **Motivo:** las hileras cortas agregan una complejidad de verificacion alta
  para el primer hito de prenda. Se declara la limitacion en `PROGRESS.md`.

## D007 — FAKE_AI deterministico

- **Decision:** con `FAKE_AI=1` el extractor usa muestras sinteticas
  deterministas derivadas del hash de la imagen, con ruido controlado, para
  poder testear votacion y reparacion sin red.
- **Motivo:** los tests deben correr sin costo y sin depender del proveedor.
  La evaluacion con `FAKE_AI=1` mide el efecto de la votacion sobre ese ruido
  simulado y se informa como tal; no es una medicion del modelo real.

## D008 — PDF con ReportLab

- **Decision:** PDF con ReportLab; SVG propio.
- **Alternativas:** WeasyPrint (depende de librerias nativas del sistema).
  ReportLab es mas portable y suficiente para el diseno del patron.
