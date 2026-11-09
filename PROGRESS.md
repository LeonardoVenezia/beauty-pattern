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

## Hitos 2-11

Pendientes.
