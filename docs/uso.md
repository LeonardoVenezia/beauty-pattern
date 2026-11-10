# Uso

## Requisitos

- Python 3.12 y `uv`.
- Node.js 20+ para la web.

## Comandos

```bash
make setup      # instala dependencias
make test       # suite completa
make lint       # ruff + mypy
make demo       # patron raglan M verificado -> data/demo/{txt,svg,pdf}
make eval       # evaluacion del extractor (FAKE_AI=1 si no hay clave)
make api        # API FastAPI en :8000
make dev        # API en :8000 y web en :3000
make web        # solo web Next.js en :3000
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

```bash
cd web
npm install
npm run dev      # http://localhost:3000
```

La web usa `NEXT_PUBLIC_API_URL` para ubicar la API; por defecto
`http://localhost:8000`. `make dev` levanta API y web en paralelo. El flujo es:
subir foto -> revisar atributos detectados -> elegir talle, hilo y muestra ->
ver el patron verificado -> descargar PDF o esquema SVG.

Con `FAKE_AI=1` la extraccion es simulada; la web funciona igual y sirve para
probar todo el flujo sin red ni costo.

## Endpoints principales

- `POST /analyze` — multipart `file`; devuelve `GarmentSpec`, confianza,
  desacuerdos e id de imagen.
- `POST /pattern` — `{spec, params}`; devuelve patron serializado, texto es/en
  y resultado del simulador.
- `GET /pattern/{id}` — patron guardado.
- `GET /pattern/{id}/pdf` y `/svg` — descargas.
- `POST /pattern/{id}/rewrite` — redaccion con IA validada contra los numeros;
  si falla, devuelve la plantilla determinista.
- `POST /pattern/{id}/critique` — critica informativa con la foto guardada;
  nunca modifica el patron.
- `GET /stitches` — catalogo de puntos.
