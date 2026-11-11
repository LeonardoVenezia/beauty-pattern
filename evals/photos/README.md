# Fotos reales para evaluar

Cada foto va en esta carpeta y tiene una entrada en `cases.json`:

```json
[
  {
    "id": "sueter-trenzas-01",
    "file": "sueter-trenzas-01.jpg",
    "expected": {
      "categoria": "pullover",
      "tecnica": "circular",
      "construccion": "raglan_top_down",
      "texturas": ["cables"]
    },
    "source": "foto propia / licencia CC-BY de ..."
  }
]
```

- `expected` lleva solo lo que se ve con seguridad en la foto. Los valores
  posibles son los de `engine/spec.py` (los mismos del prompt del extractor).
- Para varias fotos de la misma pieza, usar `"files": ["a.jpg", "b.jpg"]`
  en lugar de `file` (hasta 4; la primera es la vista general).
- `"motivo": true` marca un motivo radial de crochet (mandala, carpeta) que el
  patrón tiene que reproducir con la capa de diseño.
- `texturas` es la lista de texturas que tienen que aparecer (puede ser `[]`).
- Antes de commitear una foto, confirmar que hay derechos para usarla.

Correr (usa la IA real del `.env`; con `FAKE_AI=1` se niega, porque las
respuestas grabadas no miden nada):

```bash
set -a; source .env; set +a
make eval-fotos
```

El reporte queda en `evals/results/` (JSON y Markdown): precisión de la IA por
campo y una rúbrica determinista del patrón que sale de cada foto.
