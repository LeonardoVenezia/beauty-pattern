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
patron, lo pasa por el simulador y escribe texto, un diagrama de piezas SVG y
PDF en `data/demo/`. Si el simulador falla, el comando termina con error y no
escribe el PDF. El diagrama y los números se calculan de forma determinista
desde la IR verificada (la IA no dibuja).

## Generar un PDF desde un archivo (CLI)

```bash
make patron ARCHIVO=examples/sueter-raglan.yaml TALLE=M
uv run python -m scripts.generar_patron examples/granny-square.yaml \
  --salida granny.pdf --papel Letter --imprimir
```

El archivo YAML o JSON tiene `spec` (lo que se ve en la prenda) y `params`
(hilo, densidad, medidas, idioma). Las prendas salen con todos los talles en
notación `a (b, c)` y el talle elegido resaltado. Los errores indican el
archivo y el campo a corregir.

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
subir foto -> revisar atributos detectados -> elegir hilo, muestra y las
medidas o el talle que correspondan -> ver el patron verificado (texto con
instrucciones abreviadas y glosario, y diagrama de piezas acotado) -> descargar
PDF o esquema SVG.

El texto comprime vueltas repetitivas de forma presentacional (rangos/ciclos
con conteo final) pero los números son los de la IR verificada; el diagrama de
piezas se deriva del perfil de puntos y las medidas de la IR (mismo SVG en web
y PDF). Con `FAKE_AI=1` la extraccion es simulada; la web funciona igual y
sirve para probar todo el flujo sin red ni costo.

## Familias disponibles

El motor genera pullover raglán top-down, pullover hombro caído, pullover con
canesú circular, pullover con manga encajada, cardigan y chaleco. También genera
gorro, bufanda, cuello circular, mitones, medias tubulares, chal rectangular,
manta rectangular, bolso rectangular y una pieza plana genérica. Las familias
planas se tejen en piezas y se cosen; el canesú no incluye gráfico de jacquard
en esta versión y la manga encajada usa una copa simplificada. El patrón
siempre se pasa por el simulador antes de mostrarse.

Para accesorios se pueden enviar medidas propias en
`params.dimensiones_cm` (por ejemplo `{"width": 30, "length": 150}`,
`{"head": 57}` o `{"foot_length": 26}`).

Los amigurumis son juguetes en piezas (cabeza, cuerpo, brazos, piernas y,
según la figura, orejas, hocico y cola), en crochet o con dos agujas, con
relleno y armado. En crochet también se generan un granny square
sólido simplificado, una bufanda plana, un bolso rectangular y una pieza plana
genérica. Si la foto muestra un cuadrado o módulo de crochet, la categoría es
**Cuadrado / granny square** y la medida que se pide es el lado; no es un bolso
salvo que se vean asas, abertura o volumen.

En crochet, la opción **Manta** también se genera como un módulo granny square
(se pide el lado del módulo); no calcula una manta completa ni la cantidad y
unión de módulos.

Para amigurumi se usa `dimensiones_cm["height"]` (altura sentado; si falta,
una por defecto según el grosor del hilo) y la figura con `spec.figura`
(`bear`, `bunny`, `cat` o `generic`; sin figura, un muñeco sin orejas). El granny
square usa `dimensiones_cm["size"]`; el bolso y la pieza plana usan `width` y
`length`.

El bolso y la pieza plana son paneles rectangulares: no incluyen asas, forro,
cierre ni uniones de módulos. La pieza plana es el recurso para una foto que no
se reconoce como una categoría concreta; se advierte en el patrón. Los mitones
se generan como dos piezas reutilizables (mano y pulgar) que se cortan dos veces
cada una y se cosen.

### Hogar (crochet y dos agujas)

`engine/garments/home.py` calcula cinco categorías; el subtipo lo da la IA
(`objeto_plano`, `forma_plana`, `objeto_funda`) y las medidas, si faltan, son
las de un objeto común (ver `docs/fuentes.md`, "Hogar"):

| Categoría | Subtipo | `dimensiones_cm` |
|---|---|---|
| `flat_item` | `coaster`, `placemat`, `potholder`, `dishcloth`, `doily`; forma `circle`, `square`, `rectangle`, `oval` | `diameter` (círculo), `width` (cuadrado), `width` + `length` |
| `cozy` redonda | `mate`, `thermos`, `cup`, `bottle` | medidas del objeto: `diameter`, `height` (alto a cubrir), `top_diameter` (boca), `strap` (largo de la correa) |
| `cozy` plana | `phone`, `glasses`, `pencil_case`, `laptop` | medidas del objeto: `width`, `height`, `depth` |
| `basket` | forma `circle`, `square`, `rectangle`, `oval` | base como `flat_item` + `height` |
| `pillow` | forma | medida del relleno (`width` + `length` o `diameter`) |
| `rug` | forma | como `flat_item` |

- Círculos al crochet: anillo y aumentos parejos en cada vuelta (6 en pb, 8 en
  mpa, 12 en pa), escalonados en las vueltas pares. En agujas: desde el centro
  en redondo, 8 gajos.
- Óvalo (solo crochet): cadena trabajada por los dos lados, aumentos en las
  curvas. En agujas se entrega un rectángulo y se avisa.
- Cuadrados y rectángulos: en hileras (agujas: punto bobo, la muestra se mide en
  bobo).
- Fundas redondas: base cerrada + paredes rectas con holgura negativa (abrazan);
  la de mate se cierra hacia la boca y la de termo trae correa. Bolsitas: al
  crochet sin costuras (cadena por los dos lados); en agujas, una tira doblada.
  Cartuchera con cierre; notebook con solapa y botón.
- Canasto: tejido apretado, base + paredes; desde 12 cm de alto, dos asas
  (aberturas opuestas). Almohadón: crochet, dos caras unidas; agujas, frente +
  espalda en sobre.

## Medidas propias y talle

La pantalla de medidas se adapta a la categoría:

- **Prendas** (pullover, cardigan, chaleco): muestra talle, holgura y medidas
  corporales.
- **Accesorios y crochet** (gorro, bufanda, mitones, bolso, amigurumi, etc.):
  no muestra talle; muestra solo las medidas que usa esa categoría.

Si dejás un campo vacío, se usa el valor típico de la categoría (o del talle en
las prendas). Las medidas se envían como `medidas_cm` para prendas y como
`dimensiones_cm` para accesorios, crochet y piezas del hogar. Las categorías sin
familia disponible se marcan antes de generar y no se envían al motor.

## Modo tejiendo, contador y proyectos

Después de generar el patrón, la sección **Modo tejiendo** muestra una vuelta a
la vez con el conteo de puntos y la nota de esa vuelta. Podés avanzar, volver o
reiniciar el contador; el contador no modifica el patrón. En navegadores
compatibles, **Mantener pantalla encendida** usa el Wake Lock API.

**Guardar proyecto** guarda el patrón, el texto y la posición del contador en
el almacenamiento local de ese navegador (localStorage). La lista de proyectos
guardados aparece en la pantalla de inicio. No se sincroniza entre dispositivos
y no requiere cuenta. Los patrones también quedan guardados en la base SQLite
de la API por id, para descargar PDF/SVG.

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
