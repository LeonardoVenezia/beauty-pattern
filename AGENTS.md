# AGENTS.md — Reglas de trabajo para agentes (Claude Code u otros)

> Este archivo está pensado para **opencode**, que lee `AGENTS.md` de la raíz del proyecto automáticamente. La configuración del agente (permisos, instrucciones) vive en `opencode.json`.

## Qué es este proyecto
Aplicación web que convierte **una foto de una prenda o pieza tejida** (por ejemplo, un suéter visto en Instagram) en un **patrón de tejido completo, calculado y verificable**, con un solo flujo simple. Leer `PROYECTO.md` para el diseño completo antes de escribir código.

Usuaria final: una persona tejedora (no técnica), probablemente desde el celular. Prioridad máxima: que el patrón **cierre matemáticamente** y se pueda tejer.

## Principio rector (no negociable)
**La IA interpreta; el código calcula.**

- Los modelos de IA (visión y lenguaje) solo pueden: extraer atributos de la foto, proponer elecciones, redactar texto a partir de números ya calculados y criticar un patrón ya generado.
- **Ningún número de un patrón** (puntos a montar, aumentos, disminuciones, vueltas, medidas, metraje) puede venir de un LLM. Todos salen de código determinista, testeado.
- Todo patrón generado debe pasar por el **simulador de puntos** (ver `PROYECTO.md`, sección "Verificación") antes de mostrarse. Si el simulador falla, el patrón no se entrega; se corrige el motor, no el simulador.

## Stack (fijado; no cambiar sin registrar la razón en `DECISIONS.md`)
- Backend: Python 3.12, FastAPI, Pydantic v2, uv para dependencias.
- Motor de patrones: paquete Python puro `engine/` sin dependencia de red ni de IA.
- Visión por computadora clásica: Pillow, OpenCV, scikit-learn (k-means), NumPy.
- IA del producto: **DeepSeek V4.1 Flash Fast**, servido por el proveedor **Refuseless** (id `refuseless/deepseek-v4.1-flash-fast`; usar exactamente la variante `-fast`). Un solo modelo cumple todos los roles de IA (extractor de atributos con visión, redactor y crítico), separados por prompts y llamadas independientes. Ver `PROYECTO.md`, sección 2.1.
  - El cliente de IA va detrás de una interfaz (`ai/client.py`) con proveedor, URL base, clave e id de modelo **100 % por variables de entorno** (`AI_PROVIDER`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`). No hay nombres de modelo ni URLs en el código.
  - **No asumas el formato de API de Refuseless.** Leé su documentación oficial al empezar el hito 1. Lo más probable es que sea compatible con OpenAI Chat Completions, pero verificalo; si no lo es, escribí el adaptador correspondiente.
  - Implementá un **sondeo de capacidades al arrancar** (ver `PROYECTO.md` 2.1): entrada de imágenes, salida JSON estructurada, tool calling. El sistema se adapta a lo que el endpoint realmente soporte.
  - Segmentación opcional con un modelo preexistente (por ejemplo `rembg` o SAM) detrás de una interfaz intercambiable.
- Render: SVG para esquemas y gráficos; PDF con WeasyPrint o ReportLab.
- Frontend: Next.js + TypeScript + Tailwind, mobile-first.
- Tests: pytest, hypothesis (property-based), Playwright para el flujo end to end.
- Calidad: ruff, mypy (estricto en `engine/`), pre-commit.

## Estructura esperada del repo
```
engine/          # motor determinista (garments/, stitches/, gauge/, charts/, simulator/, i18n/)
vision/          # extracción de atributos, cuantización de color, segmentación
ai/              # clientes de IA, prompts versionados, esquemas, evaluaciones
api/             # FastAPI
web/             # Next.js
render/          # SVG/PDF
tests/           # unit, property, golden, e2e
evals/           # fotos de prueba + resultados esperados
docs/
DECISIONS.md     # bitácora de decisiones tomadas por el agente
PROGRESS.md      # estado por hito
```

## Modo de trabajo del agente
1. **Autonomía total.** No hagas preguntas al usuario durante la ejecución. Ante una ambigüedad, elegí la opción más razonable, implementala y registrala en `DECISIONS.md` (decisión, alternativas, motivo).
2. **Hitos.** Trabajá en el orden de hitos de `PROYECTO.md`. Cada hito termina con tests en verde, `PROGRESS.md` actualizado y un commit.
3. **Commits pequeños y frecuentes** en una rama de trabajo (`build/main-agent`), con mensajes claros. No reescribas el historial. Nunca hagas `push --force`.
4. **Tests primero para el motor.** Cada familia de prenda necesita tests de propiedades (para muchas combinaciones de talle y densidad) y al menos un patrón "golden" verificado a mano o contra una fuente publicada.
5. **No inventes datos de tejido.** Convenciones (abreviaturas, ease, proporciones de talle, fórmulas de aumentos) se documentan con su fuente en `docs/fuentes.md`. Si algo no está respaldado, marcalo como `ASUNCIÓN` en el código y en `DECISIONS.md`.
6. **Honestidad de resultados.** Si un hito no se pudo completar o una verificación falla, dejalo escrito en `PROGRESS.md`; no lo marques como hecho.
7. **Secretos.** Las claves van en variables de entorno (`.env` fuera de git, `.env.example` versionado). Nunca en el código.
8. **Seguridad básica.** Validar subida de imágenes (tipo, tamaño, dimensiones), borrar EXIF, limitar tasa por IP, no ejecutar nada derivado de la salida de un modelo.

## Reglas de código
- Tipado completo; `engine/` pasa mypy estricto.
- Funciones del motor puras y sin efectos secundarios.
- Prompts de IA en archivos versionados (`ai/prompts/`), con esquema de salida en Pydantic; nunca texto libre sin validar.
- Toda llamada a IA tiene: timeout, reintentos acotados, caché por hash de imagen y prompt, registro de tokens/costo, y un modo `FAKE_AI=1` que devuelve respuestas grabadas para correr tests sin red ni costo.
- El modelo es barato y rápido, así que la fiabilidad se obtiene con **validación y redundancia**, no con confianza: salida siempre validada con Pydantic, un ciclo de reparación acotado (se le devuelve el error de validación al modelo, máximo 2 veces) y votación entre varias muestras para campos críticos (ver `PROYECTO.md` 3.1).
- Las imágenes se preprocesan antes de enviarse (orientación EXIF corregida y luego EXIF eliminado, redimensionado a un máximo de unos 1344 px por lado, recortes adicionales a mayor detalle para texturas y jacquard).
- Idiomas de interfaz y patrón: español (por defecto) e inglés. Textos en `engine/i18n/`.
- Unidades: cm y pulgadas; todo se calcula internamente en cm.

## Definición de "terminado" para un hito
- Tests unitarios, de propiedades y golden pasando.
- Simulador de puntos pasando para todos los patrones del hito.
- `ruff`, `mypy` y la suite completa en verde.
- `PROGRESS.md` y `DECISIONS.md` actualizados.
- Documentación mínima de uso en `docs/`.

## Comandos (el agente debe crear y mantener estos targets en un `Makefile`)
- `make setup` — instala dependencias.
- `make test` — suite completa.
- `make lint` — ruff + mypy.
- `make dev` — levanta API y web.
- `make eval` — corre las evaluaciones de `evals/` (usa IA real solo si hay clave).
- `make demo` — genera un patrón de ejemplo end to end con `FAKE_AI=1`.
