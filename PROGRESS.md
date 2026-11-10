# Progreso

Estado real, verificado ejecutando. No se marca como hecho nada que no haya
pasado tests.

## Hito 1 — Cimientos

Completado y verificado con `pytest`, `ruff` y `mypy` en verde.

- [x] Repo git, rama `build/main-agent`, Makefile, `.env.example`.
- [x] Unidades cm/pulgadas, redondeo explicito, densidad (gauge).
- [x] IR de patrones (ops, pasos, secciones, medidas, uniones).
- [x] Especificacion `GarmentSpec` y `PatternParams` con listas cerradas.
- [x] i18n es/en (catalogos con las mismas claves).
- [x] Cliente de IA OpenAI-compatible, cache por hash, reintentos, log de costo.
- [x] `FAKE_AI=1` y cliente falso.
- [x] Sondeo de capacidades y `GET /health/ai`.
- [x] Tests del hito y commit de cierre.

**Documentacion de Refuseless leida (2026-11-09):** API compatible con
OpenAI Chat Completions en `https://api.refuseless.com/v1`, modelo
`deepseek-v4.1-flash-fast`, `response_format` pasado tal cual. La
documentacion no afirma explicitamente entrada de imagenes para este id, asi
que el sondeo las verifica en runtime y falla con mensaje claro si no las
acepta.

**Sondeo real:** no habia `AI_API_KEY` en el entorno al construir el hito. No
se probo contra el endpoint real. Todo quedo verificado con `FAKE_AI=1` y con
un cliente simulado en los tests. Ver `DECISIONS.md` D001.

## Hito 2 — Catalogo de puntos y graficos SVG

Completado y verificado.

- [x] Catalogo declarativo con: jersey, bobo, arroz, musgo, elasticos 1x1/2x2/3x1,
  canale ingles, trenzas 2/2 y 3/3 (frente y atras), ochitos, calado basico,
  bobos, nido de abeja, punto bajo, medio punto alto, punto alto y anillo
  magico.
- [x] Cada punto declara multiplo, vueltas, operaciones y notas; el motor de
  prendas ajusta conteos al multiplo.
- [x] Graficos SVG generados desde las mismas operaciones, con grilla,
  numeros de vuelta, leyenda y accesibilidad (`title`/`desc`).
- [x] Validacion automatica del catalogo y tests de render (XML valido).
- [x] `ruff` y `mypy` en verde.

**ASUNCION:** canale ingles se representa como columnas atomicas
(`brk`/`brp`) para que el simulador pueda contar puntos; el texto explica la
tecnica. El nido de abeja es una representacion simplificada con cruces
alternados. Ver `docs/fuentes.md`.

## Hito 3 — Simulador de puntos

Completado y verificado.

- [x] `engine/simulator/` interpreta la IR final vuelta por vuelta.
- [x] Comprueba consumo exacto, conteo declarado, total de aumentos y
  disminuciones por seccion, medidas objetivo con tolerancia y uniones.
- [x] Errores tipados (`Issue`) y `SimulationReport.raise_if_failed()`.
- [x] Tests unitarios y de propiedades con hypothesis (patrones validos,
  mutaciones que deben fallar y uniones).
- [x] `ruff` y `mypy` en verde; suite completa en verde.

## Hito 4 — Pullover raglan top-down

Completado y verificado.

- [x] Generador `engine/garments/raglan.py`: canesu compuesto (aumentos de
  cuerpo y mangas en la misma vuelta o separados), separacion de mangas con
  montado de axila, cuerpo circular, mangas y puños.
- [x] Planificacion determinista de conteos: busca axila y aumentos que mejor
  cierran el contorno de busto y brazo; ajusta a multiplos de 4/2.
- [x] Variantes: escotes crew, V, barco, cuello alto, embudo y cuadrado;
  largos de cuerpo cropped/hip/tunic/long; mangas corta, tres cuartos y larga.
  Sin mangas se rechaza con error claro (familia de chaleco, hito posterior).
- [x] Canesu con aumentos en vueltas alternas; si el largo de manga o la
  profundidad de sisa no cierran, usa aumentos en cada vuelta y lo advierte.
- [x] Texto determinista es/en, esquema SVG de medidas y PDF con ReportLab.
- [x] Simulador en verde para 224 combinaciones de talle x grosor de hilo x
  ajuste, y para todas las variantes de escote/largo; tests de propiedades con
  densidades y medidas generadas.
- [x] Golden talle M (DK 22 pts/30 vtas): cuello 80, canesu 80->328, cuerpo
  200->220, mangas 74->40, puños 40; profundidad de canesu 25 cm.
- [x] `ruff` y `mypy` en verde; suite completa (400 tests) en verde.

**ASUNCION:** el canesu, cuerpo y mangas se generan en jersey; si se pide otro
punto base se advierte y se teje jersey (el catalogo de texturas se integrara
en un hito posterior). Ver `DECISIONS.md` D010.

## Hito 5 — Percepcion (preprocesado, extractor, color y motivos)

Completado y verificado con tests; la IA real no se probo por falta de clave.

- [x] `vision/preprocess.py`: valida formato/tamano/pixeles, corrige orientacion
  EXIF, elimina metadatos, redimensiona a 1344 px y genera recortes de pecho,
  puno y textura.
- [x] `ai/prompts/extractor_v1.py`: prompt versionado, observaciones antes de
  clasificar, listas cerradas y esquema JSON derivado de `GarmentSpec`.
- [x] `ai/extractor.py`: N muestras (3 por defecto), validacion Pydantic,
  reparacion acotada (2 reintentos), votacion campo por campo, confianza por
  acuerdo, desacuerdos e incertidumbres; tolera muestras invalidas si queda al
  menos una valida.
- [x] Cache por hash de imagen + prompt en el cliente existente; uso de tokens
  y costo agregados por extraccion.
- [x] `vision/color.py`: cuantizacion k-means en Lab, paleta ordenada y
  limpieza de pixeles aislados.
- [x] `vision/repeat.py`: deteccion de periodo por autocorrelacion y ajuste del
  motivo a un divisor del total de puntos.
- [x] `vision/segmentation.py`: interfaz intercambiable, no-op y heuristica por
  color de borde (rembg/SAM quedan como implementaciones futuras).
- [x] `evals/`: 3 casos sinteticos, reporte por campo y por version de prompt;
  `make eval` usa `FAKE_AI=1` si no hay clave. `make demo` genera texto, SVG y
  PDF verificados.
- [x] Tests de preprocesado, color, repeticion, segmentacion, extractor
  (votacion/reparacion/muestras invalidas), eval y schema.
- [x] `ruff` y `mypy` en verde; suite completa en verde.

**Limitacion honesta:** las imagenes de `evals/` son sinteticas, no fotos
reales; con `FAKE_AI=1` la precision de 1.0 mide el flujo y la votacion sobre
respuestas grabadas, no la vision del modelo. No habia `AI_API_KEY` para correr
la evaluacion real. Ver `DECISIONS.md` D011 y D012.

## Hito 6 — API y flujo web completo

Completado y verificado con tests y build de Next.js.

- [x] `engine/serialization.py`: conversion JSON de la IR completa (secciones,
  pasos, ops, medidas, materiales, advertencias y uniones) para API y
  almacenamiento.
- [x] `api/storage.py`: SQLite para patrones e imagenes; vencimiento de imagenes
  configurable con `IMAGE_TTL_HOURS`.
- [x] `api/ratelimit.py`: limite en memoria por IP, configurable con
  `RATE_LIMIT_PER_MINUTE`.
- [x] Endpoints: `POST /analyze` (multipart, preprocesado + extractor),
  `POST /pattern` (motor + simulador + texto), `GET /pattern/{id}`,
  `GET /pattern/{id}/pdf`, `GET /pattern/{id}/svg` y `GET /stitches`.
- [x] Validacion de subida (tipo/tamano), error 413/422/429/503/502 con mensajes
  claros; el patron solo se devuelve si el simulador pasa.
- [x] Web Next.js + TypeScript + Tailwind mobile-first: foto, confirmacion
  editable de atributos con confianza/incertidumbres, talle/hilo/muestra,
  vista de medidas/materiales/advertencias e instrucciones, descarga de PDF y
  esquema SVG.
- [x] Tests de API: flujo completo analyze -> pattern -> PDF/SVG, imagen
  invalida, variante imposible, patron inexistente y limite de tasa.
- [x] `npm run build` de la web en verde; `ruff`, `mypy` y suite completa en
  verde (424 tests).

**Limitacion honesta:** el flujo end-to-end se verifico con `FAKE_AI=1`; no
habia `AI_API_KEY` para probar la vision real. La web no se probo con
automatizacion de navegador (restriccion del entorno); se verifico el build de
produccion y la API por tests.

## Hito 7 — Redactor y crítico (IA #2)

Completado y verificado con tests; la IA real no se probó por falta de clave.

- [x] `ai/prompts/writer_v1.py`: prompt versionado que prohíbe cambiar o
  agregar números y recibe el texto canónico ya calculado.
- [x] `ai/writer.py`: reescritura con validación determinista de todos los
  números contra el texto canónico + la IR; reparación acotada (máx. 3
  intentos) y plantilla determinista como fallback garantizado.
- [x] `ai/prompts/critic_v1.py` y `ai/critic.py`: crítica informativa con foto,
  `GarmentSpec` y resumen del patrón; salida JSON validada con Pydantic,
  reparación acotada y fallback vacío. Nunca modifica el patrón.
- [x] Endpoints `POST /pattern/{id}/rewrite` y `POST /pattern/{id}/critique`;
  el segundo usa la imagen guardada y respeta su vencimiento.
- [x] Web: botones "Mejorar redacción" y "Revisar con IA"; las observaciones
  del crítico se muestran como advertencias separadas del patrón.
- [x] Tests de redactor (texto canónico, número inventado reparado, fallback,
  coma decimal, idioma) y crítico (fake, reparación de JSON, fallback).
- [x] `ruff`, `mypy`, suite completa (434 tests) y build de Next.js en verde.

**Limitación honesta:** la validación de números es por conjunto de valores
permitidos (texto canónico + IR); no detecta un número correcto usado en el
contexto equivocado. La garantía fuerte sigue siendo la plantilla determinista
y el simulador, no la IA. No había `AI_API_KEY` para probar el modelo real.

## Hitos 8-11

Pendientes.

## Hito 8 — Más familias de prenda

Completado con limitaciones declaradas; tests, `ruff`, `mypy` y suite completa
(1578 tests) en verde.

- [x] `engine/garments/flat.py`: pullover hombro caído, cardigan y chaleco en
  piezas planas rectangulares; piezas de cuerpo, mangas, puños, cuello y tapas
  de botones; uniones de costura declaradas y verificadas por el simulador.
- [x] `engine/garments/yoke.py`: pullover con canesú circular top-down,
  aumentos uniformes sin líneas de raglán, separación de cuerpo/mangas,
  disminuciones de manga y puños; el largo del canesú se acorta para mangas
  cortas.
- [x] `engine/garments/set_in.py`: pullover con manga encajada en piezas
  planas, sisa y copa simplificadas con disminuciones parejas en los bordes.
- [x] Despacho en `engine/garments/__init__.py` para las cinco familias y
  errores claros para técnicas/construcciones no soportadas.
- [x] `engine/text.py` detecta el montaje inicial de las piezas planas y no
  imprime “0 puntos”; los textos de canesú, sisa y copa usan claves i18n es/en.
- [x] `render/schematic.py` y `render/pdf.py` eligen esquema genérico para las
  familias nuevas; la API usa el despachador SVG genérico.
- [x] Tests nuevos: combinaciones de talle/hilo/ajuste, variantes de largo y
  escote, patrones golden, advertencias, texto/SVG/PDF y casos imposibles.

**Limitaciones honestas:** el canesú no genera el gráfico de jacquard; conserva
la paleta y emite `warning.colorwork_not_charted`. El cardigan no incluye
ojales ni forma de escote; el chaleco no lleva bandas ni forma de sisa. La
manga encajada usa una copa simplificada (`warning.set_in_simplified`) y no
modela hileras cortas. Las piezas planas se cosen y no son prendas sin
costuras. Ver `DECISIONS.md` D015.
