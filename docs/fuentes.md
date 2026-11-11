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

## Densidad de crochet, agujas y ganchillos

- **Fuente:** Craft Yarn Council, *Standard Yarn Weight System*
  (<https://www.craftyarncouncil.com/standards/yarn-weight-system>,
  verificado el 2026-11-11). Rangos de punto bajo por 4 in y tamanos de aguja
  y ganchillo por categoria.
- **Uso:** `engine/gauge.py` (`CROCHET_SC_PER_10CM`, punto medio del rango) y
  `engine/materials.py` (aguja/ganchillo cerca del punto medio del rango).
  Los patrones de crochet sin muestra medida usan esta referencia y no la de
  dos agujas.
- **ASUNCION:** CYC no publica vueltas. Alto y ancho relativos al punto bajo:
  pb 1,0 x 1,1; pma 0,95 x 0,75; pa 0,9 x 0,55. Lace (publicado en pa) se
  toma como 32 pb.

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
- Canesu circular: profundidad objetivo = sisa de la tabla + 4 cm; para manga
  corta se reduce para que entren copa y puno (ASUNCION).
- Manga encajada (construccion clasica de abajo hacia arriba): la sisa quita
  por lado la diferencia entre el medio contorno y el ancho de espalda de la
  tabla; **ASUNCION:** 40 % se cierra al inicio de las 2 hileras siguientes y
  el resto con 1 disminucion por lado en hileras del LD; luego recto hasta la
  profundidad de sisa. Copa: mismo cierre, disminuciones en hileras del LD,
  2 pts cerrados al inicio de 4 hileras y cierre del resto; alto de copa =
  65 % de la sisa (**ASUNCION**). Escote recto (los pts centrales quedan
  libres al coser los hombros).
- Piezas planas: cuerpo, mangas, cuello y tapas de botones rectangulares; sin
  forma de sisa, escote ni ojales en esta version (ASUNCION).
- Gorro: 10 % de holgura negativa sobre el contorno de cabeza y corona con
  4 disminuciones por vuelta hasta 4 puntos (ASUNCION). El contorno de cabeza
  por talle es una ASUNCION.
- Bufanda, chal y manta: dimensiones rectangulares por defecto (25x180,
  60x180 y 100x120 cm) editables por `dimensiones_cm` (ASUNCION).
- Mitones: piezas planas de mano y pulgar, sin dedos individuales (ASUNCION).
- Medias: tubo con puno, pierna, pie y puntera; sin talon en esta version
  (ASUNCION).
- Amigurumi: anillo magico de 6 puntos bajos, esfera/ cilindro/ cono con
  aumentos y disminuciones de 6 puntos por vuelta; el granny square de esta
  version es un cuadrado solido simplificado (ASUNCION).

Todas las ASUNCIONES estan registradas tambien en `DECISIONS.md`.

## Granny square clasico

- **Construccion:** granny square tradicional en redondo: vuelta 1 con
  4 grupos de 3 pa separados por 2 cad en un anillo; cada vuelta siguiente
  teje (3 pa, 2 cad, 3 pa) en cada esquina y 3 pa en cada espacio de 1 cad.
  Es la construccion de dominio publico mas difundida en crochet.
- **Conteo:** vuelta n = 4n grupos (12n pa) y 4n + 4 cad. El simulador lo
  verifica como 16n + 4 puntos.
- **ASUNCION:** cada vuelta agrega el alto de una vuelta de pa a cada lado del
  cuadrado (lado = 2 x vueltas x alto de pa). El anillo se considera absorbido
  en la primera vuelta.

## Paneles de textura en el cuerpo

- **Uso:** `engine/garments/panels.py`. Trenzas, calados, bodoques y nido de
  abeja vistos en la foto se tejen como un panel centrado en la espalda y el
  delantero del cuerpo (raglán y canesú circular), con 2 pts rev de borde y,
  en trenzas, 2 rev entre columnas. El panel ocupa cerca del 40 % del ancho
  de cada parte.
- **Redondo:** las hileras del revés de la versión plana se tejen con el
  punto contrario y en orden inverso (convención estándar).
- **Compensación del ancho:** no se usa una regla genérica (no hay una fuente
  confiable de cuánto cierra cada trenza). Si la persona mide el ancho de
  una repetición del gráfico en su muestra (`params.panel_motivo_cm`), el
  panel de W pts equivale a E pts de jersey y se agregan W − E pts junto al
  panel al empezar, que se quitan antes del borde, la sisa recta final o el
  escote. Sin ese dato no se compensa y el patrón lo avisa. Si el motivo no
  cierra (calados), no se compensa.
- El canesú y las mangas quedan en jersey.

## Elasticos y jersey en plano

- La hilera del reves se teje "como se presentan los puntos": vista desde el
  LD (invertida y con der <-> rev) coincide con la del LD. Test:
  `tests/test_catalog.py::test_flat_ribs_keep_their_columns`. Antes los
  elasticos 1x1, 2x2 y 3x1 en plano tejian arroz o damero.

## Escote redondo en piezas planas

- **Uso:** `engine/garments/rows.py` (`plan_crew_neck`, `neck_sections`) en
  manga encajada, hombro caído y chaleco. Se cierran los pts centrales del
  delantero y cada hombro se teje por separado, disminuyendo 1 pt del lado
  del escote en las hileras del LD hasta los pts de hombro de la espalda (el
  simulador verifica la unión).
- **ASUNCION:** 7 cm de profundidad; 20 % del ancho del escote se disminuye
  por lado; la tira levanta todos los pts cerrados y 3 de cada 4 hileras de
  los costados del escote. La espalda termina recta. Si hay panel de
  textura, termina en el escote (los pts centrales se cierran).
