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

## D009 — Semantica de efectos del simulador

- **Decision:** el simulador usa la tabla de `engine/stitches/kinds.py` como
  unica fuente de verdad. `m1l`/`m1r`/`yo`/`ch` consumen 0 y producen 1;
  `kfb` y `crochet_inc` consumen 1 y producen 2; las disminuciones consumen 2 y
  producen 1; el anillo magico produce 6 puntos.
- **Motivo:** modela como se teje realmente: un aumento levantado o una lazada
  no consumen un punto existente, se intercalan entre puntos. Los generadores
  deben incluir los puntos tejidos de la vuelta ademas de los aumentos.
- **Consecuencia:** `build_step` falla si la suma de consumos no coincide con
  los puntos disponibles; el simulador vuelve a comprobarlo sobre la IR final.
- **Conteos declarados:** una seccion puede declarar
  `meta.expected_increases` y `meta.expected_decreases`; el simulador suma los
  aumentos/disminuciones reales (no el delta neto) y los compara.

## D010 — Supuestos del raglan top-down

- **Decision:** el primer generador de prenda usa raglan compuesto: los
  aumentos de cuerpo y de manga pueden ocurrir en la misma vuelta o en
  vueltas separadas; la axila se monta al separar las mangas.
- **ASUNCION:** canesu, cuerpo y mangas en jersey. Si se pide otro punto base
  se advierte y se usa jersey; las texturas y el colorwork se integraran en
  hitos posteriores.
- **ASUNCION:** 4 cm de axila, 4 cm de holgura de brazo, 4 cm de ruedo y puño,
  3 cm de cuello (8 cm en cuello alto/embudo). Tolerancia de medidas 2.5 cm
  (1 cm en largos).
- **ASUNCION:** si el canesu estandar (aumentos en vueltas alternas) no deja
  lugar para el largo de manga pedido, se aumenta en cada vuelta y se advierte.
  Esto permite mangas cortas y tres cuartos sin hileras cortas.
- **ASUNCION:** escotes V, barco, cuadrado y cuello alto cambian el contorno
  de montado y el borde, no la geometria del canesu. Sin mangas se rechaza:
  pertenece a la familia chaleco.
- **Motivo:** mantener el primer generador verificable y explicito; toda
  limitacion se declara en el patron y en `PROGRESS.md`.
- **ASUNCION:** una manga larga que no alcanza el contorno de muneca dentro de
  la tolerancia se rechaza con `ImpossibleProportionsError`; en mangas corta y
  tres cuartos el contorno de puno no se compara contra la muneca (el largo
  termina antes) y se advierte si las disminuciones no alcanzan.

## D011 — Extractor con votacion y evaluacion fake

- **Decision:** el extractor ejecuta N=3 muestras con temperatura 0.4, valida
  cada salida con `GarmentSpec`, repara como maximo 2 veces devolviendo el error
  y consolida por mayoria campo por campo. La confianza es el acuerdo entre
  muestras; los desacuerdos se agregan a `incertidumbres`.
- **Decision:** si una muestra sigue invalida se descarta y se usan las demas;
  si ninguna es valida, falla con `ExtractionError`.
- **Decision:** se intenta `response_format` JSON schema; si el endpoint lo
  rechaza, se reintenta sin el y se valida igual contra Pydantic.
- **Decision:** con `FAKE_AI=1` las respuestas son deterministas y la eval mide
  el flujo/votacion, no la vision real. Se informa como tal en el reporte.
- **Motivo:** el modelo es barato pero poco fiable; la redundancia y la
  validacion son la garantia, no la confianza en una sola respuesta.

## D012 — Umbrales de vision clasica

- **ASUNCION:** cuantizacion k-means en Lab con `random_state=0`, muestreo
  deterministico de hasta 20 000 pixeles y filtro de mediana 3x3 para limpiar
  etiquetas aisladas.
- **ASUNCION:** deteccion de repeticion por diferencia media de la imagen
  desplazada; el periodo de mayor score entre `min_period` y un tercio del
  lado. Es una aproximacion, no un detector de motivos de tejido.
- **ASUNCION:** segmentacion por color de borde con umbral 42 y componente
  conexa mas grande; rembg/SAM quedan detrás de la misma interfaz.
- **ASUNCION:** la eval usa imagenes sinteticas hasta incorporar fotos reales
  con derechos claros.

## D013 — API, persistencia y flujo web

- **Decision:** la API usa SQLite para patrones e imagenes. Cada patron se
  guarda serializado en JSON junto con el texto es/en; las imagenes tienen
  vencimiento configurable (`IMAGE_TTL_HOURS`) y se guardan solo para trazabilidad
  y posibles reprocesos, no se sirven publicamente.
- **Decision:** `engine/serialization.py` es la unica conversion IR <-> JSON;
  la API, la web y el almacenamiento consumen ese formato. Al deserializar se
  reconstruyen los tipos del motor (`YarnWeight`, `Op`, `Step`, etc.), no se
  trabaja con diccionarios sueltos.
- **Decision:** `POST /pattern` vuelve a pasar el patron por el simulador antes
  de guardarlo; si falla, responde 422 y no persiste nada. El texto se genera
  deterministicamente en es/en desde la IR.
- **Decision:** limite de tasa en memoria por IP (`RATE_LIMIT_PER_MINUTE`),
  subida maxima configurable (`MAX_UPLOAD_MB`) y validacion de imagen con el
  mismo preprocesado de vision. Para produccion con varias instancias habria
  que mover el limite a un almacenamiento compartido.
- **Decision:** la web es Next.js + TypeScript + Tailwind, mobile-first, con
  confirmacion editable de atributos y confianza visible. La API se configura
  con `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- **Motivo:** cerrar el flujo foto -> confirmacion -> PDF sin agregar
  infraestructura; SQLite y el limite en memoria son suficientes para el
  desarrollo y se pueden reemplazar por Postgres/Redis sin cambiar el contrato
  de la API.
- **Limitacion:** el flujo se probo con `FAKE_AI=1`; no habia clave para la
  vision real. La web se verifico con `npm run build`, no con automatizacion de
  navegador.

## D014 — Redactor y critico con validacion de numeros

- **Decision:** el redactor recibe el texto canonico completo (ya calculado y
  verificado) y solo puede reescribirlo. La validacion extrae todos los numeros
  de la respuesta y rechaza cualquiera que no aparezca en el texto canonico o
  en la IR (medidas, conteos, material, densidad, etc.).
- **Decision:** si tras 3 intentos la respuesta sigue con numeros no permitidos,
  se devuelve la plantilla determinista. El texto del patron siempre existe,
  aunque la IA falle.
- **Decision:** el critico recibe la foto, el `GarmentSpec` y un resumen del
  patron; devuelve `observaciones` y `riesgos` en JSON validado. Sus salidas son
  solo informativas y nunca se aplican automaticamente al patron.
- **Decision:** ambos roles usan el mismo modelo configurable, pero llamadas y
  prompts separados; `AI_MODEL_WRITER` y `AI_MODEL_CRITIC` permiten asignar
  modelos distintos sin tocar codigo.
- **Limitacion:** la validacion por conjunto no detecta un numero permitido
  usado en el contexto equivocado. La red de seguridad fuerte es la plantilla
  determinista y el simulador. Se documenta en `PROGRESS.md`.
- **Motivo:** cumplir "la IA interpreta; el codigo calcula" incluso en la
  redaccion, sin bloquear la entrega del patron si el modelo se porta mal.

## D015 — Familias planas, canesú circular y manga encajada

- **Decisión:** hombro caído, cardigan y chaleco se generan como piezas planas
  rectangulares en `engine/garments/flat.py`. No se modelan sisas, escotes ni
  ojales en esta versión; las limitaciones se declaran con advertencias
  (`warning.flat_panels`, `warning.no_neck_shaping`, `warning.no_buttonholes`,
  `warning.vest_armhole`). El cardigan usa espalda de medio contorno y dos
  delanteros de un cuarto cada uno, para que la costura lateral cierre.
- **Decisión:** el canesú circular se genera con aumentos uniformes repartidos
  (`engine/distribution.py`), sin líneas de raglán; la profundidad objetivo es
  la sisa de la tabla + 4 cm y se acorta para mangas cortas. El jacquard no se
  convierte en gráfico en esta versión: se conserva la paleta y se advierte
  (`warning.colorwork_not_charted`).
- **Decisión:** la manga encajada se simplifica con disminuciones parejas en
  los bordes de la sisa y de la copa, usando las mismas vueltas de sisa en
  cuerpo y manga. Se declara `warning.set_in_simplified`; no se modela una
  curva completa de copa ni hileras cortas.
- **Decisión:** el texto detecta el montaje inicial de una sección plana y el
  render tiene un despachador genérico (`render_schematic_svg`); el PDF elige
  el dibujo según `meta.family`.
- **Motivo:** ampliar familias sin inventar números ni prometer construcciones
  que el motor todavía no verifica. El simulador valida conteos, consumos,
  largos y uniones de costura; las limitaciones quedan visibles para la
  persona tejedora.

## D016 — Accesorios y dimensiones propias

- **Decisión:** `PatternParams` incorpora `dimensiones_cm` para medidas que no
  pertenecen a la tabla de talles corporal (`head`, `width`, `length`, `palm`,
  `foot_length`, `thumb`, etc.). Si una clave no se informa, se usa un default
  documentado como ASUNCIÓN.
- **Decisión:** gorro, bufanda, cuello, mitones, medias, chal y manta viven en
  `engine/garments/accessories.py`. Las piezas planas usan el mismo esquema
  genérico de SVG/PDF que las familias planas.
- **Decisión:** el gorro se genera en redondo con corona de 4 disminuciones por
  vuelta hasta 4 puntos; las medias son tubulares, sin talón; los mitones son
  cuatro piezas planas (mano y pulgar delantero/trasero) que se cosen; el chal
  y la manta son rectangulares. (Actualizado por D019: dos secciones
  reutilizables, mano y pulgar, con nota de armado).
- **Motivo:** cubrir accesorios con números deterministas y verificables sin
  prometer construcciones que todavía no están modeladas. Las limitaciones se
  declaran con advertencias visibles en el patrón.
- **Limitación:** no se implementaron guantes con dedos, talón de media,
  mitones tubulares ni chal triangular/modular. Quedan para una iteración
  posterior.

## D017 — Crochet: amigurumi y piezas planas

- **Decisión:** la técnica `crochet` se despacha antes que las familias de dos
  agujas. Amigurumi usa anillo mágico y aumentos/disminuciones de 6 puntos por
  vuelta; la forma se deriva de `spec.forma` (`straight` = esfera, `boxy` =
  cilindro, `a_line`/`curved` = cono).
- **Decisión:** el granny square se genera como un cuadrado sólido en punto
  alto, no como el motivo clásico de grupos; se declara con
  `warning.granny_simplified`. Una bufanda en crochet se genera como panel
  plano rectangular.
- **Decisión:** las medidas de crochet se toman de `dimensiones_cm` (`diameter`,
  `height`, `size`, `width`, `length`) y la densidad de la tabla de referencia
  por grosor de hilo, editable con `densidad`; se advierte que es una
  referencia de dos agujas (`warning.crochet_gauge`).
- **Motivo:** entregar amigurumi y piezas planas verificables sin prometer
  cambios de color, módulos unidos ni el motivo clásico de granny square.
- **Limitación:** no hay patrones de prendas en crochet, cambios de color,
  ensamblaje de módulos ni relleno/detalles de amigurumi.

## D018 — Persistencia de proyectos, contador y despliegue

- **Decisión:** el proyecto del usuario se guarda en `localStorage` del
  navegador (patrón serializado, texto y posición del contador). El patrón
  también queda en SQLite por id para PDF/SVG. No se agregan cuentas ni
  autenticación en esta entrega.
- **Decisión:** el contador de vueltas es una herramienta de lectura: recorre
  los pasos ya verificados y no altera la IR ni los números. Wake Lock es
  opcional y best-effort.
- **Decisión:** la API expone CORS configurable, cabeceras de seguridad,
  compresión y límite de tasa en `/pattern`; la web se construye en modo
  standalone y se despliega con Docker Compose.
- **Motivo:** cerrar el flujo de uso real sin introducir autenticación ni
  sincronización que no estaban en el alcance.
- **Limitación:** los proyectos no se comparten entre dispositivos; SQLite no
  escala a varias réplicas; el e2e de Playwright no se ejecutó por falta de
  navegadores instalados.

## D019 — Medidas por categoría, bolso/pieza plana y mitones

- **Decisión:** la UI de medidas muestra talle y holgura solo para prendas
  (pullover, cardigan, chaleco). Para accesorios, crochet y piezas del hogar
  muestra únicamente las medidas de esa categoría. La confirmación también
  oculta escote, largos y ajuste cuando no aplican.
- **Decisión:** las técnicas ofrecidas se limitan por categoría
  (`supportedTechniques`) y se normalizan al cambiar de categoría. Las
  categorías sin familia se bloquean antes de llamar al motor.
- **Decisión:** bolso y `otra prenda` se generan como paneles rectangulares
  (en dos agujas/circular y en crochet) con una advertencia que declara que no
  se modelan asas, forro, cierre ni unión de módulos. La pieza plana es el
  fallback honesto para una foto no reconocida. El esquema del bolso es un
  dibujo técnico (cuerpo, textura, doblez y asas punteadas opcionales), no un
  rectángulo vacío; las asas se marcan como no incluidas.
- **Decisión:** los mitones se generan como dos secciones reutilizables (mano y
  pulgar), con una nota que indica hacer dos piezas de cada una y coserlas. El
  SVG/PDF dibuja una silueta de mitón con el pulgar, en lugar del rectángulo
  genérico. Esto reemplaza las cuatro secciones repetidas de D016.
- **Motivo:** evitar errores 422 evitables, no pedir talles a quien teje un
  cuadrado y que el PDF represente la prenda que se va a tejer.
- **Limitación:** el bolso no tiene asas/forro/cierre; la pieza plana no infiere
  una prenda; los mitones siguen siendo piezas planas cosidas, no tejidos en
  redondo con pulgar integrado.


## D020 — Cuadrado de crochet vs bolso y prompt extractor v2

- **Problema:** una foto de un cuadrado de crochet con motivo radial se
  clasificaba como `bag` con confianza 1.0. El modelo justificaba la elección
  por la forma cuadrada, aunque no había asas, abertura ni volumen.
- **Decisión:** agregar la categoría `granny_square` para cuadrados/módulos de
  crochet y hacer explícita la diferencia en el prompt `extractor-v2`: un
  bolso requiere abertura, volumen y asas/correas; un panel cuadrado plano es
  `granny_square` (crochet), `other` (panel plano) o `blanket` (manta), nunca
  `bag` solo por su forma.
- **Decisión:** la UI ofrece `Cuadrado / granny square`, limitado a crochet, con
  la medida del lado; el motor lo despacha a la familia `granny_square`.
- **Decisión:** el SVG/PDF del granny square muestra un cuadrado técnico con
  textura, rondas, borde y medidas, rotulado como motivo simplificado.
- **Motivo:** evitar que un cuadrado se convierta en un bolso con asas y que el
  PDF muestre una pieza que la foto no respalda.
- **Limitación:** el generador produce un cuadrado sólido simplificado; no
  reproduce el motivo floral de la foto. La advertencia se muestra en el texto
  y el esquema se rotula como simplificado.

## D021 — Presentación determinista: instrucciones comerciales y diagramas de piezas (2026-11-10)

- **Problema:** las instrucciones listaban cada vuelta sin comprimir (poco
  legible) y el esquema era una silueta geométrica genérica de poca utilidad.
- **Decisión (sin IA en el dibujo):** el esquema se genera por código a partir
  de la IR verificada, no con un modelo generativo ni con un LLM que “dibuje”.
  Motivo: los números/forma deben ser verificables y coherentes con el
  simulador; un modelo de imagen inventa y un LLM que emite SVG no garantiza
  geometría correcta. La IA ya cumplió su rol al interpretar la foto (extractor);
  mejorar el dibujo es un problema de render determinista, no de prompt/modelo
  de imagen.
- **Decisión:** `engine/blocks.py` introduce bloques tipados compartidos por
  texto y PDF. La compresión de vueltas es **solo presentacional** (no altera
  la IR ni los conteos): rangos de vueltas idénticas y ciclos con progresión
  (repeticiones de relleno enmascaradas, nota que se repite), anclados en la
  vuelta con nota y declarando siempre el conteo final. Se emiten abreviaturas
  con glosario automático de las usadas. `render_pattern_text` conserva su
  firma y la validación de números del redactor IA sigue comparando contra la
  IR/texto canónico.
- **Decisión:** `render/schematic.py` dibuja **diagramas de piezas paramétricos**
  derivados del perfil de puntos por sección (`step.stitch_count_end`/gauge) y
  de las medidas: contorno según la progresión de puntos, cotas y conteos
  `inicio → fin`, por familia. Un único SVG sirve a web y PDF.
- **Decisión:** `render/pdf.py` compone un PDF estilo patrón comercial (portada,
  esquema embebido, tablas, glosario, instrucciones) desde los mismos bloques.
  El esquema se embebe con `svglib` (`pyproject.toml`); si no está instalado,
  el PDF se genera sin el dibujo embebido (fallback explícito, no falla).
- **Limitaciones:** el contorno de prendas es una representación simplificada
  por sección/familia (no deriva curvas finas de escote/sisa/copa donde la IR
  no expone esa geometría); la web no maquetó aún con la jerarquía de
  bloques/PDF. Afinar contornos y cartas de punto es trabajo determinista
  posterior.
- **Verificación:** 2136 tests, `ruff` y `mypy engine` en verde; demo
  regenerada. Commits `daf4489`, `daa06d9`, `184fe90`, `cd0fe4d`.

## D022 — Diagnóstico de calidad y rumbo: estándar de mercado primero (2026-11-11)

- **Diagnóstico:** el resultado decepcionaba por causas de concepto y de motor,
  no por la IA. (1) El motor usa solo categoría y medidas: lo que la IA ve
  (`texturas`, motivo) no se usa en ningún generador, así que mejorar el
  modelo o el prompt no cambia el PDF. (2) Había errores de corrección que los
  tests no veían: elástico como `40 d, 40 r`, densidad de dos agujas en
  crochet (medidas falsas), separación de mangas incompleta, claves i18n
  crudas en el PDF, granny "square" tejido como rectángulo de hileras.
  (3) El PDF está lejos de la especificación de mercado (un talle, faltan
  secciones). (4) No hay evaluación de calidad de salida, solo coherencia.
- **Decisión de producto:** el objetivo de esta etapa es un **patrón base de
  calidad comercial inspirado en la foto**, que declara con claridad lo que no
  reproduce. Reproducir motivos complejos (pétalos, puffs, relieves) requiere
  una capa de diseño (IA describe estructura con vocabulario cerrado, el
  código calcula y verifica); queda como etapa posterior, después de que el
  estándar de salida esté resuelto.
- **Orden:** correcciones (hecho, commits `4a170ff`..`6810406`) → todos los
  talles en un solo patrón con notación `a (b, c)` → PDF con las 14 secciones
  de la especificación → evaluación de salida → capa de diseño.
- **Alternativas descartadas:** cambiar de modelo de visión primero (no
  cambia la salida mientras el motor ignore los atributos); generar texto o
  números con LLM (viola "la IA interpreta, el código calcula").

## D023 — Patrón de mercado: todos los talles, documento de 14 secciones y PDF (2026-11-11)

- **Todos los talles en un patrón (`engine/multisize.py`):** cada talle se
  genera y pasa por el simulador por separado. Solo la presentación se
  combina: se alinean las líneas por su forma (texto sin números) y los
  números se escriben `a (b, c)`. Las líneas que existen solo en algunos
  talles van como "Solo talles L, XL: ... 7 (14) ...". Garantía testeada en
  las 6 familias de prenda: proyectar el texto combinado a un talle
  reproduce exactamente el texto de ese talle.
  *Alternativa descartada:* un motor "multi-talle" que calcule todos los
  talles a la vez; duplicaba la lógica y debilitaba el simulador.
- **Comparar talles reveló errores de escalado que el simulador no podía
  ver** (verifica contra objetivos que calcula el mismo generador): sisa del
  raglán de 25 → 14 cm entre M y L, y disminuciones de manga con intervalos
  irregulares. Se corrigieron en el motor (esquema estándar de raglán con
  F/S/P vueltas; intervalo único de manga) y hay tests de propiedades.
- **Notación comercial:** etiquetas relativas en dos agujas ("Vuelta
  siguiente", "Repetir las últimas 5 vueltas 13 veces más"), "todos los pts
  al der", aumentos de raglán con marcadores, "der hasta quedar 3 pts",
  puntos de control de medida; crochet mantiene las vueltas numeradas.
  Abreviaturas ES alineadas con la especificación (der, rev, 2pjd, laz,
  desl, pts, mc), tildes y modo infinitivo.
- **Documento (`engine/document.py`) y PDF (`render/pdf.py`):** las 14
  secciones de la especificación, nivel CYC derivado de las técnicas
  usadas, tabla de talles con letras A, B, C... iguales a las del esquema,
  aguja/ganchillo en mm y US (tablas CYC verificadas), página X de Y,
  marcadores del PDF, A4/Carta, versión para imprimir y talle resaltado.
- **Portada sin foto:** la foto de entrada suele ser de un tercero
  (Instagram), así que no se publica en el PDF; la portada usa el esquema.
  Si más adelante la persona sube la foto de su propia prenda terminada,
  puede ir en la portada.
- **CLI:** `scripts/generar_patron.py` (`make patron`) toma un YAML/JSON con
  `spec` + `params`, no el YAML de diseño libre de la especificación. Motivo:
  el producto parte de una foto y el motor necesita `GarmentSpec`, no texto
  de instrucciones escrito a mano. Ver próximos pasos en `HANDOFF.md`.

## D024 — Las texturas de la foto llegan al patrón; correcciones en prendas en piezas (2026-11-11)

- **Panel de textura (`engine/garments/panels.py`):** trenzas, calados,
  bodoques y nido de abeja se tejen como un panel centrado (2 rev de borde)
  en espalda y delantero: raglán y canesú circular en redondo; hombro caído,
  cárdigan y chaleco en plano. Los motivos no cambian el conteo, así que el
  simulador verifica cada vuelta igual; en la IR el panel es un `Repeat`.
  El texto usa marcadores y remite al gráfico (sección Gráficos del PDF).
  *Alternativa descartada:* textura en toda la prenda, que obliga a ajustar
  todos los conteos al múltiplo del motivo y rompe aumentos y disminuciones.
  *Pendiente:* manga encajada (la sisa corta el panel) y compensar el ancho
  que las trenzas quitan (hoy se avisa: muestra sobre el panel).
- **Revisar familias en piezas encontró errores de tela y de forma**, no de
  presentación: jersey plano tejido todo al derecho (santa clara), elásticos
  planos que tejían arroz o damero, y manga encajada con sisa de raglán (sin
  hombros). Se corrigieron en el motor y en el catálogo, con tests que
  verifican la tela (columnas del elástico, revés al revés) y la forma (ancho
  de espalda y sisa de la tabla).
- **Web:** las texturas detectadas se muestran en español y se pueden quitar
  antes de generar, porque ahora cambian el patrón y la visión fina es el
  punto débil de la IA.

## D025 — Pendientes de texturas, escote y evaluación (2026-11-11)

- **Panel en manga encajada:** `FlatRows` lleva los pts lisos a cada lado del
  panel, así la sisa cierra y disminuye en los bordes sin moverlo. El texto
  resume los tramos lisos y escribe las hileras con forma con marcadores.
- **Escote redondo** en manga encajada, hombro caído y chaleco: cierre
  central y cada hombro por separado, con uniones verificadas contra la
  espalda. El cárdigan sigue con escote recto (aviso).
- **Compensación de trenzas con dato medido**, no con una regla inventada:
  `panel_motivo_cm` (ancho de una repetición en la muestra). Los pts se
  agregan junto al panel y se quitan antes del borde, la sisa final o el
  escote, para no tocar la forma ni las uniones.
- **Evaluación con fotos (`make eval-fotos`):** mide por separado la IA
  (precisión por campo) y el patrón que sale de lo que vio (rúbrica
  determinista). Probado una vez con la IA real sobre la imagen de prueba:
  categoría y técnica correctas; el modelo describió los pétalos como
  bodoques y los huecos como calado, lo que es razonable. Falta el conjunto
  de fotos con derechos claros para medir de verdad.

## D026 — Cualquier tejido, fotos imperfectas y varias fotos (2026-11-11)

- **Ninguna combinación sin patrón.** De 62 combinaciones de categoría ×
  técnica × construcción que la IA puede devolver, todas fallaban con
  "no soportado". Ahora `engine/garments/routing.py` lleva cada una a la
  familia verificada más cercana y lo declara como advertencia `approx_*`:
  máquina → dos agujas; guantes → mitones; crochet de mitones o medias →
  dos agujas; amigurumi a dos agujas → crochet; construcciones de pullover
  sin familia → la más parecida (de abajo hacia arriba → manga encajada,
  piezas → hombro caído, resto → raglán). *Alternativa descartada:* rechazar,
  porque deja a la persona sin nada y la aproximación es honesta si se avisa.
  El PDF conserva esas advertencias al regenerar los talles.
- **Crochet de prendas:** pullover, cárdigan y chaleco en rectángulos (la
  construcción de crochet más común para principiantes), gorro (círculo
  plano + tubo), cuello y chal. Textura no identificada y jacquard sin
  gráfico se avisan siempre.
- **Varias fotos (hasta 4) y calidad medida.** `/analyze` acepta `files`.
  `vision/quality.py` mide desenfoque, resolución y exposición sin IA; el
  aviso va al prompt (para que el modelo sea prudente) y a la web (para
  pedir otra foto). Prompt `extractor-v3`: combina fotos, clasifica aunque
  la foto sea mala bajando la confianza, y elige lo más cercano para piezas
  fuera de catálogo. La web dejó de reescribir técnica y construcción en
  silencio.

## D027 — Escote del cárdigan (2026-11-11)

- En V por defecto; redondo si la foto muestra cuello redondo, alto o
  chimenea. Cada delantero pierde la mitad del escote de la espalda, así el
  hombro coincide (JoinCheck). V: disminuciones en dos ritmos regulares
  desde la altura de la sisa (ASUNCIÓN). El panel de textura se centra en la
  zona del hombro para que el escote no lo alcance.

## D028 — Capa de diseño: motivos radiales de crochet (2026-11-11)

- **Problema:** la IA veía un mandala y el motor entregaba un granny clásico.
- **Decisión:** la IA describe la *estructura* con vocabulario cerrado
  (`MotifDesign`: forma, simetría, bandas con punto, color y grosor
  relativo) y el motor calcula vueltas por banda, puntos por vuelta
  (círculo plano: 2π·r / ancho de punto, redondeado a la simetría), vueltas
  caladas, la vuelta que cuadra y las esquinas. El simulador verifica cada
  vuelta. Es coherente con "la IA interpreta; el código calcula": el modelo
  no da ningún conteo; la simetría y el orden de bandas son observaciones,
  como la paleta.
- *Alternativas descartadas:* que la IA escriba las vueltas (viola la regla
  y no cierra); un catálogo cerrado de mandalas (no generaliza).
- Si las bandas no entran en la medida pedida, se entrega más grande y se
  avisa (no se falla). 2000 diseños al azar: todos verificados.
- Probado con la IA real sobre `patron.jpeg`: cuadrado, simetría 8, 8
  bandas con 4 colores, 3 muestras coincidentes.
- *Límite:* no reproduce la forma exacta de cada pétalo (picos, arcos de
  cadenas); reproduce bandas, punto, color y simetría.

## D029 — Formato contra PDFs comerciales de referencia (2026-11-12)

- **Contexto:** se compararon nuestros PDFs con 20 patrones gratuitos de
  marcas (crochet y dos agujas, en `patrones-crochet/` y
  `patrones-dos-agujas/`, solo como referencia de formato: no se copian
  diseños ni se commitean).
- **Decisiones:**
  - Gráfico de símbolos de crochet (convención Craft Yarn Council) para
    motivos y granny square, siempre con leyenda propia. Se dibuja desde la
    IR verificada: un símbolo por punto producido. Motivos con más de 170
    pts en la vuelta mayor: se dibuja ampliado un sector de la simetría
    (≥ 1/4), como hacen los impresos.
  - Esquema por letras (sirve para todos los talles) también para cárdigan
    (V o redondo, abertura con tapa) y chaleco.
  - Texto: ciclos de forma ("Repetir las últimas 4 hileras N veces"),
    "*2 der, 2 rev; rep desde * hasta quedar 3 pts, ..." y unidades repetidas
    agrupadas "(cl, cad, saltar 1) 9 veces".
  - Elástico plano 2x2 para cualquier cantidad de puntos (antes 1x1 o santa
    clara según el talle: un talle salía sin elástico).
- *ASUNCIÓN:* proporciones de altura de los símbolos (pb 1, mpa 1,4,
  pa 1,9, pad 2,5) son de dibujo, no de tejido.
- *Pendiente:* retícula de colores para jacquard/fair isle (familia 2 de los
  gráficos de referencia).

## D030 — Principios del dibujo de crochet y pistas antes del análisis (2026-11-13)

Revisión de una tejedora con experiencia sobre un motivo generado: los puntos
del borde no mostraban dónde se tejían y los bordes del cuadrado se veían
desparejos.

- **Principios del gráfico** (`render/crochet_chart.py`):
  1. Cada símbolo sale del punto de la vuelta anterior donde se teje
     (`_anchors`, a partir de lo que consume cada operación de la IR). Si la
     cabeza queda lejos (vuelta que cuadra), el símbolo va en tamaño normal en
     el borde y una guía punteada lo une con su base: nada se calcula a ojo.
  2. En un lado recto los puntos van de pie, perpendiculares al lado, no
     apuntando al centro.
  3. Las vueltas redondas se giran para que la esquina caiga sobre el punto
     donde se teje (las redondas son simétricas; girarlas no cambia el tejido).
  Test: `test_every_chart_symbol_is_anchored_on_the_stitch_it_is_worked_into`.
- **Pistas previas**: en la subida, dos preguntas opcionales ("¿con qué está
  tejido?", "¿qué es?"), con "No sé" por defecto. Se le dicen al modelo y
  además mandan sobre su respuesta (confianza 1). Alternativa descartada:
  pedir más datos antes; la mayoría se los salta y la foto ya los da.
- **Defaults**: medida del motivo según las vueltas de la foto y el hilo;
  grosor preseleccionado con el estimado de la foto (commit 993a164).

## D031 — Comparación con patrones publicados: canesú legible, gorro real, foto, descripción libre y guía humana (2026-11-16)

Contexto: se compararon tres resultados nuestros (gorro de elástico, osito, pullover con canesú de jacquard) con patrones que circulan en internet. Los nuestros perdían en tres frentes: técnica mal detectada (agujas → crochet), texto ilegible (canesú con una línea "Solo talles…" por vuelta) y ausencia de voz humana y de imagen de la pieza.

Decisiones:
- **Canesú circular**: 6 vueltas de aumento repartido (`YOKE_INCREASE_ROUNDS`) con crecimiento geométrico y vueltas lisas entre medio, iguales en todos los talles. Cada vuelta se escribe "(5 der, m1l) 4 veces, (4 der, m1l) 14 veces"; ninguna vuelta reparte exacto, así siempre tiene la misma forma y el texto multitalle no se parte. ASUNCIÓN: sistema de porcentajes de E. Zimmermann (3 vueltas) y patrones comerciales (4-8). Alternativa descartada: aumentar en casi todas las vueltas (lo que había), ilegible.
- **Repeticiones** entre paréntesis: "(ops) N veces" en vez de "Repetir N veces: ops", que no dejaba ver dónde terminaba la repetición.
- **Gorro de dos agujas**: respeta el punto de la foto. En elástico, el gorro entero va en 2x2 y la corona disminuye dentro del elástico (primero los reveses, después los derechos). En los demás puntos, la corona va en gajos (4-10, el que mejor ajusta la medida), cada 2 vueltas y el final en todas si no entra en ~1/3 del alto (`CROWN_SHARE`, ASUNCIÓN). Se une en redondo sin cerrar entre partes y se termina pasando la hebra por los puntos (`meta["gather"]`).
- **Extractor v4**: reglas para distinguir agujas de crochet por la superficie (columnas de V, elástico, nudos) y la descripción libre de la persona como dato.
- **Descripción libre** antes de analizar (hasta 600 caracteres), en lugar de dos desplegables; la API sigue aceptando `tejido`/`categoria`.
- **Foto en la portada** del PDF (`?foto=<image_id>`), reprocesada (sin EXIF, achicada). Vive lo que dura la imagen guardada (`IMAGE_TTL_HOURS`).
- **Guía (IA, segunda pasada)**: notas de una tejedora experta por sección, intro y cierre (`ai/guide.py`, `guide-v1`). No puede tener ningún número (ni cifras ni palabras); se valida y repara hasta 2 veces y, si no cumple, el PDF sale sin guía. Así la IA aporta la voz humana sin poder contradecir el cálculo. El PDF la pide al descargarse (con caché del cliente de IA); `?guia=false` la omite.

## D032 — Guardas de jacquard en el canesú circular (2026-11-16)

- **Decisión:** si la foto muestra fair isle, el canesú circular
  (`engine/garments/yoke.py`) lleva guardas horizontales con un gráfico cada
  una, en lugar de advertir "no incluye un gráfico de jacquard".
- **Motivos** (`engine/colorwork.py`): biblioteca chica de motivos
  geométricos ORIGINALES generados por reglas (damero, puntitos, crucecitas,
  zigzag, rombos, abetos, estrellas por simetría octogonal). Un "cortador de
  flotes" garantiza flotes de 5 pts como máximo (vuelta circular); hay test
  para todos los motivos y alturas. La IA no elige celdas ni números: solo la
  paleta (ya existente). El primer color es el fondo (**ASUNCIÓN**: la paleta
  viene ordenada por dominancia); si faltan colores se completan con unos por
  defecto.
- **Ubicación:** guardas en los tramos de vueltas lisas entre aumentos, con
  una vuelta lisa antes y al menos una después: borde (damero, repetición de
  2) después del último aumento, porque el conteo final es fijo y siempre
  múltiplo de 4; guarda principal en el tramo anterior; mediana y chica más
  arriba (tramos 6, 5, 3 y 1 con 6 aumentos). La altura sale del tramo más
  corto entre el talle pedido y todos los de la tabla, así el gráfico es el
  mismo en el patrón multitalle (test).
- **Conteos:** los conteos intermedios del crecimiento geométrico se ajustan
  al múltiplo más cercano de la repetición de la guarda de su tramo, sin
  repartos exactos (el texto multitalle sigue sin "Solo talles"). El
  conteo final no cambia. El simulador verifica en cada vuelta de gráfico que
  la repetición entre justa y que la vuelta no cambie el conteo
  (`chart_repeat`).
- **Documento:** texto "tejer las vueltas 1 a N del gráfico K, repitiendo R
  veces los W pts del gráfico"; gráfico SVG (`render/colorwork.py`) con
  cuadros de color, símbolo por color para B/N, vueltas a la derecha, llave
  de repetición y referencias con nombre de color aproximado; versión en
  texto con letras. Si el cuerpo tiene panel de textura, ese es el gráfico 1
  y los de jacquard siguen. El esquema pinta las guardas en el canesú.
- **Metraje:** `Materials.color_meters` (A = total; contrastes = puntos de
  contraste + 1/3 por punto de flote, **ASUNCIÓN**).
- **Alternativas descartadas:** un gráfico único de todo el canesú con las
  disminuciones dentro de las guardas (como varios patrones publicados): más
  fiel, pero mezcla forma y color y rompe el texto multitalle; dejar que la
  IA dibuje el motivo: viola "la IA interpreta, el código calcula".
- **Límites:** no reproduce el dibujo de la foto; las guardas son de 2
  colores por vuelta; en hilos muy gruesos solo entran dameros; intarsia y
  mosaico siguen sin gráfico; la IA no elige "estilo" de motivo todavía.

## D033 — Amigurumi en piezas (crochet y dos agujas) con plantillas de figura (2026-11-16)

**Decisión.** El amigurumi se genera como un juguete en piezas, como los
patrones publicados: cada pieza es una sección de la IR (cabeza, cuerpo,
brazos y piernas "tejer 2", y según la figura orejas, hocico y cola), con su
cierre, su relleno y un armado con números calculados (`Pattern.finishing`,
nuevo; `Section.end_note_keys`, nuevo). La IA solo elige la plantilla
(`GarmentSpec.figura`: `bear`, `bunny`, `cat`, `generic`); las proporciones
están en `engine/garments/toy.py` y escalan con una sola medida, la altura
del muñeco sentado. Sin figura: muñeco sin orejas y una nota.

- **Geometría.** Cada pieza crece desde su extremo cerrado; su forma es una
  lista de tramos (contorno objetivo, largo sobre el tejido; "lo más rápido"
  o "lo que falte"). Los cambios se reparten parejo y van de a un sector
  (6 pts en crochet, 8 en agujas) por vuelta o por hilera del derecho, así
  cada vuelta se escribe "*n pb, aum; rep". El simulador verifica conteos y
  el largo de cada pieza (tolerancia 20 %); el generador rechaza con
  `too_small_for_yarn` una altura que no entra en el hilo.
- **Dos agujas: en plano, no en redondo.** Alternativas: en redondo con
  agujas de doble punta (sin costura) o en plano. Se eligió en plano y en
  jersey, desde pocos puntos montados, con kfb/2pjd en las hileras del
  derecho, fruncido de los extremos y costura con punto colchonero, porque
  montar 6-8 puntos en redondo es lo más difícil para una principiante y es
  la construcción clásica de juguetes de dos agujas. El texto escribe solo
  las hileras del derecho ("Hileras pares: rev") como los patrones impresos.
  Se quitó el ruteo que forzaba el amigurumi de agujas a crochet.
- **ASUNCIONES** (docs/fuentes.md): proporciones de las plantillas (cabeza
  0,52 x altura, cuerpo 0,38 de diámetro y 0,58 de costado, brazos 0,12 x
  0,34, piernas 0,16 x 0,28, orejas, hocico y cola); altura por defecto por
  grosor (10 a 40 cm); tejido apretado (pb CYC x 1,25, jersey CYC x 1,15,
  con ganchillo/agujas más finos: DK 3 mm / 3,25 mm); 8 aumentos por hilera
  del derecho en agujas; altura sentado = 0,9 x cabeza + 0,9 x costado del
  cuerpo; ojos al 56 % de la cabeza separados 18 % del contorno, ojos de
  seguridad de ~1 mm por cm de cabeza.
- **Esquema.** `render/toy.py` dibuja el muñeco armado de frente con formas
  simples a escala de la IR, rótulos en una columna con líneas guía y la
  cota de altura afuera del dibujo (antes la cota "Ancho" pisaba el borde).
- **Descartado:** formas sueltas (esfera, cilindro, cono con `spec.forma`):
  no eran un patrón de juguete.

## D034 — Exactitud geométrica, no solo aritmética (2026-11-16)

Pedido: "si vas a hacer un cuadrado, no puede tener 10 puntos de un lado y 11 del otro". El simulador ya garantizaba que cada vuelta consume y produce lo declarado, pero una vuelta puede cerrar la cuenta y ser incoherente.

Decisiones:
- **Simulador, en cada patrón antes de entregarlo**: (1) toda vuelta con 4 esquinas tiene los 4 lados iguales (`square_sides`); (2) mangas, puños y tapas izquierda/derecha tienen el mismo conteo en cada vuelta (`pair_mismatch`); (3) delanteros y lados del escote en espejo pueden ir como mucho UNA hilera corridos (los cierres van al principio de una hilera de su lado, como en los patrones publicados) y terminan con los mismos puntos.
- **Texto multitalle** (`tests/test_exactness.py`): se proyecta el texto fusionado a cada talle y los conteos `[N pts]` tienen que ser, en orden, los de la IR de ese talle. 7 familias × 3 grosores.
- **Redactor de IA**: la versión reescrita tiene que tener exactamente la misma secuencia de números que el patrón calculado (antes alcanzaba con que cada número existiera en el patrón: "12 vueltas" cambiado por "8 vueltas" pasaba). Si no, se repara o se entrega la plantilla.
- Comprobado además por muestreo: 3108 vueltas cuadradas de 400 motivos al azar, todos con lados iguales; todas las piezas pares de 8 familias × 7 talles × 3 grosores, iguales.

## D035 — Idiomas, PDF ajustable al final y dibujo de puntos coherente (2026-11-16)

Contexto: la persona vende para el mercado hispano e internacional (sobre todo en inglés). Pidió elegir cosas al descargar el PDF, todas sus fotos en la portada, gráficos arriba, nada de "créditos y legales" (lo consultó con un abogado) y poder firmarse como creadora.

Decisiones:
- **Cinco idiomas del patrón**: es, en, fr, de, it (`engine/i18n/`, mismas claves y mismos `{parámetros}` en todos; test). El idioma se elige al descargar: el patrón guardado se regenera con ese idioma y vuelve a pasar por el simulador (los números no dependen del idioma, pero algunos textos se fijan al generar).
- **Costo de IA**: la guía humana se pide solo para el idioma que se descarga, una vez, y queda en caché por (patrón, idioma). Alternativa descartada: pedir los cinco idiomas en una sola consulta (paga cinco veces la salida aunque se use uno, y una respuesta larga falla más la validación). Los números escritos en palabras se prohíben por idioma ("dos" es número en es y "la espalda" en fr).
- **Último paso**: idioma, talle resaltado y grosor del hilo se cambian ahí (talle e hilo recalculan y verifican al instante), más papel, guía sí/no, fotos de portada y "Diseñado por" (opcional, máx. 80 caracteres; va en portada, pie y metadatos del PDF).
- **PDF**: portada con todas las fotos elegidas (una grande o grilla de 2); el esquema y los gráficos van primero; sin sección de créditos/legales ni la nota "diseño propio"; sin salto de página forzado antes de las instrucciones.
- **Interfaz web** en los cinco idiomas, inglés por defecto (o el del navegador).
- **Cuándo hay dibujo con cada punto** (regla de coherencia): se dibuja punto por punto donde la posición de cada punto no es obvia por el texto: motivos y cuadrados de crochet, texturas y trenzas, jacquard y, nuevo, las vueltas de aumento del amigurumi al crochet (`render/toy.py::render_round_chart_svg`). El dibujo lista solo las piezas que se tejen exactamente igual, vuelta por vuelta (`engine/document.py::_round_chart_pieces`). No se dibuja punto por punto el jersey liso (todas las casillas serían iguales: los patrones comerciales dan esquema y medidas) ni el amigurumi a dos agujas (sus vueltas son "tejer todo" o aumentos repartidos que el texto ya ubica).

## D036 — Amigurumi "bolita": cabeza y cuerpo en una sola pieza (2026-11-17)

Contexto: un gatito bolita (prueba de la persona en `pruebas/`) salía con cabeza, cuello, cuerpo sentado, brazos, piernas y cola larga, y 41 cm de alto; el de la foto es una esfera de unos 18 cm.

Decisiones:
- Nuevo campo `GarmentSpec.cuerpo_juguete` (`pieces` | `ball`), que la IA elige por la forma (prompt `extractor-v5`, campo votado) y la persona puede corregir en la confirmación.
- `ball`: una esfera (`BALL_D` = 0,9 del alto), 4 patitas cortas, orejas según el animal (punta, redondas o largas) y cola corta (gato) o pompón (oso, conejo). Armado propio: ojos, orejas, patitas y cola en vueltas calculadas de la esfera.
- ASUNCIÓN: alto por defecto = la mitad del muñeco sentado del mismo hilo (`BALL_HEIGHT_FACTOR`); proporciones de orejas, patitas y cola medidas a ojo sobre juguetes bolita publicados. Con super bulky da 18 cm, como la foto.
- Verificado con la IA real: el gatito sale `cat` + `ball` con confianza 1,0; el osito de las comparaciones sigue `bear` + `pieces`.

## D037 — Catálogo ampliado al ~95 % (2026-11-17)

Base: `docs/investigacion-2026-11.md`.

Decisiones:
- **Vocabulario primero, motor después.** Todas las opciones comunes entran ya en `engine/spec.py`; la IA las reconoce con el prompt `extractor-v6`, que genera sus listas desde los enums. Mientras una opción no tenga cálculo propio, `engine/garments/routing.py` la manda a la familia verificada más parecida y el patrón lo avisa (`warning.approx.*`). Implementar una opción = borrarla de esas tablas. Un test garantiza que toda categoría da un patrón verificado o un rechazo honesto.
- **Subtipos en lugar de multiplicar categorías:** `estilo_gorro`, `objeto_plano` + `forma_plana`, `objeto_funda`, `estilo_manga`, `estilo_manta` y `motivo.estilo_granny`. La IA elige primero qué es y después de qué tipo.
- **No se separa `construccion` en tres ejes** (hombro / dirección / armado), aunque la investigación lo sugiere: la dirección y el armado los decide el motor, y la foto solo informa el hombro. Se suman los hombros que faltaban.
- **Seed/moss:** se mantienen los valores (`seed` = punto arroz, `moss` = punto arroz doble) y el prompt explica cómo distinguirlos; las etiquetas por idioma dicen el nombre local.
- **Textos por área** (`engine/i18n/areas/*.py`): cada línea de trabajo suma sus claves en su propio módulo, en los cinco idiomas, sin tocar los catálogos base.
- **Bugs viejos que expuso el barrido**, sin entregar nada mal porque el simulador los frena: mitones con punto arroz (múltiplo); cárdigan con cuello alto + largo corto (delanteros distintos).

## D038 — Hogar con cálculo propio (2026-11-17)

Las cinco categorías de hogar de D037 (`flat_item`, `cozy`, `basket`, `pillow`,
`rug`) dejan de aproximarse: `engine/garments/home.py` (+ `home_shapes.py`), en
crochet y dos agujas, con esquema propio (`render/home.py`) y textos en
`engine/i18n/areas/home.py`.

- **Tres geometrías** (investigación 2026-11): disco/rectángulo, base + tubo,
  base + paredes. El óvalo es solo de crochet (cadena por los dos lados); en
  agujas se entrega un rectángulo con aviso (`warning.home.knit_oval`):
  alternativa descartada, óvalo con aumentos en hileras cortas, porque no es
  una construcción común ni simple.
- **Una densidad por patrón** (el simulador usa una sola): en agujas las piezas
  rectangulares van enteras en punto bobo (densidad propia, el documento lo
  dice) y las redondas en jersey; no se mezclan bobo y jersey en una pieza
  salvo bordes de pocas hileras.
- **Funda redonda** = base cerrada (círculo) + paredes con holgura negativa;
  mate con cierre hacia la boca; termo con correa. **Bolsita**: crochet sin
  costuras desde una cadena trabajada por los dos lados; agujas, tira doblada
  (montar 6-8 pts en redondo en un fondo rectangular es difícil para
  principiantes).
- **Dos puntos nuevos** (`StitchKind.CROCHET_EDGE`, `PICK_UP`): puntos tejidos
  sobre un borde que suman un punto sin consumir uno vivo (otro lado de la
  cadena base, extremos de hileras, levantar puntos). Sin ellos el óvalo, la
  bolsita sin costura y el canasto rectangular no se podían escribir en la IR.
- **Cambios compartidos chicos:** `Section.meta["continue"]` (la sección sigue
  de la anterior, sin "Con N puntos en la aguja"), `meta["explicit_rounds"]`
  (el óvalo no se comprime en "repetir las vueltas 5-6": cada vuelta crece
  distinto), `meta["garter_gauge"]` (la muestra se mide en punto bobo) y
  `doc.weave_ends_toy`/`technique.toy_assembly` solo para amigurumi (antes
  dependían de que el patrón tuviera armado).
- Carpetita o posavasos al crochet con un motivo visible: motor de motivos.
- ASUNCIONES en docs/fuentes.md, "Hogar".
## D039 — Prendas: top, vestido, saco, bolero, poncho/ruana, escotes, largos y mangas (2026-11-17)

- Tablas comunes en `engine/garments/options.py` (largos cintura -10 cm, codo 0,6; vestido +20/+37/+55 cm; saco +15/+35; escotes; holgura y alto de tira). ASUNCIONES.
- Sin mangas (top por defecto) → manga encajada con sisa formada y tiras de sisa (`warning.approx.sleeveless` si se pidió otra construcción). Cardigan/crochet sin mangas: sin piezas de manga.
- Vestido/línea A: borde = max(pecho, cadera)+holgura; línea A ×1,25 (ASUNCIÓN). Aumentos en los costados (raglan, canesú) o disminuciones en los bordes (piezas). Con panel de textura el cuerpo va recto.
- Escotes: mock/scoop/cowl en todas las familias de agujas; henley/polo (tapa de 2,5 cm, abertura 8 cm, 3 ojales) en hombro caído, manga encajada y chaleco; cuello chal en cardigan/saco. En raglan/canesú henley/polo/chal siguen aproximados; en crochet todos los escotes nuevos siguen aproximados.
- Mangas globo (+40 %), campana (×1,5, borde santa clara) y casquillo (tira de 2 cm) en raglan, canesú y manga encajada; en hombro caído, cardigan y crochet se tejen rectas con aviso.
- Hombro caído modificado (escalón de 4 cm) implementado; T = hombro caído sin aviso. Saddle, dolman y side-to-side siguen aproximados.
- Bolero de un rectángulo (agujas y crochet), poncho de dos rectángulos y ruana (`GarmentSpec.estilo_poncho`, campo nuevo), talles adulto XS-3XL y niño 2-12.
- Bugs: delanteros de cardigan corridos 2 hileras (primera disminución ≥2 hileras después del comienzo del escote); contorno de crochet con doble redondeo.

## D040 — Rama principal `main`, higiene de artefactos y remoto (2026-11-19)

- La rama de trabajo `build/main-agent` pasa a ser `main`: era la única rama con historia y el remoto estaba vacío. Se fusionaron los commits pendientes de i18n de accesorios antes de publicar.
- No se versionan: `.claude/` ni `.commandcode/` (configuración local de agentes), `*.tsbuildinfo` y `.hypothesis/` (artefactos), `pruebas/`, `comparaciones/`, `prueba*.pdf`, `patron*.pdf` y `patron.jpeg` (material de la usuaria).
- Tampoco se versionan `patrones-crochet/` ni `patrones-dos-agujas/`: son PDFs de terceros descargados como referencia de formato; su propia guía prohíbe redistribuirlos. Quedan solo en local.
- El remoto `origin` apunta a `github.com/LeonardoVenezia/beauty-pattern` y la rama publicada es `main`.
