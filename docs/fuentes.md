# Fuentes de convenciones de tejido

Cada convencion usada por el motor se documenta aca. Lo que no tiene fuente
publica verificada se marca **ASUNCION**.

## Densidad por grosor de hilo

- **Fuente:** Craft Yarn Council, *Standard Yarn Weight System* (rangos de
  muestra por categoria de hilo).
- **Uso:** `engine/gauge.py` toma el punto medio de cada rango, expresado en
  puntos y vueltas por 10 cm. Son valores de referencia editables por la
  persona; no reemplazan la muestra real.
- **Valores:** lace 36/48, fingering 30/40, sport 24/32, dk 22/30,
  worsted 18/24, bulky 14/18, super bulky 9/12.

## Tabla de talles

- **Fuente de los rangos:** Craft Yarn Council, *Standard Body Measurements*
  (contornos de pecho/cintura/cadera por talle).
- **Uso:** `engine/sizes.py` usa puntos medios redondeados de esos rangos.
- **ASUNCION:** largos de cuerpo, largo de manga, contorno de brazo, cuello y
  espalda son valores intermedios de trabajo, no una tabla publicada.

## Holgura (ease)

- **ASUNCION:** entallado -2 cm, regular +6 cm, holgado +12 cm, muy holgado
  +20 cm sobre el contorno de pecho.
- **Motivo:** son valores habituales en patronaje de punto, pero no se
  verificaron contra una fuente unica. La persona puede sobrescribirlos con
  `PatternParams.ease_cm`.

## Abreviaturas y nombres de puntos

- **Fuente:** convenciones habituales de tejido a dos agujas y crochet en
  espanol e ingles (der/rev, k/p, pb/sc, pa/dc, etc.).
- **Uso:** `engine/i18n/es.py` y `engine/i18n/en.py`, con variante
  principiante (nombres completos) y experta (abreviaturas).

## Formulas de reparto de aumentos y disminuciones

- **ASUNCION documentada:** `engine/distribution.py`. Grupos lo mas parejos
  posible (diferencia maxima 1), resto repartido desde el centro hacia afuera,
  aumentos simetricos M1L/M1R. Es un algoritmo propio, deterministico y
  testeado, no una formula publicada.

## Construcciones

- Raglan top-down: reparto de canesu en 30 % espalda, 30 % delantero, 20 % por
  manga (ASUNCION), linea de raglan de 1 punto, 8 aumentos cada dos vueltas.
  **ASUNCION:** canesu compuesto (aumentos de cuerpo y manga pueden separarse),
  4 cm de axila, 4 cm de holgura de brazo, 4 cm de ruedo/puno, 3 cm de cuello
  (8 cm en cuello alto), mangas corta/tres cuartos/larga; si el canesu estandar
  no deja lugar para la manga pedida, se aumenta en cada vuelta. Sin mangas se
  rechaza (familia chaleco). Ver `DECISIONS.md` D010.
- Hombro caido: mangas rectangulares, sisa recta, sin copa (ASUNCION de
  proporcion: largo de sisa = 18-24 % del contorno de pecho).
- Canesu circular: profundidad de canesu = 18-22 % del contorno de pecho
  (ASUNCION).
- Manga encajada: copa con disminuciones simetricas y sisa calculada
  (ASUNCION basada en proporciones clasicas de sastreria de punto).
- Gorro: corona con disminuciones en 6 sectores, 10-12 % de holgura negativa
  sobre el contorno de cabeza (ASUNCION).
- Medias: talon con lengueta, gusset y puntera con disminuciones simetricas
  (proporciones ASUNCION).
- Amigurumi: anillo magico de 6 puntos bajos, esfera/ cilindro/ cono con
  aumentos y disminuciones uniformes (ASUNCION).

Todas las ASUNCIONES estan registradas tambien en `DECISIONS.md`.
