"""Esquemas de las piezas del hogar (engine/garments/home.py).

Dibujos simples y rotulados, con las medidas reales de la IR verificada:
- pieza plana y alfombra: el circulo, ovalo o rectangulo con sus cotas;
- almohadon: el frente y, si es en sobre, como se superponen las dos mitades;
- funda redonda: vista de costado (paredes, base y boca) y la base vista
  desde abajo; correa si la hay;
- bolsita: el frente con la solapa, el doblez o el cierre;
- canasto: vista de costado con las asas y la base.
"""

from __future__ import annotations

from engine.i18n import t
from engine.ir import Pattern, Section
from render.draw import (
    FILL,
    FILL_ALT,
    STROKE,
    STROKE_SOFT,
    TEXT_SOFT,
    _f,
    caption,
    dashed_line,
    dim_h,
    dim_v,
    label,
    shape_path,
    shape_rect,
    svg_document,
    title_block,
)

WIDTH, HEIGHT = 900.0, 720.0
TOP, BOTTOM = 130.0, 600.0
K = 0.5523  # cubicas que aproximan un cuarto de elipse


def _ellipse(cx: float, cy: float, rx: float, ry: float) -> str:
    kx, ky = rx * K, ry * K
    return (
        f"M {_f(cx - rx)} {_f(cy)} "
        f"C {_f(cx - rx)} {_f(cy - ky)} {_f(cx - kx)} {_f(cy - ry)} {_f(cx)} {_f(cy - ry)} "
        f"C {_f(cx + kx)} {_f(cy - ry)} {_f(cx + rx)} {_f(cy - ky)} {_f(cx + rx)} {_f(cy)} "
        f"C {_f(cx + rx)} {_f(cy + ky)} {_f(cx + kx)} {_f(cy + ry)} {_f(cx)} {_f(cy + ry)} "
        f"C {_f(cx - kx)} {_f(cy + ry)} {_f(cx - rx)} {_f(cy + ky)} {_f(cx - rx)} {_f(cy)} Z"
    )


def _stadium(x: float, y: float, w: float, h: float) -> str:
    """Ovalo de crochet: lados rectos y extremos en medio circulo."""
    r = min(w, h) / 2
    k = r * K
    if w >= h:
        x1, x2 = x + r, x + w - r
        return (
            f"M {_f(x1)} {_f(y)} L {_f(x2)} {_f(y)} "
            f"C {_f(x2 + k)} {_f(y)} {_f(x + w)} {_f(y + r - k)} {_f(x + w)} {_f(y + r)} "
            f"C {_f(x + w)} {_f(y + r + k)} {_f(x2 + k)} {_f(y + h)} {_f(x2)} {_f(y + h)} "
            f"L {_f(x1)} {_f(y + h)} "
            f"C {_f(x1 - k)} {_f(y + h)} {_f(x)} {_f(y + r + k)} {_f(x)} {_f(y + r)} "
            f"C {_f(x)} {_f(y + r - k)} {_f(x1 - k)} {_f(y)} {_f(x1)} {_f(y)} Z"
        )
    return _stadium(x, y, h, w)  # pragma: no cover - el ovalo siempre va acostado


def _measure(pattern: Pattern, key: str) -> float | None:
    return next((m.value_cm for m in pattern.measurements if m.key == key), None)


def _fmt(pattern: Pattern, cm: float) -> str:
    if pattern.params.unidades == "in":
        return f"{round(cm / 2.54 * 2) / 2:g} in"
    return f"{round(cm * 2) / 2:g} cm"


def _name(key: str, lang: str) -> str:
    return t(f"measure.{key}", lang)


def _dim(pattern: Pattern, key: str, lang: str) -> tuple[str, ...]:
    value = _measure(pattern, key)
    return (_name(key, lang), _fmt(pattern, value or 0.0))


def _shape(section: Section) -> str:
    if "straight" in section.meta:
        return "oval"
    return "circle" if section.mode == "round" else "rect"


def _info(section: Section, pattern: Pattern, lang: str) -> str:
    craft = "crochet" if pattern.spec.tecnica.value == "crochet" else "knit"
    rows = sum(1 for step in section.steps if step.consumes or step.produces) - 1
    return t(f"schematic.home.info.{craft}.{section.mode}", lang, sts=section.end_stitches, rows=max(1, rows))


def _fit(w_cm: float, h_cm: float, box_w: float, box_h: float) -> tuple[float, float]:
    scale = min(box_w / max(w_cm, 0.1), box_h / max(h_cm, 0.1))
    return w_cm * scale, h_cm * scale


def _flat_shape(
    pattern: Pattern,
    section: Section,
    lang: str,
    cx: float,
    top: float,
    box_w: float,
    box_h: float,
) -> list[str]:
    """Pieza plana con cotas abajo y a la derecha."""
    parts: list[str] = []
    shape = _shape(section)
    if shape == "circle":
        d = _measure(pattern, "diameter") or 10.0
        w, h = _fit(d, d, box_w, box_h)
        x, y = cx - w / 2, top
        parts.append(shape_path(_ellipse(cx, y + h / 2, w / 2, h / 2), fill=FILL))
        for frac in (0.66, 0.33):  # vueltas sugeridas
            parts.append(shape_path(_ellipse(cx, y + h / 2, w / 2 * frac, h / 2 * frac), fill="none", stroke=STROKE_SOFT, width=1))
        parts += dim_h(x, x + w, y + h + 34, _dim(pattern, "diameter", lang), extension=-30)
    else:
        oval_like = shape == "oval" or pattern.meta.family == "home_basket"
        long_key, short_key = ("length", "width") if oval_like else ("width", "length")
        if pattern.meta.family == "home_pouch":
            long_key, short_key = "width", "height"
        wc = _measure(pattern, long_key) or 20.0
        hc = _measure(pattern, short_key) or 20.0
        w, h = _fit(wc, hc, box_w, box_h)
        x, y = cx - w / 2, top
        if shape == "oval":
            parts.append(shape_path(_stadium(x, y, w, h), fill=FILL))
            parts.append(dashed_line(x + h / 2, y + h / 2, x + w - h / 2, y + h / 2))
            parts.append(label(cx, y + h / 2 - 8, t("schematic.home.chain", lang), size=10, color=TEXT_SOFT))
        else:
            parts.append(shape_rect(x, y, w, h, fill=FILL))
        parts += dim_h(x, x + w, y + h + 34, _dim(pattern, long_key, lang), extension=-30)
        parts += dim_v(y, y + h, x + w + 26, _dim(pattern, short_key, lang), side="right", extension=-22)
    return parts


def _flat_svg(pattern: Pattern, lang: str) -> list[str]:
    section = pattern.sections[0]
    parts = _flat_shape(pattern, section, lang, WIDTH / 2 - 40, TOP + 10, 460, 360)
    copies = section.meta.get("copies", 1)
    note = t("schematic.home.make_two" if copies == 2 else "schematic.cut_one", lang)
    parts.append(label(WIDTH / 2 - 40, BOTTOM + 30, note, size=13, weight="700"))
    parts.append(label(WIDTH / 2 - 40, BOTTOM + 50, _info(section, pattern, lang), size=11, color=TEXT_SOFT))
    if any(n.key.startswith("finishing.home.hanging_loop") for n in pattern.finishing):
        parts.append(label(WIDTH / 2 - 40, BOTTOM + 68, t("schematic.home.loop", lang), size=11, color=TEXT_SOFT))
    return parts


def _pillow_svg(pattern: Pattern, lang: str) -> list[str]:
    front = pattern.sections[0]
    if len(pattern.sections) == 1:  # dos caras iguales
        return _flat_svg(pattern, lang)
    parts = _flat_shape(pattern, front, lang, 290, TOP + 30, 340, 340)
    parts.append(label(290, TOP + 10, t(front.name_key, lang), size=13, weight="700"))
    # Espalda en sobre: dos mitades superpuestas.
    bx, by, bw, bh = 600.0, TOP + 60, 200.0, 200.0
    upper = 0.6 * bh
    parts.append(shape_rect(bx, by, bw, upper, fill=FILL))
    parts.append(shape_rect(bx, by + bh - upper, bw, upper, fill=FILL_ALT))
    parts.append(dashed_line(bx, by + bh - upper, bx + bw, by + bh - upper))
    parts.append(label(bx + bw / 2, by - 14, t(pattern.sections[1].name_key, lang), size=12, weight="700"))
    parts.append(label(bx + bw / 2, by + bh + 22, t("schematic.home.envelope", lang), size=10, color=TEXT_SOFT))
    return parts


def _cozy_svg(pattern: Pattern, lang: str) -> list[str]:
    parts: list[str] = []
    height = _measure(pattern, "height") or 10.0
    circ = _measure(pattern, "circumference") or 20.0
    top_circ = _measure(pattern, "home_top")
    width_cm = circ / 3.1416
    w, h = _fit(width_cm, height, 260, 380)
    cx, y0 = 300.0, TOP + 40
    y1 = y0 + h
    ry = w * 0.12
    top_w = w * (top_circ / circ) if top_circ else w
    shoulder = y0 + h * 0.3 if top_circ else y0
    path = (
        f"M {_f(cx - top_w / 2)} {_f(y0)} L {_f(cx - w / 2)} {_f(shoulder)} L {_f(cx - w / 2)} {_f(y1)} "
        f"C {_f(cx - w / 2)} {_f(y1 + ry * 1.3)} {_f(cx + w / 2)} {_f(y1 + ry * 1.3)} {_f(cx + w / 2)} {_f(y1)} "
        f"L {_f(cx + w / 2)} {_f(shoulder)} L {_f(cx + top_w / 2)} {_f(y0)} Z"
    )
    parts.append(shape_path(path, fill=FILL))
    parts.append(shape_path(_ellipse(cx, y0, top_w / 2, ry * top_w / w), fill="#ffffff"))
    base_rounds = len(pattern.sections[0].steps)
    parts.append(dashed_line(cx - w / 2, y1, cx + w / 2, y1))
    parts += dim_v(y0, y1, cx + w / 2 + 34, _dim(pattern, "height", lang), side="right", extension=-30)
    parts.append(label(cx, y1 + ry + 40, f"{_name('circumference', lang)}: {_fmt(pattern, circ)}", size=12))
    if top_circ:
        parts.append(label(cx, y0 - ry - 14, f"{_name('home_top', lang)}: {_fmt(pattern, top_circ)}", size=12))
    strap = _measure(pattern, "home_strap")
    if strap:
        parts.append(
            f'<path d="M {_f(cx - w / 2 + 6)} {_f(y0 + 14)} C {_f(cx - w)} {_f(y0 - 150)}, '
            f'{_f(cx + w)} {_f(y0 - 150)}, {_f(cx + w / 2 - 6)} {_f(y0 + 14)}" fill="none" '
            f'stroke="{STROKE_SOFT}" stroke-width="4" stroke-dasharray="8 5"/>'
        )
        parts.append(label(cx + w / 2 + 40, y0 - 60, f"{_name('home_strap', lang)}: {_fmt(pattern, strap)}", size=11, anchor="start"))
    # Base vista desde abajo.
    bx, by, r = 680.0, TOP + 150, 90.0
    parts.append(shape_path(_ellipse(bx, by, r, r), fill=FILL_ALT))
    parts.append(shape_path(_ellipse(bx, by, r * 0.5, r * 0.5), fill="none", stroke=STROKE_SOFT, width=1))
    parts.append(label(bx, by - r - 16, t("section.home_base", lang), size=13, weight="700"))
    parts.append(label(bx, by + r + 24, t("schematic.home.base_rounds", lang, n=base_rounds, sts=pattern.sections[0].end_stitches), size=11, color=TEXT_SOFT))
    return parts


def _pouch_svg(pattern: Pattern, lang: str) -> list[str]:
    section = pattern.sections[0]
    parts: list[str] = []
    flap = _measure(pattern, "home_flap")
    wc = _measure(pattern, "width") or 10.0
    hc = _measure(pattern, "height") or 10.0
    total_h = hc + (flap or 0)
    w, h_all = _fit(wc, total_h, 420, 380)
    h = h_all * hc / total_h
    cx = WIDTH / 2 - 40
    x, y = cx - w / 2, TOP + 20 + (h_all - h)
    parts.append(shape_rect(x, y, w, h, fill=FILL))
    if flap:
        fh = h_all - h
        parts.append(shape_rect(x, y - fh, w, fh + 2, fill=FILL_ALT))
        parts.append(dashed_line(x, y, x + w, y))
        parts.append(f'<circle cx="{_f(cx)}" cy="{_f(y + 10)}" r="7" fill="#ffffff" stroke="{STROKE}" stroke-width="1.5"/>')
        parts += dim_v(y - fh, y, x - 26, _dim(pattern, "home_flap", lang), side="left", extension=22)
    if any(n.key == "finishing.home.zipper" for n in pattern.finishing):
        zig = " ".join(f"{_f(x + 10 + i * 8)},{_f(y + (4 if i % 2 else -4))}" for i in range(int((w - 20) / 8) + 1))
        parts.append(f'<polyline points="{zig}" fill="none" stroke="{STROKE}" stroke-width="1.5"/>')
        parts.append(label(cx, y - 14, t("schematic.home.zipper", lang), size=11, color=TEXT_SOFT))
    if section.mode == "flat":  # agujas: tira doblada
        parts.append(label(cx, y + h - 10, t("schematic.fold", lang), size=10, color=TEXT_SOFT))
    else:
        parts.append(label(cx, y + h - 10, t("schematic.home.closed_bottom", lang), size=10, color=TEXT_SOFT))
    parts += dim_h(x, x + w, y + h + 34, _dim(pattern, "width", lang), extension=-30)
    parts += dim_v(y, y + h, x + w + 26, _dim(pattern, "height", lang), side="right", extension=-22)
    parts.append(label(cx, BOTTOM + 40, t("schematic.home.pouch_note", lang), size=11, color=TEXT_SOFT))
    return parts


def _basket_svg(pattern: Pattern, lang: str) -> list[str]:
    base, walls = pattern.sections[0], pattern.sections[1]
    parts: list[str] = []
    height = _measure(pattern, "height") or 10.0
    shape = _shape(base)
    if shape == "circle":
        width_cm = _measure(pattern, "diameter") or 20.0
    else:
        width_cm = _measure(pattern, "length") or 20.0
    w, h = _fit(width_cm, height, 330, 300)
    cx, y0 = 290.0, TOP + 60
    y1 = y0 + h
    ry = w * (0.14 if shape == "circle" else 0.08)
    path = (
        f"M {_f(cx - w / 2)} {_f(y0)} L {_f(cx - w / 2)} {_f(y1)} "
        f"C {_f(cx - w / 2)} {_f(y1 + ry * 1.3)} {_f(cx + w / 2)} {_f(y1 + ry * 1.3)} {_f(cx + w / 2)} {_f(y1)} "
        f"L {_f(cx + w / 2)} {_f(y0)} Z"
    )
    parts.append(shape_path(path, fill=FILL))
    parts.append(shape_path(_ellipse(cx, y0, w / 2, ry), fill="#ffffff"))
    if any(step.note_key == "home.note.handles_open" for step in walls.steps):
        hw = min(70.0, w * 0.3)
        parts.append(shape_rect(cx - hw / 2, y0 + 18, hw, 14, rx=7, fill="#ffffff"))
        parts.append(label(cx, y0 + 52, t("schematic.home.handle", lang), size=10, color=TEXT_SOFT))
    parts += dim_v(y0, y1, cx + w / 2 + 30, _dim(pattern, "height", lang), side="right", extension=-26)
    # Base, vista desde arriba.
    bx, by = 690.0, TOP + 120
    parts.append(label(bx, by - 30, t("section.home_base", lang), size=13, weight="700"))
    parts += _flat_shape(pattern, base, lang, bx - 20, by, 170, 170)
    parts.append(label(cx, y1 + ry + 44, _info(walls, pattern, lang), size=11, color=TEXT_SOFT))
    return parts


def render_home_svg(pattern: Pattern, lang: str) -> str:
    fam = pattern.meta.family
    if fam == "home_cozy":
        parts = _cozy_svg(pattern, lang)
    elif fam == "home_pouch":
        parts = _pouch_svg(pattern, lang)
    elif fam == "home_basket":
        parts = _basket_svg(pattern, lang)
    elif fam == "home_pillow":
        parts = _pillow_svg(pattern, lang)
    else:
        parts = _flat_svg(pattern, lang)
    title = t(pattern.meta.title_key, lang)
    unit = t(f"unit.{pattern.params.unidades}", lang)
    head = title_block(WIDTH, 42, title, t("schematic.measures_in", lang, unit=unit))
    tail = [caption(WIDTH, HEIGHT - 20, t("schematic.caption", lang))]
    return svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), head + parts + tail)
