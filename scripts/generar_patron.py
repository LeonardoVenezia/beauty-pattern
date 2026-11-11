"""CLI: generar-patron patron.yaml --salida patron.pdf --papel A4 --talle M --imprimir

El archivo (YAML o JSON) tiene dos claves: `spec` (lo que se ve en la prenda,
GarmentSpec) y `params` (densidad, hilo, medidas, idioma; PatternParams).
Cada talle se genera y pasa por el simulador antes de entrar al PDF.
Los errores indican archivo, campo y que corregir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from engine.document import build_document
from engine.garments import GarmentError, generate_size_set
from engine.i18n import t
from engine.spec import GarmentSpec, PatternParams
from render.pdf import render_document_pdf


def _load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict) or "spec" not in data:
        raise ValueError("el archivo debe tener una clave 'spec' (y opcionalmente 'params')")
    return data


def _explain(path: Path, section: str, error: ValidationError) -> str:
    lines = []
    for issue in error.errors():
        field = ".".join(str(part) for part in (section, *issue["loc"]))
        lines.append(f"{path}: campo '{field}': {issue['msg']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generar-patron", description=__doc__)
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--salida", type=Path)
    parser.add_argument("--papel", choices=["A4", "Letter"], default="A4")
    parser.add_argument("--talle", help="talle a resaltar, p. ej. M")
    parser.add_argument("--imprimir", action="store_true", help="version para imprimir")
    parser.add_argument("--idioma", choices=["es", "en"])
    args = parser.parse_args(argv)

    try:
        data = _load(args.archivo)
    except (OSError, ValueError) as exc:
        print(f"{args.archivo}: {exc}", file=sys.stderr)
        return 2
    try:
        spec = GarmentSpec.model_validate(data["spec"])
    except ValidationError as exc:
        print(_explain(args.archivo, "spec", exc), file=sys.stderr)
        return 2
    try:
        params = PatternParams.model_validate(data.get("params") or {})
    except ValidationError as exc:
        print(_explain(args.archivo, "params", exc), file=sys.stderr)
        return 2
    if args.talle:
        params = params.model_copy(update={"talla": args.talle})
    try:
        patterns = generate_size_set(spec, params)
    except GarmentError as exc:
        language = args.idioma or params.idioma
        print(f"{args.archivo}: {t(exc.key, language, **exc.params)}", file=sys.stderr)
        return 1
    sizes = [p.meta.size for p in patterns]
    if args.talle and len(sizes) > 1 and args.talle not in sizes:
        print(
            f"{args.archivo}: talle '{args.talle}' no disponible; usar uno de {', '.join(sizes)}",
            file=sys.stderr,
        )
        return 2
    document = build_document(patterns, highlight=args.talle, lang=args.idioma)
    output = args.salida or args.archivo.with_suffix(".pdf")
    output.write_bytes(render_document_pdf(document, paper=args.papel, print_mode=args.imprimir))
    print(f"{output} (talles: {', '.join(sizes)})" if len(sizes) > 1 else str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
