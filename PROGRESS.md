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

**Limitaciones honestas:** el canesú genera guardas de jacquard (fair isle)
con motivos geométricos originales (ver `DECISIONS.md`, "Guardas de jacquard
en el canesú circular"); intarsia y mosaico siguen sin gráfico
(`warning.colorwork_not_charted`). El cardigan no incluye
ojales ni forma de escote; el chaleco no lleva bandas ni forma de sisa. La
manga encajada usa una copa simplificada (`warning.set_in_simplified`) y no
modela hileras cortas. Las piezas planas se cosen y no son prendas sin
costuras. Ver `DECISIONS.md` D015.

## Hito 9 — Accesorios y piezas del hogar

Completado parcialmente, con limitaciones declaradas; tests, `ruff`, `mypy` y
suite completa (1982 tests) en verde.

- [x] `engine/garments/accessories.py`: gorro, bufanda, cuello circular,
  mitones, medias tubulares, chal rectangular y manta rectangular.
- [x] `PatternParams.dimensiones_cm`: medidas propias para accesorios (por
  ejemplo `head`, `width`, `length`, `palm`, `foot_length`), con defaults
  documentados como ASUNCIÓN.
- [x] Gorro: borde en elástico, cuerpo y corona con disminuciones repartidas
  hasta 4 puntos; bufanda, chal y manta como paneles rectangulares; cuello en
  tubo de elástico 2x2.
- [x] Mitones: piezas planas de mano y pulgar que se cosen; medias: tubo con
  puño, pierna, pie y puntera con disminuciones.
- [x] Render genérico de accesorios en SVG y PDF; textos es/en con secciones y
  advertencias propias.
- [x] Tests de todas las combinaciones talle/hilo, medidas propias,
  advertencias y texto/SVG/PDF.

**Limitaciones honestas:** no hay guantes con dedos; las medias no incluyen
talón (son tubulares); los mitones son piezas planas simplificadas; el chal y
la manta son rectangulares, no triangulares ni modulares. La bufanda en jersey
puede enrollarse. Ver `DECISIONS.md` D016.

## Hito 10 — Crochet

Completado con limitaciones declaradas; tests, `ruff`, `mypy` y suite completa
(2013 tests) en verde.

- [x] `engine/garments/crochet.py`: amigurumi en esfera, cilindro y cono;
  granny square simplificado y bufanda plana en crochet.
- [x] Amigurumi con anillo mágico, aumentos y disminuciones de 6 puntos por
  vuelta; formas elegidas con `spec.forma` (`straight` esfera, `boxy`
  cilindro, `a_line`/`curved` cono).
- [x] Medidas propias `diameter`, `height` y `size` en `dimensiones_cm`.
- [x] Punto base de crochet (`crochet_sc`, `crochet_hdc`, `crochet_dc`) y
  ganchillo por grosor de hilo.
- [x] Texto, SVG y PDF para crochet; apertura con anillo mágico o cadenas y
  remate específico de crochet.
- [x] Tests de todas las formas y grosores de hilo, medidas propias, texto,
  SVG y PDF.

**Limitaciones honestas:** el granny square es un cuadrado sólido simplificado,
no el motivo clásico de grupos; no hay cambios de color ni uniones de módulos;
la densidad de crochet usa la tabla de referencia de dos agujas editable. El
amigurumi no incluye relleno ni detalles de ensamblaje. La categoría **Manta**
en crochet se despacha como un módulo granny square: no calcula una manta
completa ni la unión de módulos. Ver D017.

## Hito 11 — Pulido

Completado con las limitaciones de despliegue indicadas; tests, `ruff`, `mypy`
y build de la web en verde.

- [x] API: cabeceras de seguridad, compresión GZip, CORS configurable por
  `CORS_ORIGINS`, límite de tasa también en `/pattern`, caché privada para
  PDF/SVG.
- [x] Web: contador de vueltas por sección en modo tejiendo, botones
  anterior/siguiente/reiniciar y Wake Lock opcional.
- [x] Web: guardar, cargar y borrar proyectos en localStorage, incluyendo el
  patrón, el texto y la posición del contador.
- [x] Web: medidas propias por categoría, incluyendo accesorios y crochet.
- [x] Accesibilidad: enlace para saltar al contenido, `aria-current` en pasos,
  región de estado `aria-live`, `aria-busy`, foco visible en todos los
  controles, reducción de movimiento y mayor contraste.
- [x] Rendimiento: build standalone de Next, compresión y memoización del
  listado de vueltas.
- [x] Despliegue: `Dockerfile` de API, `web/Dockerfile`, `docker-compose.yml`,
  `.dockerignore` y `docs/despliegue.md`.
- [x] `make examples` ahora funciona con `scripts/generate_examples.py`.
- [x] Tests de cabeceras de seguridad y suite completa.

**Limitaciones:** no hay autenticación ni proyectos compartidos entre
dispositivos; SQLite es para una instancia pequeña; el Wake Lock depende del
navegador; no se ejecutó Playwright e2e en este entorno.

## Correcciones posteriores al hito 11

- [x] La pantalla de medidas distingue prendas de accesorios: el talle solo se
  muestra para pullover, cardigan y chaleco; los accesorios usan únicamente sus
  medidas. Se ocultan escote, largos y ajuste cuando no aplican.
- [x] La pantalla de confirmación limita las técnicas a las soportadas por la
  categoría y normaliza la selección al cambiar de categoría; las categorías
  sin familia se marcan antes de generar.
- [x] Bolso rectangular soportado en dos agujas/circular y crochet; pieza plana
  genérica para fotos no reconocidas. Se declaran las limitaciones (sin asas,
  forro, cierre ni módulos unidos).
- [x] Mitones: de cuatro secciones repetidas a dos piezas reutilizables (mano y
  pulgar), con nota de armado; esquema SVG y PDF con forma de mitón en lugar de
  un rectángulo.
- [x] Los textos de accesorios ya no muestran un talle que no aplica; se
  mantiene el talle solo en prendas.
- [x] Mensajes de error de la web traducidos para técnicas, categorías y
  proporciones no soportadas.
- [x] Tests nuevos de bolso, pieza plana, mitones y crochet; 2136 tests en
  verde, `ruff`/`mypy` limpios y build de la web en verde. El SVG/PDF del mitón
  se verificó visualmente con una silueta y el pulgar adjunto.
- [x] Esquema del bolso reemplazado por un dibujo técnico con cuerpo, textura de
  tejido, línea de doblez, costuras y asas punteadas marcadas como opcionales
  (no incluidas). Verificado en SVG y PDF para dos agujas y crochet.


## Corrección de clasificación: cuadrado de crochet

- [x] La foto de un cuadrado de crochet se clasificaba como bolso. Se agregó
  `granny_square` al esquema y la UI, y el prompt `extractor-v2` prohíbe
  clasificar un panel cuadrado plano como bolso si no hay asas, abertura o
  volumen.
- [x] Verificado con la API real: la misma foto ahora devuelve
  `categoria=granny_square`, `tecnica=crochet`, `construccion=modules`.
- [x] El granny square tiene esquema SVG/PDF propio (cuadrado, textura, rondas,
  borde y medidas) y la UI pide el lado del cuadrado.
- [x] Tests de categoría, prompt, esquema y PDF; suite completa en verde.

## Mejora de presentación: texto comercial y diagramas de piezas (2026-11-10)

Objetivo: que el patrón se lea como uno comprado y que el esquema sea un
diagrama útil (no una silueta decorativa), sin romper la regla “la IA
interpreta; el código calcula” (ningún número ni dibujo generado por IA).

- [x] `engine/blocks.py`: capa de bloques tipados (compartida por texto y PDF)
  que comprime vueltas de forma **solo presentacional** —rangos de vueltas
  idénticas y ciclos con progresión (relleno enmascarado, nota que se repite),
  anclados en la vuelta con nota y con conteo final declarado— sin alterar la
  IR. Glosario automático de las abreviaturas usadas.
- [x] `engine/text.py`: instrucciones siempre abreviadas con glosario (estilo
  patrón comercial), independiente del nivel; firma de `render_pattern_text`
  intacta. Raglán demo: 438 → ~115 líneas.
- [x] `render/draw.py` + `render/schematic.py`: diagramas de **piezas
  paramétricos derivados de la IR** (perfil de puntos por sección, medidas y
  gauge): contorno según la progresión de puntos, cotas y conteos
  `inicio → fin`, por familia (paneles/accesorios y conjunto de piezas en
  prendas). Un único SVG para web y PDF; determinista.
- [x] `render/pdf.py`: formato comercial (portada, esquema embebido vía
  svglib, tablas de materiales/medidas, glosario, secciones) renderizado desde
  los mismos bloques. `pyproject.toml` declara `svglib>=1.5` con fallback si
  no está disponible.
- [x] Commits: `daf4489` (texto/bloques), `daa06d9` (siluetas, sustituido),
  `184fe90` (PDF), `cd0fe4d` (diagramas de piezas). Demo regenerada.
- [x] Verificación: **2136 tests** en verde, `ruff` limpio, `mypy` estricto en
  `engine/` limpio, `make demo` OK. (3 aserciones de dibujo ajustadas en
  `tests/test_accessories.py`, `tests/test_flat.py`, `tests/test_crochet.py`).

**Limitaciones:** contornos de prenda simplificados por familia (sin
escote/sisa/copa finos donde la IR no lo expone); en este entorno `svglib` no
se instaló en el venv, así que el PDF puede generarse sin el esquema embebido
(hay fallback; con `svglib` instalado se incrusta). La web aún no refleja la
misma maquetación jerárquica que el PDF. Ver `DECISIONS.md` D021.

## Calidad de mercado (2026-11-11)

Diagnóstico y rumbo en `DECISIONS.md` D022 y D023.

- [x] Correcciones: elástico como repetición (`*1 der, 1 rev*`), densidad de
  crochet CYC por punto (antes usaba la de dos agujas y las medidas eran
  falsas), claves i18n crudas en el PDF (más un test que lo impide), vuelta de
  separación de mangas explícita, granny square real en redondo.
- [x] Escalado: sisa del raglán con la tabla (antes 25 → 14 cm entre M y L),
  mangas con intervalo único. Tests de propiedades.
- [x] Todos los talles en un patrón con notación `a (b, c)` y prueba de ida y
  vuelta por talle.
- [x] Documento de 14 secciones y PDF comercial (talle resaltado, A4/Carta,
  imprimir, marcadores, página X de Y), esquema de pullover con cotas por
  letra, diagrama de granny por vueltas.
- [x] CLI `make patron ARCHIVO=examples/sueter-raglan.yaml TALLE=M` y 4
  ejemplos.
- [x] Verificación: **2255 tests** (15 omitidos: familias no soportadas por
  técnica), `ruff` y `mypy` en verde, `tsc` de la web en verde.

**Pendiente (no hecho):** reproducir motivos complejos de la foto (capa de
diseño); evaluaciones con fotos reales; gráficos de calado/jacquard en el
PDF; esquemas con letras para cardigan, chaleco y accesorios; la web todavía
muestra el texto de un talle (el PDF ya trae todos).

## Texturas y prendas en piezas (2026-11-11, continuación)

- [x] Paneles de textura (trenzas, calados, bodoques, nido de abeja) en
  raglán, canesú circular, hombro caído, cárdigan y chaleco, con gráfico en
  el PDF (recuadro de repetición y numeración de puntos).
- [x] Manga encajada reescrita con construcción clásica (sisa al ancho de
  espalda, copa estándar, operación "cerrar pts" simulada).
- [x] Jersey plano real (revés al revés) y elástico en el borde inferior de
  las piezas; elásticos planos del catálogo corregidos.
- [x] Web: texturas en español, con botón para quitarlas.
- [x] Verificación: **2305 tests**, `make lint` y `tsc` en verde.

**Pendiente:** panel en manga encajada; escote con forma en piezas planas;
evaluación con fotos reales; capa de diseño para motivos complejos.

## Pendientes resueltos (2026-11-11, continuación 2)

- [x] Panel de textura en manga encajada (sisa con cierre y disminuciones).
- [x] Escote redondo en manga encajada, hombro caído y chaleco.
- [x] Compensación del ancho de las trenzas con la muestra medida (web, CLI).
- [x] `make eval-fotos`: IA por campo + rúbrica del patrón; probado con la IA
  real sobre la imagen de prueba.
- [x] Verificación: **2320 tests**, `make lint` y `tsc` en verde.

**Pendiente (resuelto en la continuación 3, salvo las fotos):** cargar 20–30
fotos con derechos claros en `evals/photos/` y correr `make eval-fotos`.

## Cualquier tejido, varias fotos y capa de diseño (2026-11-11, continuación 3)

- [x] Hasta 4 fotos por análisis y aviso de calidad medido (D026).
- [x] Ninguna combinación de la IA sin patrón: ruteo a la familia más
  cercana con advertencia; prendas, gorro, cuello y chal de crochet (D026).
- [x] Escote del cárdigan en V o redondo (D027).
- [x] Capa de diseño para motivos radiales de crochet (D028); probado con la
  IA real sobre la imagen de prueba.
- [x] Verificación: **2411 tests**, `make lint` y `tsc` en verde.

**Pendiente:** fotos reales para `make eval-fotos`; escote en V de pullover;
guantes con dedos; jacquard como gráfico de color; formas de pétalo
(picos, arcos de cadenas) en los motivos.

## Formato comparado con patrones comerciales (2026-11-12)

- Hecho: gráfico de símbolos de crochet (motivos, granny), esquema por
  letras del cárdigan y del chaleco, texto del escote en V en ciclos,
  elástico 2x2 en todos los talles, tapas de botones izquierda/derecha,
  lectura del gráfico en plano. Ver D029.
- Verificado: suite completa, `make lint` en verde.
- Pendiente: retícula de colores (jacquard), fotos reales para `make eval-fotos`.

## Comparación con patrones de internet (2026-11-16)

- [x] Canesú circular legible en todos los talles (6 vueltas de aumento). D031.
- [x] Gorro de dos agujas: respeta el elástico, corona en el elástico o en
  gajos, cierre pasando la hebra; esquema como silueta con textura. D031.
- [x] Extractor v4 (agujas vs crochet por la superficie) y descripción libre
  antes de analizar. Verificado con la IA real: el gorrito de elástico ahora
  sale de dos agujas; el osito (foto chica, lana peluda) sigue saliendo crochet
  y se corrige con la descripción o en la confirmación.
- [x] Foto de la persona en la portada del PDF.
- [x] Guía humana (segunda pasada de IA, sin números, validada). Probada con
  la IA real sobre el gorro.
- [x] Amigurumi en piezas (agujas y crochet). D033.
- [x] Gráfico de jacquard del canesú. D032.

## Amigurumi en piezas, crochet y dos agujas (2026-11-16)

- Hecho: el amigurumi deja de ser una bola. Ahora es un juguete en piezas
  (cabeza, cuerpo, 2 brazos, 2 piernas y, según la figura, 2 orejas, hocico y
  cola) con relleno y armado calculados: posición de ojos, orejas, brazos,
  piernas y cola en vueltas/hileras reales (`Pattern.finishing`).
- Plantillas `bear`, `bunny`, `cat` y `generic` (`GarmentSpec.figura`, la
  elige la IA; sin figura, muñeco sin orejas). Escalan con la altura
  sentado (`dimensiones_cm["height"]`, o una por defecto según el hilo).
- Crochet: espiral desde anillo mágico, ±6 pts por vuelta. Dos agujas: en
  plano y en jersey desde 8 pts, ±8 por hilera del derecho (kfb, 2pjd),
  extremos fruncidos y costura colchonero. Ya no se fuerza crochet.
- Esquema del muñeco armado (`render/toy.py`) con rótulos por pieza; arregla
  la cota "Ancho" que pisaba el dibujo.
- Verificado: todas las plantillas x grosores x técnicas, alturas de 0,5 a 3
  veces la de referencia (hypothesis), golden de osito en crochet y en dos
  agujas; suite completa y `make lint` en verde. Ver D033.
- Limitaciones: un solo color; sin ropa, pelo ni hocico para gato o conejo;
  las proporciones son de plantilla, no medidas de la foto.

## Idiomas, PDF ajustable y dibujo de aumentos (2026-11-16, D035)

- Hecho: patrones en es/en/fr/de/it (mismos números, test); interfaz web en los cinco idiomas, inglés por defecto; último paso con idioma, talle, hilo, papel, guía, fotos de portada y "Diseñado por"; PDF con todas las fotos, esquema y gráficos primero, sin legales; dibujo de aumentos del amigurumi al crochet.
- Pendiente: revisión de las traducciones por tejedoras nativas (fr/de/it); el extractor de IA sigue devolviendo sus observaciones en español; no se probó la interfaz en un navegador real.

## Hogar con cálculo propio (2026-11-17, D038)

- Hecho: posavasos, individual, agarradera, paño y carpetita (círculo,
  cuadrado, rectángulo, óvalo al crochet); fundas de mate (se cierra hacia la
  boca), termo (con correa), vaso y botella (base cerrada, abrazan); fundas de
  celular, anteojos, cartuchera (cierre) y notebook (solapa y botón); canasto
  (base redonda, ovalada o rectangular, asas); almohadón (dos caras al crochet,
  sobre en agujas) y alfombra. Crochet y dos agujas, esquema en 5 idiomas, PDF.
- Verificado: hypothesis sobre subtipos × técnicas × grosores × medidas
  propias; círculos con aumentos parejos, óvalos con lados rectos y extremos
  iguales, cuadrados con lados iguales, asas opuestas; golden a mano de funda
  de mate y posavasos en DK. Suite y `make lint` en verde.
- Pendiente: óvalo en agujas (se entrega rectángulo, con aviso); taza con
  asa (la funda es para vasos sin asa); el dibujo punto por punto de los
  círculos de crochet (hoy solo esquema); medidas por defecto sin validar con
  una tejedora.
