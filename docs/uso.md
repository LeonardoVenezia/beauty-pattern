# Uso

## Requisitos

- Python 3.12 y `uv`.
- Node.js 20+ solo para la web (hito 6).

## Comandos

```bash
make setup      # instala dependencias
make test       # suite completa
make lint       # ruff + mypy
make demo       # patron raglan M verificado -> data/demo/{txt,svg,pdf}
make eval       # evaluacion del extractor (FAKE_AI=1 si no hay clave)
make api        # API FastAPI en :8000
```

## Patron de ejemplo

`make demo` no usa IA: parte de un `GarmentSpec` escrito a mano, genera el
patron, lo pasa por el simulador y escribe texto, esquema SVG y PDF en
`data/demo/`. Si el simulador falla, el comando termina con error y no escribe
el PDF.

## IA real

Completa `AI_API_KEY` en `.env` y exporta las variables (o usa un gestor de
entorno). Con `FAKE_AI=0 make eval` se mide el endpoint real; sin clave se usa
`FAKE_AI=1` y el reporte lo indica. Las imagenes de `evals/` son sinteticas
hasta incorporar fotos reales.

## Web

La web Next.js mobile-first se construye en el hito 6. `make dev` levantara
API y web cuando exista `web/`.
