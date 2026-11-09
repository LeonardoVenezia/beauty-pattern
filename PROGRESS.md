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

## Hitos 4-11

Pendientes.
