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
