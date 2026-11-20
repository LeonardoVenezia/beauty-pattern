# Especificación: generador de patrones de tejido (estándar de mercado)

Nov 11, 2026 · @Leonardo

## Propósito

El programa recibe los datos de un patrón (dos agujas o crochet) y genera un PDF descargable con la estructura, el lenguaje técnico y la calidad que el comprador espera de un patrón pago en plataformas como Ravelry, Etsy, LoveCrafts o Payhip.

Este documento es la especificación para Claude Code: define qué contenido es obligatorio, qué estándares técnicos seguir, el modelo de datos de entrada y los criterios para dar el programa por terminado. Las referencias técnicas principales son los estándares del Craft Yarn Council (CYC), que la industria usa de hecho en inglés, adaptados a español.

Alcance de la primera versión: patrones escritos en español (con opción de inglés), un PDF por patrón, con tabla de talles, gráficos generados a partir de una grilla y validaciones de coherencia. Fuera de alcance: venta, cobro, entrega del archivo y diseño asistido del patrón.

## Qué espera el comprador

Quien paga un patrón espera poder terminar la prenda sin escribirle a la diseñadora. Eso se traduce en estas expectativas concretas:

- **Saber antes de empezar si puede hacerlo**: nivel de dificultad, técnicas necesarias, materiales y cantidad exacta de hilo por talle.
- **Instrucciones completas para todos los talles**: cada número de puntos y vueltas dado para cada talle, sin "calcular el resto".
- **Terminología estándar y consistente**: abreviaturas definidas en el propio patrón y usadas siempre igual.
- **Muestra (gauge) explícita**: puntos y vueltas en 10 cm, con aguja y punto indicados, porque de eso depende que la prenda calce.
- **Puntos de control**: conteo de puntos al final de cada vuelta con cambios y medidas a verificar.
- **Apoyo visual**: foto principal de buena calidad, esquema con medidas de la prenda terminada y gráficos para calados, jacquard o texturas.
- **Formato legible e imprimible**: PDF de pocas páginas por sección, letra clara, que funcione en pantalla y en papel A4/Carta.
- **Patrón revisado**: la gente espera que esté probado por testers y editado técnicamente; un error en un conteo genera reseñas negativas.
- **Datos de soporte**: contacto de la diseñadora, página de erratas, versión y fecha del patrón, y aviso de derechos de autor.

## Estructura del patrón

El PDF generado debe seguir este orden. Las secciones marcadas como opcionales se omiten si no hay datos; las demás son obligatorias y el programa no debe generar el PDF si faltan.

| # | Sección | Contenido | Obligatoria |
| --- | --- | --- | --- |
| 1 | Portada | Nombre del patrón, nombre de la diseñadora o marca, foto principal, técnica (dos agujas / crochet) | Sí |
| 2 | Descripción | 1 a 3 párrafos: qué es la prenda, construcción (de arriba hacia abajo, en redondo, por piezas), estilo | Sí |
| 3 | Ficha técnica | Nivel de dificultad, talles disponibles, holgura recomendada (ease), técnicas necesarias | Sí |
| 4 | Tabla de talles y medidas | Medidas de la prenda terminada por talle; medida del cuerpo sugerida | Sí, si la prenda tiene talles |
| 5 | Materiales | Hilo (marca, nombre, composición, peso CYC, metros/gramos por ovillo), cantidad por talle en ovillos y metros; agujas o ganchos (mm y US); accesorios (marcadores, aguja lanera, botones con medida) | Sí |
| 6 | Muestra | Puntos y vueltas en 10 × 10 cm, punto usado, aguja, si es lavada y bloqueada | Sí |
| 7 | Abreviaturas | Solo las usadas en el patrón, en orden alfabético, con su definición | Sí |
| 8 | Puntos especiales y técnicas | Explicación paso a paso de puntos no básicos, con enlace a video opcional | Opcional |
| 9 | Notas del patrón | Construcción, cómo leer los gráficos, cómo seguir los talles, sustitución de hilo | Sí |
| 10 | Instrucciones | Divididas por partes (Cuerpo, Mangas, Cuello…), vuelta por vuelta, con conteos | Sí |
| 11 | Gráficos | Grilla con leyenda de símbolos, numeración de vueltas y puntos, repetición marcada | Opcional |
| 12 | Esquema (schematic) | Dibujo de la prenda con medidas por talle | Sí, si la prenda tiene talles |
| 13 | Terminación | Rematar hebras, costuras, bloqueo, colocación de botones | Sí |
| 14 | Créditos y legales | Copyright, uso permitido (personal, venta de piezas terminadas sí/no), contacto, redes, erratas, versión y fecha | Sí |

### Convenciones de las instrucciones

- Los números por talle se escriben en el orden de la tabla: `52 (56, 60, 64, 68) pts`. Si un valor es igual para todos, se escribe una sola vez.
- Si un talle no aplica a un paso, se indica con guion: `–`.
- Cada vuelta que cambia el número de puntos termina con el conteo entre corchetes: `[64 (68, 72) pts]`.
- Las repeticiones usan asteriscos o corchetes: `*2 der, 2 rev; rep desde * hasta el final`.
- Se indica el lado: LD (lado derecho) / LR (lado revés) en piezas planas.
- Las medidas se dan en cm y, opcionalmente, en pulgadas entre paréntesis.
- Opcional deseable: resaltar con color el talle elegido por el comprador (generar una versión del PDF por talle).

## Estándares técnicos

El programa debe usar catálogos fijos para pesos de hilo, niveles de dificultad y abreviaturas, basados en los estándares del Craft Yarn Council, para que el comprador reconozca los valores. Los valores de muestra y aguja de esta sección son aproximados (de memoria, sin verificar contra la fuente) y deben revisarse contra [los estándares del Craft Yarn Council](https://www.craftyarncouncil.com/standards) antes de cargarlos.

### Peso del hilo (CYC)

| Categoría | Nombre CYC | Nombres comunes | Muestra dos agujas (pts en 10 cm) | Aguja sugerida (mm) |
| --- | --- | --- | --- | --- |
| 0 | Lace | Encaje, 1 hebra, Cobweb | 33–40 | 1,5–2,25 |
| 1 | Super Fine | Fingering, Sock, 4 hebras | 27–32 | 2,25–3,25 |
| 2 | Fine | Sport | 23–26 | 3,25–3,75 |
| 3 | Light | DK, Light Worsted | 21–24 | 3,75–4,5 |
| 4 | Medium | Worsted, Aran | 16–20 | 4,5–5,5 |
| 5 | Bulky | Chunky | 12–15 | 5,5–8 |
| 6 | Super Bulky | Super Chunky, Roving | 7–11 | 8–12,75 |
| 7 | Jumbo | Jumbo, Roving | 6 o menos | 12,75 o más |

El programa usa esta tabla para advertir (no bloquear) si la muestra declarada no coincide con la categoría del hilo.

### Nivel de dificultad (CYC)

| Nivel | Nombre | Qué implica |
| --- | --- | --- |
| 1 | Principiante | Puntos básicos, sin forma, piezas planas |
| 2 | Fácil | Puntos básicos, repeticiones simples, aumentos y disminuciones sencillos, terminación simple |
| 3 | Intermedio | Calados o trenzas simples, tejido en redondo con agujas de doble punta o circulares, formas a media dificultad |
| 4 | Avanzado | Calados complejos, jacquard o intarsia, trenzas complejas, formas detalladas y terminación refinada |

### Abreviaturas

El programa mantiene un diccionario de abreviaturas por técnica e idioma; el PDF incluye solo las usadas en las instrucciones (detectadas automáticamente). Las abreviaturas en español varían por país, así que el diccionario debe ser editable y cada patrón declara la variante regional.

| Técnica | Abreviatura (ES) | Significado | Equivalente (EN) |
| --- | --- | --- | --- |
| Dos agujas | der | punto derecho | k |
| Dos agujas | rev | punto revés | p |
| Dos agujas | laz | lazada | yo |
| Dos agujas | 2pjd | 2 puntos juntos al derecho (disminución) | k2tog |
| Dos agujas | desl | deslizar un punto | sl |
| Dos agujas | aum | aumento | inc / M1 |
| Dos agujas | LD / LR | lado derecho / lado revés | RS / WS |
| Crochet | cad | cadena | ch |
| Crochet | pd | punto deslizado / punto raso | sl st |
| Crochet | pb | punto bajo / medio punto | sc (US) / dc (UK) |
| Crochet | pa | punto alto / vareta | dc (US) / tr (UK) |
| Crochet | am | anillo mágico | magic ring |
| Ambas | pts / vtas | puntos / vueltas | sts / rows-rnds |
| Ambas | rep | repetir | rep |
| Ambas | mc | marcador | pm / m |

En crochet, si el patrón se exporta en inglés, el programa debe declarar en las notas si usa terminología US o UK, porque los mismos nombres designan puntos distintos.

### Talles

- Cada patrón define su lista de talles (ej. XS, S, M, L, XL, 2XL o por contorno de busto en cm) y, para cada uno, las medidas de la prenda terminada.
- La holgura (ease) se declara en cm: positiva (prenda más grande que el cuerpo), cero o negativa.
- Rango esperado hoy en prendas de adulto: al menos 6 a 10 talles; los patrones con pocos talles reciben críticas. Recomendación, no validación.
- Accesorios sin talle (chales, gorros de talle único) omiten la tabla de talles pero mantienen las medidas finales.

### Muestra

- Formato fijo: `22 pts y 30 vtas = 10 × 10 cm en punto jersey con aguja de 4 mm, después del bloqueo`.
- Puede haber más de una muestra (ej. jersey y trenza); cada una indica el punto.

## Gráficos, esquemas y fotos

Los gráficos y el esquema se generan desde datos (no como imágenes subidas), para que siempre coincidan con las instrucciones escritas.

### Gráficos de puntos

- Entrada: una grilla de símbolos (filas × columnas) más una leyenda; cada celda referencia un símbolo del diccionario.
- Salida en vector (SVG embebido en el PDF), legible al imprimir: celda mínima de 4 mm.
- Numeración de vueltas en el lateral: en piezas planas, LD a la derecha y LR a la izquierda; en redondo, todas a la derecha. Numeración de puntos abajo.
- Lectura estándar: de abajo hacia arriba; LD de derecha a izquierda, LR de izquierda a derecha (dos agujas).
- Repetición marcada con un recuadro de color y nota "repetir N veces".
- Celdas "sin punto" en gris para calados que cambian el número de puntos.
- Leyenda con símbolo, nombre, qué hacer en LD y qué hacer en LR.
- Gráficos de color (jacquard, intarsia) con colores reales del hilo y su código (A, B, C) para imprimir en blanco y negro.
- Crochet: soportar diagramas por símbolos estándar (cadena, pb, pa) en filas; los diagramas circulares quedan para una versión posterior.
- Gráficos grandes se dividen en varias páginas con superposición de una fila y columna, y se indica la unión.

### Esquema de la prenda

- Dibujo lineal plano de cada pieza (delantero, espalda, manga) o de la prenda entera.
- Cotas con letras (A, B, C…) y una tabla de medidas por talle al lado, en cm (y pulgadas opcional).
- Para la v1 se aceptan plantillas de esquema por tipo de prenda (suéter raglan, cárdigan, gorro, chal triangular, medias) con medidas paramétricas.

### Fotos

- Foto de portada obligatoria, mínimo 1600 px en el lado largo; el programa advierte si es menor.
- Fotos adicionales opcionales (detalle de punto, prenda puesta, terminación), con epígrafe.
- Fotos de paso a paso opcionales junto a los puntos especiales.

## Formato del PDF

El entregable es un PDF con texto seleccionable (no imágenes de texto), pensado para leerse en tablet y para imprimir.

- Tamaño de página configurable: A4 (por defecto) y Carta. Márgenes de 15–20 mm.
- Tipografía sin serifa para el cuerpo, 10–12 pt; títulos de sección jerarquizados; interlineado amplio.
- Encabezado o pie en cada página: nombre del patrón, diseñadora, número de página "3 de 12" y copyright.
- Índice con enlaces internos en patrones de más de 6 páginas; marcadores (bookmarks) del PDF por sección.
- Primera página: portada con foto. Segunda: ficha técnica, materiales y muestra en una vista, para que el comprador decida si empieza.
- Las tablas y gráficos no se cortan entre páginas salvo que sean más grandes que una página.
- Cada parte de las instrucciones (Cuerpo, Mangas…) empieza con su título y no queda un título solo al final de una página.
- Opción "versión para imprimir": sin fondos de color y con fotos reducidas para ahorrar tinta.
- Opción por talle: un PDF adicional con solo el talle elegido o con ese talle resaltado.
- Plantilla visual configurable por marca: logo, dos colores, tipografía. Los datos del patrón no deben depender de la plantilla.
- Metadatos del PDF: título, autora, palabras clave, idioma.
- Peso del archivo objetivo: menos de 15 MB, comprimiendo fotos.

## Modelo de datos

Cada patrón es un archivo YAML (o JSON equivalente) validado con un esquema; los números que varían por talle se escriben como listas alineadas con `talles`, y el texto usa variables entre llaves que el programa reemplaza.

```yaml
version_patron: "1.0"
fecha: 2026-11-11
idioma: es
variante_regional: AR        # define el diccionario de abreviaturas
tecnica: dos_agujas           # dos_agujas | crochet
crochet_terminologia: null    # us | uk (solo crochet)

titulo: "Suéter Bruma"
disenadora: { nombre: "Ana Pérez", marca: "Bruma Tejidos", web: "https://...", email: "..." }
descripcion: |
  Suéter raglan tejido de arriba hacia abajo, sin costuras...
construccion: "top-down, en redondo"
nivel: 2                      # 1 a 4 (CYC)
tecnicas: ["tejido en redondo", "aumentos raglan", "levantar puntos"]

talles: ["XS", "S", "M", "L", "XL"]
holgura_cm: 10
medidas_finales:              # cota del esquema -> valores por talle (cm)
  A_contorno_busto: [86, 94, 102, 110, 118]
  B_largo_total:    [56, 58, 60, 62, 64]

hilos:
  - codigo: A
    marca: "Marca X"
    nombre: "Merino DK"
    composicion: "100% merino"
    peso_cyc: 3
    metros_por_ovillo: 225
    gramos_por_ovillo: 100
    ovillos: [4, 4, 5, 5, 6]
    color: "Gris niebla"
agujas:
  - { mm: 4, us: 6, tipo: "circular 80 cm", uso: "cuerpo" }
accesorios: ["4 marcadores", "aguja lanera"]

muestras:
  - { puntos: 22, vueltas: 30, punto: "jersey", aguja_mm: 4, bloqueada: true }

notas: ["El número entre paréntesis corresponde a los talles S, M, L, XL."]
puntos_especiales:
  - { abreviatura: "aumD", nombre: "aumento a la derecha", pasos: "...", video: null }

partes:
  - titulo: "Cuello"
    pasos:
      - texto: "Con aguja de 4 mm, montar {mon} pts. Unir en redondo y colocar mc."
        valores: { mon: [88, 96, 100, 104, 112] }
        conteo: "{mon}"
      - texto: "Vtas 1–8: *1 der, 1 rev; rep desde *."
        grafico: null

graficos:
  - id: G1
    titulo: "Calado del canesú"
    modo: plano              # plano | redondo
    repeticion: { columnas: [1, 8], veces: "hasta el final" }
    leyenda: ["der", "laz", "2pjd", "sin_punto"]
    grilla:                  # fila 1 = primera vuelta (abajo)
      - [der, der, laz, 2pjd, der, der, der, der]

esquema: { plantilla: "sueter_raglan", cotas: [A_contorno_busto, B_largo_total] }
fotos:
  portada: "fotos/portada.jpg"
  adicionales: [{ archivo: "fotos/detalle.jpg", epigrafe: "Detalle del calado" }]
legales:
  copyright: "© 2026 Ana Pérez"
  uso: "Uso personal. Se permite vender piezas terminadas en pequeña escala citando a la diseñadora."
  erratas_url: "https://..."
```

El diccionario de símbolos y abreviaturas es un archivo aparte, compartido entre patrones, con: clave, abreviatura por idioma y región, nombre, instrucción en LD, instrucción en LR, símbolo de gráfico (SVG) y cuántos puntos consume y produce (para validar conteos).

## Requisitos y validaciones

El programa funciona en cuatro pasos y se detiene con un informe de errores legible si una validación bloqueante falla.

1. **Cargar y validar** el YAML contra el esquema (campos obligatorios, tipos, listas por talle del mismo largo que `talles`).
2. **Expandir** variables por talle a la notación `88 (96, 100, 104, 112)`, colapsando valores repetidos; generar la nota de cómo leer los talles.
3. **Componer** las secciones en el orden de la estructura, detectar las abreviaturas usadas y armar su lista, generar gráficos y esquema en SVG.
4. **Renderizar** el PDF (recomendado: HTML + CSS de impresión con WeasyPrint o Typst; Claude Code elige y justifica) y escribir el informe de advertencias.

### Validaciones

| Validación | Tipo | Detalle |
| --- | --- | --- |
| Secciones obligatorias presentes | Bloqueante | Según la tabla de estructura |
| Listas por talle completas | Bloqueante | Cada lista tiene un valor por talle (o un único valor común) |
| Abreviatura sin definir | Bloqueante | Toda abreviatura usada existe en el diccionario o en `puntos_especiales` |
| Símbolo de gráfico sin leyenda | Bloqueante | Todo símbolo de la grilla figura en la leyenda |
| Filas de gráfico desparejas | Bloqueante | Cada fila produce el número de puntos esperado según el diccionario |
| Conteo de puntos incoherente | Advertencia | Si un paso declara `conteo`, se compara con el calculado cuando sea posible |
| Muestra vs. peso de hilo | Advertencia | La muestra cae fuera del rango CYC de la categoría |
| Medidas vs. muestra | Advertencia | Puntos montados ÷ muestra ≈ medida final (tolerancia 5%) |
| Metraje insuficiente | Advertencia | Ovillos × metros por ovillo menor que el metraje estimado, si se declara |
| Foto de baja resolución | Advertencia | Lado largo menor a 1600 px |
| Pocos talles | Advertencia | Prenda de adulto con menos de 6 talles |
| Abreviatura definida y no usada | Informativa | Se excluye del PDF |

### Otros requisitos

- Interfaz de línea de comandos: `generar-patron patron.yaml --salida patron.pdf --papel A4 --talle M --imprimir`.
- Salida en español e inglés a partir del mismo archivo cuando el diccionario tenga ambos idiomas.
- Código separado en capas (modelo, validación, composición, render) para sumar una interfaz web más adelante.
- Pruebas automáticas con al menos tres patrones de ejemplo: un suéter con talles (dos agujas), un chal con gráfico de calado y un amigurumi en crochet.
- Plantillas visuales en archivos aparte; agregar una nueva no requiere tocar el código.

## Criterios de aceptación y prompt para Claude Code

El programa está terminado cuando cumple todos estos puntos:

- [ ] Los tres patrones de ejemplo generan PDF sin errores bloqueantes.
- [ ] Cada PDF contiene las 14 secciones en orden (o las omite solo si son opcionales y no tienen datos).
- [ ] Todo número por talle aparece en notación `a (b, c, d)` y coincide con el YAML.
- [ ] La lista de abreviaturas del PDF contiene exactamente las usadas en las instrucciones.
- [ ] Los gráficos son vectoriales, numerados, con leyenda y repetición marcada, y legibles impresos en A4.
- [ ] El esquema muestra cotas con letras y tabla de medidas por talle.
- [ ] Un YAML con un error deliberado (talle faltante, abreviatura inexistente) produce un mensaje que indica archivo, campo y corrección.
- [ ] La opción `--talle M` genera la versión con ese talle resaltado.
- [ ] Las pruebas automáticas pasan.

### Prompt sugerido

```markdown
Adjunto la especificación "Generador de patrones de tejido". Construí el programa que describe.

1. Antes de escribir código, proponé el stack (lenguaje, motor de PDF, librería de validación de esquema)
   y la estructura de carpetas, y esperá mi aprobación.
2. Implementá primero el modelo de datos y el esquema de validación, con los tres patrones de ejemplo.
3. Después la expansión por talle, la composición de secciones y el render del PDF.
4. Después gráficos y esquema en SVG.
5. Al final, las validaciones de advertencia y la CLI.

Verificá los rangos del Craft Yarn Council contra la fuente oficial antes de cargarlos.
Usá los criterios de aceptación como lista de pruebas. Al terminar cada paso, mostrame un PDF de ejemplo.
```

**Preguntas abiertas para definir antes de empezar:** variante regional del español por defecto ("talle" o "talla", "punto bajo" o "medio punto"); si la v1 incluye inglés; y si los patrones se cargarán a mano en YAML o hará falta un formulario.
