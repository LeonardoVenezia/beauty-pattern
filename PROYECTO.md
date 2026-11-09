# PROYECTO — Foto a patrón de tejido (nombre provisorio: "Tejedora")

## 1. Objetivo
El usuario sube una foto de una prenda o pieza tejida y obtiene un **patrón completo** (materiales, medidas, instrucciones por secciones, gráficos, esquema, metraje estimado) en PDF y en pantalla, adaptado a **su hilo, su densidad y su talle**.

Alcance máximo: tejido a dos agujas, circular, a máquina simple (solo exportación opcional futura) y crochet; prendas, accesorios y piezas del hogar.

## 2. Principio de diseño
**La IA interpreta, el código calcula.** Tres capas separadas:

```
FOTO ──> [1. Percepción] ──> Atributos (JSON validado)
                │                     │
                │            [2. Confirmación del usuario]
                │                     │
                ▼                     ▼
        Regiones de color      [3. Motor determinista] ──> Patrón estructurado (IR)
                                      │
                                [4. Simulador / verificador]
                                      │
                         [5. Redacción + crítica con IA]
                                      │
                               [6. Render PDF/SVG/web]
```

### 2.1 Modelo de IA y proveedor

- **Modelo**: DeepSeek V4.1 Flash Fast (`refuseless/deepseek-v4.1-flash-fast`), proveedor Refuseless. Es un modelo multimodal (entrada de imagen, salida de texto), con contexto de 1 M de tokens y precio muy bajo. Un solo modelo cumple los tres roles (extractor, redactor, crítico), con prompts y llamadas separadas.
- **Configuración por entorno** (`.env.example` versionado): `AI_PROVIDER`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, y opcionalmente `AI_MODEL_EXTRACTOR`, `AI_MODEL_WRITER`, `AI_MODEL_CRITIC` para poder asignar modelos distintos por rol sin tocar código.
- **Formato de API sin confirmar**: no se sabe con certeza qué formato expone Refuseless para este modelo. El agente debe leer la documentación oficial del proveedor y escribir el adaptador. El mismo modelo está también disponible en otros proveedores (por ejemplo DeepSeek directo bajo el nombre `deepseek-flash`, o vía gateways), lo que sirve de plan B: cambiar de proveedor debe ser cuestión de variables de entorno.
- **Sondeo de capacidades al arrancar** (`ai/probe.py`), con resultado cacheado y visible en un endpoint `GET /health/ai`:
  1. ¿Acepta imágenes (base64 y/o URL)? Se prueba con una imagen sintética conocida.
  2. ¿Soporta salida JSON estructurada (`response_format`/JSON schema)? Si no, se usa JSON por prompt + validación.
  3. ¿Soporta tool calling? (opcional; el diseño no depende de ello).
  - Si el endpoint **no acepta imágenes**, el sistema no debe inventar nada: falla con un mensaje claro y ofrece cambiar de proveedor por configuración.
- **Costos**: registrar tokens por llamada y estimar costo por patrón. Con este modelo el costo es bajo, lo que permite usar redundancia (varias muestras) donde convenga.
- **Límite conocido de la entrada de imagen**: el modelo procesa imágenes hasta una resolución del orden de 1344 × 1344 px; imágenes mayores se reducen. Por eso el preprocesado propio (3.1) es obligatorio y los detalles finos (texturas, motivos) se envían como recortes aparte.

## 3. Capa 1 — Percepción (IA + visión clásica)

### 3.1 IA #1: extracción de atributos con visión
Entrada: imagen (y opcionalmente una segunda foto). Salida: objeto `GarmentSpec` validado con Pydantic, con **confianza por campo** y un campo `no_visible` para lo que la foto no permite saber.

**Robustez ante un modelo pequeño y barato** (obligatorio):
- **Preprocesado**: corregir orientación, quitar EXIF, redimensionar (máx. ~1344 px) y generar recortes de detalle (zona del pecho/canesú, puño, textura) enviados en llamadas separadas.
- **Varias muestras y votación**: ejecutar el extractor N veces (por defecto N=3, temperatura baja pero no nula) y consolidar campo por campo. La confianza de cada campo se deriva del grado de acuerdo entre muestras; los campos con desacuerdo se marcan como "dudoso" en la pantalla de confirmación.
- **Salida validada**: el JSON se valida con Pydantic; si falla, ciclo de reparación acotado (devolver el error al modelo, máximo 2 intentos); si sigue fallando, el campo queda como `desconocido`, nunca inventado.
- **Descripción antes de clasificar**: el prompt pide primero observaciones descriptivas concretas (qué se ve, dónde) y recién después la clasificación contra listas cerradas de valores permitidos. Los valores fuera de la lista se rechazan.
- **Prompts versionados** y cambios solo tras correr `make eval`.

Campos mínimos (ampliar según familia):
- `categoria`: pullover, cardigan, chaleco, gorro, bufanda, cuello, mitones/guantes, medias, chal, manta, bolso, amigurumi, otro.
- `tecnica`: tejido a dos agujas / circular / crochet.
- `construccion`: raglan top-down, hombro caído, manga encajada, canesú circular (yoke), cuerpo en una pieza, desde abajo, etc.
- `escote`: redondo, V, barco, cuello alto, cuello tortuga, capucha…
- `largo_cuerpo`, `largo_manga`, `ajuste` (muy holgado / holgado / regular / entallado), `forma` (recto, A, cropped…).
- `punto_base`: jersey, elástico 1x1/2x2, punto musgo, canalé, bobo, etc.
- `texturas`: lista (trenzas, calados, ochitos, bobos…), cada una con ubicación y repetición estimada.
- `colorwork`: tipo (ninguno, listas, fair isle/jacquard, intarsia, mosaico), zona, cantidad de colores, paleta.
- `acabados`: puños, cintura, cuello, tapas de botones, bolsillos, flecos.
- `hilo_aparente`: grosor estimado, aspecto (liso, mohair, bouclé, jaspeado) — solo orientativo.
- `incertidumbres`: lista de cosas que el modelo no pudo determinar.

El modelo **no** devuelve medidas ni conteos de puntos.

### 3.2 Visión clásica
- Recorte y segmentación de la zona de color/textura (segmentación intercambiable: `rembg`/SAM opcional, o heurística por color y bordes).
- Cuantización de color (k-means en espacio Lab, N configurable), limpieza de píxeles aislados, ajuste de proporción de celda según densidad (los puntos no son cuadrados).
- Detección de repetición (autocorrelación) para convertir jacquard en un **motivo repetible** con ancho que divida el total de puntos.
- Para fair isle: límite de colores por vuelta (por defecto 2), detección y reporte de flotes demasiado largos.
- Para texturas: clasificación contra un catálogo propio de puntos (ver 4.3). Si no hay coincidencia confiable, se pide confirmación al usuario o se propone el punto más cercano.

## 4. Capa 3 — Motor determinista (`engine/`)

### 4.1 Representación intermedia (IR)
Un patrón es una estructura tipada: secciones → pasos → vueltas/instrucciones atómicas (`knit`, `purl`, `k2tog`, `ssk`, `yo`, `m1l`, `m1r`, `cable(...)`, `bobble`, `sc`, `dc`, `inc`, `dec`, etc.), cada una con su efecto en el conteo de puntos. Todo lo demás (texto, PDF, gráficos) se genera **desde la IR**.

### 4.2 Parámetros del usuario
- Densidad: puntos y vueltas por 10 cm (con valores por defecto por grosor de hilo, editables).
- Medidas: talle estándar (tablas documentadas, con fuente) o medidas propias.
- Ease (holgura) derivada del `ajuste`, editable.
- Unidades, idioma, nivel de detalle (principiante / experta).

### 4.3 Catálogo de puntos (`engine/stitches/`)
Biblioteca declarativa (datos, no código suelto): cada punto tiene múltiplo de puntos, vueltas por repetición, instrucciones por vuelta, efecto en el conteo, versión en gráfico y símbolo estándar. Cubrir al menos: jersey, bobo, musgo, elásticos 1x1/2x2/3x1, canalé inglés, trenzas simples (2/2, 3/3, cruzadas a izq. y der.), ochitos, calados básicos, bobos (nudos), punto arroz, nido de abeja, ochitos en crochet, punto bajo, medio punto alto, punto alto, círculo mágico.

### 4.4 Familias de prenda (por orden de prioridad)
Cada familia es un módulo con función pura `generate(spec, params) -> Pattern`:
1. Pullover raglan top-down (circular), con todas las variantes de escote y manga.
2. Pullover hombro caído (en piezas o circular).
3. Canesú circular con jacquard (yoke).
4. Pullover manga encajada.
5. Cardigan (cualquiera de las construcciones anteriores, con tapa de botones).
6. Chaleco.
7. Gorro (varias formas de corona), bufanda, cuello.
8. Mitones/guantes.
9. Medias (puño, talón con lengüeta, empeine, puntera).
10. Chales (triangular, creciente, rectangular).
11. Mantas/cobijas (por módulos o panel).
12. Crochet: amigurumi (esfera, cilindro, cono con aumentos/disminuciones calculados), granny squares, prendas simples en crochet.

Si la foto no corresponde a una familia soportada, el sistema lo dice con claridad y ofrece la familia más cercana en lugar de inventar.

### 4.5 Reglas de cálculo
- Reparto de aumentos/disminuciones: algoritmo determinista y documentado (distribución uniforme con resto repartido de forma simétrica).
- Ajuste de conteos a múltiplos necesarios (repetición de punto, motivo de jacquard, simetría).
- Todos los redondeos son explícitos, con tolerancia máxima documentada respecto de la medida objetivo.
- Metraje estimado a partir de gauge y área, con margen documentado; se presenta como estimación.

## 5. Capa 4 — Verificación (obligatoria)

### 5.1 Simulador de puntos (`engine/simulator/`)
Interpreta **la salida textual/estructurada final** (no la IR interna) vuelta por vuelta y comprueba:
- el conteo de puntos de cada vuelta es el declarado;
- cada vuelta consume exactamente los puntos disponibles;
- los aumentos y disminuciones suman el total esperado por sección;
- el contorno final coincide con las medidas objetivo dentro de la tolerancia;
- las uniones (hombros, mangas al cuerpo, axila) tienen el mismo número de puntos de ambos lados.

### 5.2 Pruebas
- Property-based (hypothesis): para miles de combinaciones de talle, densidad y ease, el simulador debe pasar.
- Golden: patrones conocidos reproducidos y comparados.
- Regresión visual de los SVG/PDF.

## 6. Capa 5 — Redacción y crítica (IA)

### 6.1 IA #2: redactor y crítico (mismo modelo, roles separados)
Ambos roles usan el mismo modelo que el extractor (ver 2.1), con prompts y contextos totalmente separados. Como no hay un segundo modelo distinto, la independencia del crítico es **parcial**; por eso el crítico es solo informativo y los controles que importan son deterministas (simulador, validación de números).
- **Redactor**: recibe la IR y los números ya calculados y produce texto claro, adaptado al nivel de la usuaria. Tiene prohibido cambiar o añadir números; una validación posterior compara todos los números del texto con los de la IR y rechaza el resultado si no coinciden (con reintentos acotados; si no logra pasar la validación, se usa una **plantilla de texto determinista** como alternativa, que siempre debe existir).
- **Crítico**: recibe la foto, el `GarmentSpec` confirmado y un resumen del patrón; marca incoherencias probables (por ejemplo, "la foto parece tener mangas más largas"). Sus observaciones se muestran como advertencias para la usuaria; **nunca modifican el patrón automáticamente**. Si el endpoint fuera capaz de usar otro modelo, `AI_MODEL_CRITIC` permite asignarlo sin cambios de código.

### 6.2 Evaluación de la IA
`evals/` contiene un conjunto de fotos de prueba con atributos esperados. `make eval` mide precisión por campo del extractor y registra resultados por versión de prompt. Los prompts se versionan y no se cambian sin correr la evaluación.

## 7. Experiencia de usuario (frontend)
Flujo mobile-first, mínimo de fricción:
1. Subir foto (cámara, galería o pegar enlace de imagen).
2. Pantalla de confirmación: "Esto es lo que detecté" con los atributos editables en lenguaje simple y las incertidumbres destacadas.
3. Dos preguntas de contexto: grosor del hilo (con fotos de referencia y densidad por defecto) y talle (o medidas). Opción "medir mi muestra" para ingresar la densidad real.
4. Vista previa del patrón (esquema con medidas, resumen de materiales, advertencias).
5. Descargar PDF; guardar proyecto; contador de vueltas integrado (modo "tejiendo": una vuelta a la vez, con pantalla encendida).

Accesibilidad: letra grande, alto contraste, soporte de lector de pantalla en las partes clave.

## 8. API (FastAPI)
- `POST /analyze` — imagen → `GarmentSpec`.
- `POST /pattern` — `GarmentSpec` confirmado + parámetros → patrón (IR + texto + advertencias).
- `GET /pattern/{id}/pdf`, `/svg`.
- `GET /stitches` — catálogo.
- Almacenamiento: SQLite (desarrollo) con migración sencilla a Postgres; imágenes con vencimiento configurable.

## 9. Hitos
1. **Cimientos**: repo, Makefile, CI local, IR de patrones, unidades, densidad, i18n, `FAKE_AI`, `.env.example`, cliente de IA con adaptador para Refuseless (tras leer su documentación) y sondeo de capacidades (`ai/probe.py`, `GET /health/ai`).
2. **Catálogo de puntos** y render de gráficos de punto (SVG).
3. **Simulador** completo con tests de propiedades.
4. **Pullover raglan top-down** de punta a punta (motor + simulador + texto + PDF + esquema SVG), sin IA todavía, desde un `GarmentSpec` escrito a mano.
5. **Percepción**: preprocesado de imagen y recortes, extractor con IA #1 (varias muestras con votación, reparación de salida), esquemas Pydantic, caché, evals; cuantización de color y detección de motivos repetibles.
6. **API y frontend** con flujo completo foto → confirmación → PDF.
7. **Redactor y crítico** (IA #2) con validación de números.
8. **Más familias**: hombro caído, canesú con jacquard, manga encajada, cardigan, chaleco.
9. **Accesorios**: gorro, bufanda, cuello, mitones, medias, chales, mantas.
10. **Crochet**: amigurumi y piezas planas.
11. **Pulido**: rendimiento, accesibilidad, contador de vueltas, guardado de proyectos, seguridad, documentación de usuario y despliegue (Dockerfile + guía).

## 10. Riesgos conocidos (tenerlos presentes)
- Una foto no muestra espalda, mangas completas ni el hilo real: el sistema debe declarar supuestos, no esconderlos.
- Patrones con construcciones muy poco comunes pueden no tener familia: decirlo y ofrecer alternativa.
- La IA puede equivocarse al reconocer puntos de textura: siempre confirmar con la usuaria. Con un modelo pequeño y barato, la visión fina (trenzas, calados, jacquard detallado) es el punto más débil; por eso existen los recortes, la votación entre muestras, la lista cerrada de valores y la confirmación.
- El endpoint de Refuseless podría no aceptar imágenes, no soportar JSON estructurado o cambiar de comportamiento; el sondeo de capacidades y la posibilidad de cambiar de proveedor por entorno existen para eso.
- Un único modelo en todos los roles reduce la independencia de la crítica; la garantía de corrección descansa en el motor y el simulador, no en la IA.
- Los patrones deben presentarse como guías: recomendar siempre tejer una muestra antes de empezar.
- Respetar derechos de autor: el producto genera patrones propios inspirados en la apariencia general de una prenda; no reproduce ni descarga patrones publicados, y se informa a la usuaria que, si la prenda es de un diseñador, el patrón original es suyo.

## 11. Fuentes a documentar (`docs/fuentes.md`)
Tablas de talles y medidas, convenciones de ease, abreviaturas estándar de tejido y crochet, fórmulas de reparto de aumentos y proporciones de construcción. Cada una con su referencia; las que no tengan, marcadas como asunción.
