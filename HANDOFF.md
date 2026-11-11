# Handoff — Tejedora

**Fecha:** 2026-11-11 (actualizado; ver sección 0)
**Rama:** `build/main-agent`
**HEAD de código de referencia:** `cd0fe4d` (último commit de implementación;
esta documentación se agrega en commits posteriores sobre la misma rama)
**Estado:** hitos 1–11 cerrados con limitaciones declaradas, más correcciones
posteriores (clasificación de cuadrado de crochet y **mejora de presentación**:
texto comercial y diagramas de piezas). Suite de **2136 tests**, `ruff`, `mypy`
(estricto en `engine/`) y build de Next.js en verde.

Este documento es el punto de entrada para **commandcode** o cualquier otro
agente que retome el proyecto. Antes de tocar código, leer también
`AGENTS.md`, `PROYECTO.md`, `PROGRESS.md` y `DECISIONS.md`.

> **Regla no negociable (sigue vigente):** la IA interpreta; el código calcula.
> Ningún número de un patrón (puntos, vueltas, medidas, metraje) sale de un
> LLM. El esquema y el PDF se generan de forma determinista desde la IR
> verificada por el simulador; la IA no dibuja.

## 0. Sesión 2026-11-11 — calidad de mercado (leer primero)

Objetivo: que el PDF cumpla `Especificación generador de patrones de tejido
(estándar de mercado).md`. Diagnóstico en `DECISIONS.md` D022: el problema
era de concepto y de motor, no de IA. Lo hecho está en D023 y en `PROGRESS.md`.

- **Nuevos módulos:** `engine/multisize.py` (todos los talles `a (b, c)`),
  `engine/document.py` (14 secciones), `render/pdf.py` (reescrito sobre el
  documento), `render/sweater.py` (esquema con cotas por letra),
  `render/granny.py`, `scripts/generar_patron.py`, `examples/*.yaml`.
- **Flujo del PDF:** `render_pattern_pdf(pattern)` regenera todos los talles
  con `generate_size_set` (cada uno simulado) y resalta el talle del
  patrón. La API (`GET /pattern/{id}/pdf?papel=Letter&imprimir=true`) no
  cambió de forma.
- **CLI:** `make patron ARCHIVO=examples/sueter-raglan.yaml TALLE=M`.
- **Invariantes nuevos con test:** el texto combinado proyecta exactamente a
  cada talle (`tests/test_multisize.py`); la sisa crece con el talle; ninguna
  clave i18n sin traducir en ninguna familia (`tests/test_document.py`,
  `tests/test_i18n_keys.py`).
- **Español:** abreviaturas de la especificación (der, rev, 2pjd, pts, mc),
  tildes, instrucciones en infinitivo. Al agregar textos, mantener ese estilo.
- **Verificación:** 2255 tests, `make lint` y `tsc` de la web en verde.
  `svglib` sí está instalado y el esquema se incrusta.

**Continuación (misma fecha):** las texturas de la foto ya llegan al patrón
como panel (`engine/garments/panels.py`, D024); se corrigieron jersey plano,
elásticos planos y la manga encajada (`engine/garments/rows.py` es el
acumulador de hileras planas LD/LR). 2305 tests.

**Continuación 2:** panel en manga encajada, escote redondo en piezas,
compensación de trenzas con `panel_motivo_cm`, `make eval-fotos` (ver
`evals/photos/README.md`). D025. 2320 tests.

**Próximos pasos, en orden:**
1. *Capa de diseño* para reproducir motivos de la foto (p. ej. el mandala de
   `patron.jpeg`): la IA describe la estructura con vocabulario cerrado
   (vueltas, familias de punto, repeticiones radiales, color por vuelta) y
   el motor calcula y simula. Hoy se entrega un granny clásico y se avisa.
2. *Evaluación real:* el armado está (`make eval-fotos`); faltan 20–30
   fotos con derechos claros en `evals/photos/`. Después, comparar modelos
   de visión (es un cambio de `.env`).
3. Jacquard/fair isle como gráfico de color; panel en manga encajada;
   escote con forma (cuello redondo) en piezas planas.
4. Esquemas con letras para cardigan, chaleco y accesorios.
5. La web muestra el texto de un talle; pasar a mostrar el documento.

## 1. Qué es este proyecto

Aplicación web que convierte la foto de una prenda o pieza tejida en un patrón
completo, calculado y verificado. La usuaria final teje; no es técnica. El
flujo es foto -> confirmación de atributos -> medidas/hilo/densidad -> patrón
verificado -> PDF/SVG/web.

**Regla no negociable:** la IA interpreta; el código calcula.

- La IA solo extrae atributos de la foto, redacta texto a partir de números ya
  calculados y critica un patrón existente.
- Ningún número de un patrón sale de un LLM. Todos los calcula `engine/` de
  forma determinista.
- Todo patrón pasa por `engine/simulator/` antes de mostrarse. Si el simulador
  falla, no se entrega el patrón.

## 2. Arranque rápido

Requisitos: Python 3.12, `uv`, Node.js 20+ y `make`.

```bash
cp .env.example .env          # opcional: completar AI_API_KEY para IA real
make setup
make test                     # 2136 tests
make lint                     # ruff + mypy
cd web && npm run build && cd ..
make demo                     # patrón raglán verificado, sin IA
make dev                      # API :8000 + web :3000, carga .env en la API
```

La API documenta sus endpoints en <http://localhost:8000/docs>. La web queda
en <http://localhost:3000>. La web no lee el `.env` raíz: usa
`NEXT_PUBLIC_API_URL` desde su propio entorno y cae a `http://localhost:8000`.
Para apuntarla a otra API, exportá esa variable antes de `npm run dev` o del
build.

Si `npm ci` falla por el registry privado configurado en la máquina:

```bash
cd web && npm ci --registry=https://registry.npmjs.org && cd ..
```

### Verificación ejecutada (2026-11-10)

- `make test`: **2136 passed**, 1 `StarletteDeprecationWarning` por
  `httpx`/`starlette.testclient` (no falla).
- `make lint`: ruff y mypy estricto sin errores.
- `FAKE_AI=1 make eval`: 3 casos sintéticos, accuracy 1.0 (mide el flujo, no
  visión real).
- `make demo`: genera `data/demo/patron.txt`, `esquema.svg` y `patron.pdf`.
- `cd web && npm run build`: build de producción verde. Next imprime
  “Skipping linting” porque `web/package.json` no tiene script de lint.

## 3. IA: real vs. simulada

La configuración es 100 % por entorno. El código no contiene URL ni id de
modelo. Valores documentados en `.env.example`:

- `AI_PROVIDER=refuseless`
- `AI_BASE_URL=https://api.refuseless.com/v1`
- `AI_MODEL=deepseek-v4.1-flash-fast`
- `AI_API_KEY` (nunca versionar)
- `FAKE_AI=1` para pruebas sin red ni costo; `FAKE_AI=0` para IA real.

En esta máquina existe un `.env` local con IA real configurada. **No lo
commitees, no imprimas la clave y no lo borres.** El `.env` no se recarga solo:
si cambiás una variable, reiniciá la API (`make api` o `make dev`).

`GET /health/ai` muestra el sondeo de capacidades (imagen, JSON estructurado,
tool calling). Si el proveedor no acepta imágenes, `/analyze` falla con un
mensaje claro; no se inventa un patrón.

La API real ya se verificó manualmente con la foto local `patron.jpeg`: la
imagen se clasifica como `granny_square` / `crochet` y `POST /pattern` genera
la familia `granny_square` con un cuadrado de 20 × 20 cm. Esa verificación no
es una evaluación exhaustiva.

Para una evaluación real del extractor:

```bash
set -a; source .env; set +a
FAKE_AI=0 make eval
```

`make eval` **no** carga `.env` por sí solo (a diferencia de `make api` y
`make dev`). Sin exportar las variables usa `FAKE_AI=1` o falla por
configuración incompleta. La eval actual tiene 3 casos sintéticos; no mide
visión real sobre fotos variadas.

## 4. Arquitectura

```
engine/    motor determinista: IR, puntos, prendas, simulador, i18n
vision/    preprocesado, color, segmentación, motivos repetibles
ai/        cliente, prompts versionados, extractor, redactor, crítico, probe
api/       FastAPI + SQLite + rate limit
web/       Next.js + TypeScript + Tailwind, mobile-first
render/    SVG y PDF
tests/     unitarios, propiedades (hypothesis), golden, API
evals/     casos sintéticos y medición por campo
docs/      fuentes, uso, despliegue, ejemplos
scripts/   demo y generación de ejemplos
```

Flujo:

```
foto -> preprocesado -> extractor IA (N muestras + votación + Pydantic)
     -> confirmación editable en la web
     -> engine/garments (familia pura) -> IR
     -> engine/simulator (obligatorio)
     -> texto determinista + SVG/PDF
```

### Rutas clave

- `engine/spec.py` — `GarmentSpec`, `PatternParams`, enums de categorías,
  técnicas y construcciones. `Category.GRANNY_SQUARE` vive acá.
- `engine/garments/__init__.py` — despacho por técnica/categoría/construcción.
- `engine/garments/raglan.py` — pullover raglán top-down.
- `engine/garments/flat.py` — hombro caído, cardigan, chaleco.
- `engine/garments/yoke.py` — canesú circular.
- `engine/garments/set_in.py` — manga encajada.
- `engine/garments/accessories.py` — gorro, bufanda, cuello, mitones, medias,
  chal, manta, bolso y pieza plana.
- `engine/garments/crochet.py` — amigurumi, bufanda, bolso, pieza plana y
  `generate_granny_square`.
- `engine/simulator/` — verificador de conteos, consumos, aumentos,
  disminuciones, medidas y uniones.
- `engine/blocks.py` — **capa de presentación** (bloques tipados) que comparten
  texto y PDF: compresión presentacional de vueltas (rangos y ciclos con
  progresión/nota y conteo final declarado), formateo con abreviaturas y
  glosario automático de las abreviaturas usadas. No cambia la IR ni los
  números.
- `engine/text.py` — renderiza los bloques a texto plano (`render_pattern_text`
  mantiene firma; siempre abreviado con glosario). El contador de la web sigue
  leyendo los pasos reales de la IR.
- `ai/prompts/extractor_v2.py` — prompt vigente del extractor. `extractor_v1.py`
  queda como historial; no importarlo.
- `ai/extractor.py` — muestras, votación, reparación, caché y confianza.
- `api/main.py` — endpoints y validación de errores.
- `web/app/page.tsx` — flujo completo, categorías, técnicas soportadas y
  medidas por categoría.
- `render/schematic.py` — **diagramas de piezas paramétricos** derivados de la
  IR (perfil de puntos por sección + medidas/gauge): piezas acotadas con
  contorno según la progresión de puntos y conteos. Un único SVG para web y PDF.
- `render/draw.py` — primitivas SVG (cotas, flechas, etc.) compatibles con
  svglib.
- `render/pdf.py` — PDF con formato comercial (portada, esquema embebido vía
  svglib, materiales/medidas/tablas, glosario e instrucciones) renderizado
  desde los mismos bloques que el texto. Si `svglib` no está instalado, el PDF
  se genera sin el esquema embebido (fallback).

## 5. Estado funcional

### Familias disponibles

Dos agujas/circular:

- Pullover raglán top-down, hombro caído, canesú circular y manga encajada.
- Cardigan y chaleco en piezas planas.
- Gorro, bufanda, cuello circular, mitones, medias tubulares, chal rectangular,
  manta rectangular, bolso rectangular y pieza plana genérica.

Crochet:

- Amigurumi (esfera, cilindro, cono).
- Bufanda plana, bolso rectangular y pieza plana genérica.
- Granny square sólido simplificado (`granny_square`).

No soportado: guantes con dedos (`gloves`), tejido a máquina (`machine`),
prendas de crochet, talón de media, chal triangular, unión de módulos y
jacquard convertido a gráfico.

### Correcciones recientes

- Las medidas de la UI dependen de la categoría: las prendas piden talle y
  holgura; accesorios y crochet piden solo sus medidas.
- Bolso y pieza plana tienen generador propio y un diagrama de pieza acotado;
  las asas del bolso son opcionales y no están incluidas en el patrón.
- Mitones reducidos a dos piezas reutilizables (mano y pulgar) con nota de
  armado y diagrama propio.
- La foto de un cuadrado de crochet ya no se clasifica como bolso. Se agregó
  `granny_square`, el prompt `extractor-v2` y la regla de que un bolso requiere
  abertura, volumen o asas.
- El granny square tiene diagrama propio y la UI pide el lado del cuadrado.
- Errores 422 de la web traducidos a mensajes entendibles.

### Sesión 2026-11-10 — texto comercial y diagramas de piezas (commits nuevos)

Motivación: el esquema era “inútil” y las instrucciones no parecían un patrón
comprado. Se descartó generar dibujos con IA (los números/formas deben ser
verificables y deterministas; la IA ya cumple su rol interpretando la foto).

Commits (sobre `c65e6a1`):
- `daf4489 feat(text): instrucciones estilo patron comercial con vueltas comprimidas`
  — `engine/blocks.py` + reescritura de `engine/text.py` + claves i18n
  (es/en): instrucciones con compresión presentacional (rangos/ciclos,
  anclados en la vuelta con nota, conteo final declarado) y glosario
  automático. El raglán demo pasó de 438 a ~115 líneas. Firma de
  `render_pattern_text` intacta; la validación de números del redactor IA
  sigue comparando contra la IR.
- `daa06d9 feat(render): esquemas tecnicos por familia con cotas y silueta`
  — `render/draw.py` y primera versión de siluetas por familia (un solo SVG
  web/PDF). **Sustituido** por el commit siguiente.
- `184fe90 feat(render): PDF comercial con portada, tablas y esquema SVG embebido`
  — `render/pdf.py` renderiza desde bloques (portada, tablas
  materiales/medidas, glosario, secciones) y embebe el SVG vía svglib.
  `pyproject.toml` declara `svglib>=1.5` con fallback si no está instalado.
- `cd0fe4d feat(render): diagramas de piezas parametricos derivados de la IR`
  — reescritura de `render/schematic.py`: piezas acotadas calculadas desde el
  perfil de puntos por sección y las medidas/gauge de la IR (contorno según
  progresión de puntos, conteos `inicio → fin`), en vez de siluetas
  genéricas. Paneles/accesorios y prendas como conjunto de piezas.

Regenerados `data/demo/*` con `PYTHONPATH=. .venv/bin/python scripts/demo.py`.

Ver `DECISIONS.md` D021 (presentación determinista: bloques, diagramas de
piezas, PDF, sin IA en el dibujo) y D019/D020.

## 6. Limitaciones conocidas

1. **Granny square clásico:** se teje en redondo con grupos de 3 pa y color
   por vuelta, pero no reproduce motivos complejos de la foto (pétalos,
   puffs, relieves). Se advierte con `granny_classic`.
2. **Manta en crochet:** la UI ofrece “Manta” y crochet, pero el backend
   despacha `BLANKET` a `generate_granny_square` y pide “Lado del módulo”. No
   calcula una manta completa ni la cantidad/uniones de módulos. Revisar y
   corregir antes de promocionar mantas de crochet.
3. **Bolso:** panel rectangular; no incluye asas, forro, cierre ni unión de
   módulos. El diagrama muestra asas/doblez solo como referencia opcional.
4. **Pieza plana:** fallback honesto para una foto no reconocida; no infiere
   una prenda.
5. **Diagramas de prendas (paramétricos pero simplificados):** el contorno se
   deriva del perfil de puntos por sección y las medidas/gauge, pero **no**
   modela curvas de escote/sisa/copa detalladas ni la geometría fina de cada
   construcción (p.ej. la línea de raglán/canesú como plano de piezas clásico
   o la copa encajada real). Es mucho más fiel que la silueta anterior, pero
   sigue siendo una representación simplificada por familia/sección. Afinarlo
   requiere exponer/derivar más geometría desde la IR por familia.
6. **Prendas planas/construcciones:** no modelan sisas, escotes, ojales ni copa
   completa de manga. El canesú no genera gráfico de jacquard. La manga
   encajada usa una copa simplificada.
7. **Accesorios:** no hay guantes con dedos, talón de media, mitones tejidos en
   redondo con pulgar integrado, chal triangular ni manta modular.
8. **Crochet:** no hay cambios de color, ensamblaje de módulos ni prendas de
   crochet. La densidad de crochet usa una tabla de referencia de dos agujas
   editable.
9. **PDF y svglib:** `pyproject.toml` declara `svglib>=1.5` para embeber el
   mismo SVG del esquema en el PDF. En este entorno no se pudo instalar en el
   venv (sin `pip` en el venv y `uv pip install` no completó), así que el PDF
   generado aquí puede salir sin el dibujo embebido; el render tiene fallback
   y, con `svglib` disponible, lo incrusta automáticamente.
10. **IA:** el extractor se verificó con una foto real; `evals/` solo tiene
    casos sintéticos. La confianza del modelo puede ser alta aunque la
    clasificación sea dudosa.
11. **Web/e2e:** `npm run build` pasa, pero no hay script de lint en `web/` y
    Playwright no se ejecutó (faltan navegadores y la usuaria pidió no usar
    automatización de navegador). `make e2e` requiere `npx playwright install`.
12. **Producción:** SQLite, rate limit en memoria, sin autenticación ni
    almacenamiento de objetos. Sirve para una instancia pequeña, no para
    varias réplicas.

## 7. Próximos pasos sugeridos, en orden

1. **Afinar diagramas de piezas (prioridad visual):** donde la IR lo permita,
   derivar contornos más fieles por familia (escote, sisa y caída de raglan en
   cuerpo/canesú, copa de manga, talón/puntera) y mejorar layout de cotas para
   evitar solapes en talles extremos. Agregar cartas/gráficos de punto
   (`render/chart.py` ya existe) cuando el patrón tenga un motivo repetido.
2. **Paridad web ↔ PDF:** la web (`web/app/page.tsx`) aún muestra el patrón
   mayormente como texto corrido + SVG; darle la misma jerarquía que el PDF
   (secciones, tabla de medidas/materiales, glosario) usando la misma
   estructura/bloques si se expone desde la API.
3. **svglib en el entorno de ejecución:** asegurar instalación de `svglib` en
   los entornos que generan PDF para que el esquema siempre se embeba (hoy
   hay fallback).
4. **Corregir la manta de crochet:** decidir si se genera una manta
   rectangular real o si la UI debe rotularla como “módulo granny square”.
   Agregar test que cubra `width`/`length` y no solo `size`.
5. **Ampliar la evaluación real:** incorporar fotos con derechos claros
   (pulover, cardigan, gorro, bolso, cuadrado), correr `make eval` con IA real
   y registrar precisión por campo y por versión de prompt.
6. **Granny square fiel:** si se quiere reproducir el motivo de la foto,
   implementar grupos, rondas y cambios de color; mientras tanto, mantener la
   advertencia visible.
7. **Familias pendientes:** guantes, talón de media, chal triangular, ojales
   de cardigan y gráfico de jacquard del canesú.
8. **Calidad de flujo:** prueba e2e manual o Playwright (pedir permiso antes de
   usar el navegador), regresión visual de SVG/PDF y un lint/typecheck explícito
   para la web.
9. **Producción:** autenticación si habrá cuentas, Postgres/uploads de objetos,
   rate limit compartido, backups y observabilidad.
10. **Higiene:** revisar los artefactos locales (`patron.jpeg`, PDFs de prueba)
    antes de agregarlos a `evals/`; no commitearlos sin autorización. Also
    quedan cambios locales preexistentes sin commitear por mí (`.gitignore`,
    `AGENTS.md`, `PROGRESS.md`, `README.md`, `docs/uso.md`, `render/draw.py`
    menor) y archivos no trackeados (`HANDOFF.md`, `.commandcode/`, `.npmrc`);
    revisarlos antes de commitear.

## 8. Pruebas manuales mínimas

Con `make dev` levantado y la API cargando `.env`:

```bash
# Salud de la IA
curl -s http://localhost:8000/health/ai

# Análisis real de la foto local (consume tokens)
curl -s -F "file=@patron.jpeg" http://localhost:8000/analyze

# Patrón sin foto (útil para probar el motor)
curl -s -X POST http://localhost:8000/pattern \
  -H 'content-type: application/json' \
  -d '{"spec":{"categoria":"granny_square","tecnica":"crochet"},"params":{"dimensiones_cm":{"size":20}}}'
```

Verificar que `POST /pattern` responda 200, que `family` sea `granny_square`,
que las medidas sean 20 × 20 cm y que el PDF se abra. Para no gastar crédito,
usar `FAKE_AI=1`.

## 9. Archivos locales y secretos

- `.env` está fuera de git y contiene la configuración real. No mostrarlo ni
  commitearlo.
- `patron.jpeg`, `patron-*.pdf` son artefactos de prueba de la usuaria. Están
  ignorados por `.gitignore`; no borrarlos ni commitearlos sin confirmación.
- `data/`, `.ai-cache/`, `web/node_modules/` y `web/.next/` son generados y no
  se versionan.

## 10. Reglas de trabajo para el próximo agente

- Trabajar en `build/main-agent`; no reescribir historial ni hacer
  `push --force`.
- Tests primero para el motor. Toda familia nueva necesita propiedades,
  golden y paso por el simulador.
- No agregar números calculados por IA ni relajar el simulador para que un
  patrón pase.
- Documentar decisiones y supuestos en `DECISIONS.md`; actualizar
  `PROGRESS.md` solo cuando esté verificado.
- Mantener `ruff`, `mypy`, `pytest` y `npm run build` en verde.
- Commits pequeños y claros. No commitear secretos ni artefactos de la usuaria.
- Si algo no se pudo verificar, decirlo en `PROGRESS.md`/`HANDOFF.md`; no
  marcarlo como hecho.
