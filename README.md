# Tejedora

Foto de una prenda tejida -> patron completo, calculado y verificado.

**Principio rector:** la IA interpreta; el codigo calcula. Ningun numero de un
patron (puntos, aumentos, vueltas, medidas, metraje) sale de un modelo de IA.
Todo lo calcula `engine/` de forma determinista y lo verifica el simulador
antes de mostrar el patron.

## Requisitos

- Python 3.12 (lo instala `uv` automaticamente)
- Node.js 20+ para la web
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Puesta en marcha

```bash
cp .env.example .env      # completa AI_API_KEY solo si vas a usar IA real
make setup
make test
make demo                 # patron de ejemplo end to end con FAKE_AI=1
make dev                  # API en :8000 y web en :3000
```

La web queda en <http://localhost:3000>. La API documenta sus endpoints en
<http://localhost:8000/docs>.

## IA del producto

El modelo se configura **solo** por entorno (`AI_PROVIDER`, `AI_BASE_URL`,
`AI_API_KEY`, `AI_MODEL`). El proveedor documentado es Refuseless, API
compatible con OpenAI Chat Completions, base `https://api.refuseless.com/v1`,
modelo `deepseek-v4.1-flash-fast`. Ver `docs/fuentes.md` y `DECISIONS.md`.

Con `FAKE_AI=1` (valor por defecto en `.env.example`) no se hace ninguna
llamada de red ni se gasta credito. Todos los tests corren asi.

`GET /health/ai` muestra el resultado del sondeo de capacidades (texto,
imagenes, JSON estructurado, tool calling).

## Estructura

```
engine/   motor determinista: IR, puntos, prendas, simulador, i18n
vision/   preprocesado de imagen, color, motivos
ai/       cliente, prompts, sondeo, cache
api/      FastAPI
web/      Next.js mobile-first
render/   SVG y PDF
tests/    unitarios, propiedades, golden, e2e
evals/    fotos de prueba y medicion de la IA
docs/     fuentes, ejemplos y documentacion
```

## Despliegue

Hay `Dockerfile` para la API, `web/Dockerfile` para la web y
`docker-compose.yml` para levantar ambos. Ver `docs/despliegue.md` para
variables, HTTPS, respaldos y limitaciones.

```bash
cp .env.example .env
docker compose up --build
```

## Documentacion

- `PROYECTO.md` — diseno completo.
- `AGENTS.md` — reglas de trabajo.
- `DECISIONS.md` — decisiones y supuestos.
- `PROGRESS.md` — estado real por hito.
- `docs/fuentes.md` — fuentes de convenciones de tejido.
- `docs/uso.md` — guia de uso.
- `docs/despliegue.md` — Docker, variables y operacion.

## Aviso

Los patrones son guias: teje siempre una muestra antes de empezar. El metraje
es una estimacion. Si la prenda de la foto es de un disenador, su patron
original es suyo; esta herramienta genera un patron propio inspirado en la
apariencia general.
