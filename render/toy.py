"""Esquema de un juguete (amigurumi): el muneco armado.

Cada pieza es una forma simple (circulo, pera, capsula, triangulo) con el
tamano que sale de la IR verificada: contorno maximo y vueltas de cada
seccion. Las formas que se paran o se acuestan (cuadrupedo, alargado) se ven
de costado; el resto, de frente. Los rotulos van en una columna a la derecha,
con lineas guia, para que ningun texto quede encima del dibujo.

El dibujo se arma en cm (eje y hacia arriba, el piso en 0) y recien al final
se escala para entrar en la hoja.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from math import cos, pi, sin

from engine.garments.toy import (
    FIGURES,
    TOY_SIZE_MEASURES,
    FigureKit,
    pattern_plan,
    resolve_body,
    toy_pieces,
)
from engine.i18n import t
from engine.ir import Pattern, Section
from engine.rounding import round_half_up
from engine.spec import resolve_gauge
from render.draw import (
    FILL,
    FILL_ALT,
    STROKE,
    TEXT,
    TEXT_SOFT,
    _f,
    caption,
    dim_h,
    dim_v,
    label,
    title_block,
)
from render.draw import svg_document as _svg_document

WIDTH, HEIGHT = 900.0, 720.0
TOP, BOTTOM = 120.0, 640.0
FIG_CX = 330.0  # centro del muneco
FIG_W = 400.0  # ancho disponible para el muneco
LABEL_X = 610.0
K = 0.5523  # cubicas que aproximan un cuarto de elipse

Point = tuple[float, float]
Emit = Callable[[Callable[[float], float], Callable[[float], float], float], str]


def _ellipse_d(cx: float, cy: float, rx: float, ry: float) -> str:
    """Elipse como path (svglib no maneja bien <ellipse> con estilos)."""
    kx, ky = rx * K, ry * K
    return (
        f"M {_f(cx - rx)} {_f(cy)} "
        f"C {_f(cx - rx)} {_f(cy - ky)} {_f(cx - kx)} {_f(cy - ry)} {_f(cx)} {_f(cy - ry)} "
        f"C {_f(cx + kx)} {_f(cy - ry)} {_f(cx + rx)} {_f(cy - ky)} {_f(cx + rx)} {_f(cy)} "
        f"C {_f(cx + rx)} {_f(cy + ky)} {_f(cx + kx)} {_f(cy + ry)} {_f(cx)} {_f(cy + ry)} "
        f"C {_f(cx - kx)} {_f(cy + ry)} {_f(cx - rx)} {_f(cy + ky)} {_f(cx - rx)} {_f(cy)} Z"
    )


def _spread_labels(wanted: list[float], gap: float, low: float, high: float) -> list[float]:
    """Rotulos lo mas cerca posible de su pieza, sin pisarse."""
    placed: list[float] = []
    for y in wanted:
        placed.append(max(y, low, placed[-1] + gap if placed else low))
    overflow = placed[-1] - high if placed else 0.0
    if overflow > 0:
        placed[-1] -= overflow
        for index in range(len(placed) - 2, -1, -1):
            placed[index] = min(placed[index], placed[index + 1] - gap)
    return placed


@dataclass(frozen=True)
class _Piece:
    section: Section
    circ: float  # contorno maximo (cm)
    length: float  # largo sobre el tejido (cm)

    @property
    def diameter(self) -> float:
        return self.circ / pi


def _pieces(pattern: Pattern) -> dict[str, _Piece]:
    gauge = resolve_gauge(pattern.params)
    out: dict[str, _Piece] = {}
    for section in pattern.sections:
        top = section.meta.get("max_stitches", section.end_stitches)
        rows = section.meta.get("row_count", len(section.steps))
        out[section.id] = _Piece(section, gauge.cm_for_stitches(top), gauge.cm_for_rows(rows))
    return out


@dataclass
class _Scene:
    """Formas en cm por capa (0 atras, 1 cuerpo, 2 adelante) y anclas de
    los rotulos."""

    pieces: dict[str, _Piece]
    variants: dict[str, str] = field(default_factory=dict)
    shapes: list[tuple[int, Emit]] = field(default_factory=list)
    points: list[Point] = field(default_factory=list)
    anchors: dict[str, Point] = field(default_factory=dict)

    def ellipse(
        self, cx: float, cy: float, rx: float, ry: float, *, fill: str = FILL, layer: int = 1, width: float = 2
    ) -> None:
        self.points += [(cx - rx, cy - ry), (cx + rx, cy + ry)]

        def emit(X: Callable[[float], float], Y: Callable[[float], float], s: float) -> str:
            d = _ellipse_d(X(cx), Y(cy), rx * s, ry * s)
            stroke = STROKE if width else "none"
            return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{_f(width)}"/>'

        self.shapes.append((layer, emit))

    def poly(self, pts: list[Point], *, fill: str = FILL, layer: int = 1, closed: bool = True, width: float = 2) -> None:
        self.points += pts

        def emit(X: Callable[[float], float], Y: Callable[[float], float], s: float) -> str:
            d = "M " + " L ".join(f"{_f(X(x))} {_f(Y(y))}" for x, y in pts) + (" Z" if closed else "")
            paint = fill if closed else "none"
            return f'<path d="{d}" fill="{paint}" stroke="{STROKE}" stroke-width="{_f(width)}" stroke-linejoin="round"/>'

        self.shapes.append((layer, emit))

    def tube(self, pts: list[Point], width_cm: float, *, layer: int = 1, fill: str = FILL) -> None:
        """Trazo grueso con borde (cola, brazo curvo, tentaculo)."""
        self.points += [(x - width_cm / 2, y - width_cm / 2) for x, y in pts]
        self.points += [(x + width_cm / 2, y + width_cm / 2) for x, y in pts]

        def emit(X: Callable[[float], float], Y: Callable[[float], float], s: float) -> str:
            d = "M " + " L ".join(f"{_f(X(x))} {_f(Y(y))}" for x, y in pts)
            w = max(2.0, width_cm * s)
            return (
                f'<path d="{d}" fill="none" stroke="{STROKE}" stroke-width="{_f(w + 4)}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
                f'<path d="{d}" fill="none" stroke="{fill}" stroke-width="{_f(w)}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )

        self.shapes.append((layer, emit))

    def tapered(self, pts: list[Point], widths: list[float], *, layer: int = 1) -> None:
        """Tubo de ancho variable: primero todos los bordes y despues el
        relleno, para que los tramos no dejen costuras dibujadas."""
        widest = max(widths)
        self.points += [(x, y - widest / 2) for x, y in pts] + [(x, y + widest / 2) for x, y in pts]

        def emit(X: Callable[[float], float], Y: Callable[[float], float], s: float) -> str:
            segs = [
                (f"M {_f(X(a[0]))} {_f(Y(a[1]))} L {_f(X(b[0]))} {_f(Y(b[1]))}", max(2.0, w * s))
                for a, b, w in zip(pts, pts[1:], widths, strict=False)
            ]
            edge = "".join(
                f'<path d="{d}" fill="none" stroke="{STROKE}" stroke-width="{_f(w + 4)}" stroke-linecap="round"/>'
                for d, w in segs
            )
            body = "".join(
                f'<path d="{d}" fill="none" stroke="{FILL}" stroke-width="{_f(w)}" stroke-linecap="round"/>'
                for d, w in segs
            )
            return edge + body

        self.shapes.append((layer, emit))

    def capsule(self, cx: float, top: float, w: float, h: float, *, layer: int = 1) -> None:
        """Capsula vertical (brazo, pierna) de `top` hacia abajo."""
        h = max(h, w)
        self.tube([(cx, top - w / 2), (cx, top - h + w / 2)], w, layer=layer)

    def dot(self, cx: float, cy: float, r: float, *, layer: int = 3, min_px: float = 2.5) -> None:
        def emit(X: Callable[[float], float], Y: Callable[[float], float], s: float) -> str:
            return f'<circle cx="{_f(X(cx))}" cy="{_f(Y(cy))}" r="{_f(max(min_px, r * s))}" fill="{TEXT}"/>'

        self.shapes.append((layer, emit))

    def anchor(self, piece_id: str, x: float, y: float) -> None:
        if piece_id in self.pieces and piece_id not in self.anchors:
            self.anchors[piece_id] = (x, y)

    def get(self, piece_id: str) -> _Piece | None:
        return self.pieces.get(piece_id)


@dataclass(frozen=True)
class _Head:
    x: float
    y: float
    r: float
    side: bool  # de costado: la cara mira a la derecha


# ---------------------------------------------------------------------------
# Partes de la cabeza y del cuerpo (kit).
# ---------------------------------------------------------------------------


def _kind(scene: _Scene, piece_id: str, kit: FigureKit) -> str:
    """Clase del kit de una pieza (la variante con que se tejio)."""
    del kit
    return scene.variants.get(piece_id, piece_id)


def _draw_head(scene: _Scene, head: _Head, kit: FigureKit) -> None:
    hx, hy, r = head.x, head.y, head.r
    _draw_hair(scene, head, kit)  # la melena va detras de las orejas
    ear = scene.get("ear")
    if ear is not None:
        kind = _kind(scene, "ear", kit)
        sides = (1,) if head.side else (-1, 1)
        for side in sides:
            bx = hx + side * r * (0.5 if not head.side else -0.15)
            if kind == "ear_long":
                w, h = ear.circ / 2, ear.length
                cx, cy = bx * 0.85 + hx * 0.15, hy + r * 0.8 + h / 2
                scene.ellipse(cx, cy, w / 2, h / 2, layer=0)
                scene.ellipse(cx, cy, w / 4, h * 0.36, fill=FILL_ALT, layer=0, width=1)
                scene.anchor("ear", cx, cy + h * 0.3)
            elif kind == "ear_pointy":
                w, h = ear.circ / 2, ear.length
                by = hy + r * 0.62
                tip = (bx + side * w * 0.15, by + h * 0.95)
                scene.poly([(bx - w / 2, by), tip, (bx + w / 2, by)], layer=0)
                scene.anchor("ear", bx, by + h * 0.5)
            elif kind in {"ear_floppy", "ear_flat", "ear_cup"}:
                w, h = ear.circ / 2, max(ear.length, ear.diameter)
                # (x del centro, y del centro, semiancho, semialto) en radios y largos.
                if head.side:
                    cx, cy, rx, ry = {
                        "ear_floppy": (hx - r * 0.25, hy + r * 0.2 - h * 0.35, w * 0.3, h * 0.55),
                        "ear_flat": (hx - r * 0.35, hy, w * 0.4, h * 0.75),
                        "ear_cup": (hx - r * 0.3, hy + r * 0.75, w * 0.3, h * 0.45),
                    }[kind]
                else:
                    cx, cy, rx, ry = {
                        "ear_floppy": (hx + side * (r + w * 0.05), hy + r * 0.2 - h * 0.3, w * 0.42, h * 0.55),
                        "ear_flat": (hx + side * (r + w * 0.2), hy + r * 0.1, w * 0.55, h * 0.75),
                        "ear_cup": (hx + side * (r + w * 0.15), hy + r * 0.45, w * 0.45, h * 0.4),
                    }[kind]
                layer = 2 if head.side else 0
                scene.ellipse(cx, cy, rx, ry, layer=layer)
                scene.ellipse(cx, cy, rx * 0.55, ry * 0.6, fill=FILL_ALT, layer=layer, width=1)
                scene.anchor("ear", cx + side * rx * 0.4, cy)
            else:  # redonda
                er = ear.diameter / 2
                # Sobre el borde de la cabeza, a 40 grados de la vertical.
                cx = hx + (side * r * 0.64 if not head.side else -r * 0.2)
                cy = hy + r * (0.77 if not head.side else 0.98)
                scene.ellipse(cx, cy, er, er, layer=0)
                scene.ellipse(cx, cy, er / 2, er / 2, fill=FILL_ALT, layer=0, width=0)
                scene.anchor("ear", cx + er * 0.3, cy + er * 0.3)
    horn = scene.get("horn")
    if horn is not None:
        spiral = _kind(scene, "horn", kit) == "horn_spiral"
        w, h = horn.circ / 2 * 0.7, horn.length
        bases = [(hx + (r * 0.1 if head.side else 0), hy + r * 0.85)] if spiral else [
            (hx + s * r * 0.3, hy + r * 0.85) for s in ((1,) if head.side else (-1, 1))
        ]
        for bx, by in bases:
            scene.poly([(bx - w / 2, by), (bx, by + h), (bx + w / 2, by)], layer=0, fill=FILL_ALT)
            if spiral:
                for k in (0.3, 0.55, 0.78):
                    y = by + h * k
                    half = w / 2 * (1 - k)
                    scene.poly([(bx - half, y - h * 0.05), (bx + half, y + h * 0.05)], closed=False, layer=0, width=1)
            scene.anchor("horn", bx + w * 0.2, by + h * 0.5)
    antenna = scene.get("antenna")
    if antenna is not None:
        for side in (1,) if head.side else (-1, 1):
            bx, by = hx + side * r * 0.3, hy + r * 0.9
            tip = (bx + side * r * 0.25, by + antenna.length)
            scene.tube([(bx, by), tip], antenna.diameter * 0.5, layer=0)
            scene.ellipse(tip[0], tip[1], antenna.diameter * 0.6, antenna.diameter * 0.6, layer=0)
            scene.anchor("antenna", tip[0], tip[1])
    bump = scene.get("eyebump")
    eye_y = hy + r * 0.05
    eye_x = r * 0.4
    if bump is not None:
        br = bump.diameter / 2
        eye_y = hy + r * 0.7
        for side in (1,) if head.side else (-1, 1):
            cx = hx + side * r * 0.45
            scene.ellipse(cx, eye_y, br, br, layer=2)
            scene.dot(cx, eye_y, br * 0.35)
            scene.anchor("eyebump", cx + br * 0.4, eye_y + br * 0.3)
    elif head.side:
        scene.dot(hx + r * 0.45, eye_y, r * 0.1)
    else:
        for side in (-1, 1):
            scene.dot(hx + side * eye_x, eye_y, r * 0.1)
    # Hocico, trompa o pico.
    muzzle, trunk, beak = scene.get("muzzle"), scene.get("trunk"), scene.get("beak")
    my = hy - r * 0.35
    if muzzle is not None:
        kind = _kind(scene, "muzzle", kit)
        md = muzzle.diameter
        cx = hx + (r * 0.85 if head.side else 0)
        rx, ry = (md * 0.35, md * 0.5) if head.side else (md * 0.55, md * 0.42)
        scene.ellipse(cx, my, rx, ry, fill=FILL_ALT, layer=2)
        if kind == "muzzle":
            scene.ellipse(cx + (rx * 0.5 if head.side else 0), my + ry * 0.35, r * 0.1, r * 0.07, fill=TEXT, layer=3, width=1)
        else:
            for side in (-1, 1):
                scene.dot(cx + side * rx * 0.35, my, r * 0.05)
        scene.anchor("muzzle", cx + rx * 0.5, my - ry * 0.3)
    elif trunk is not None:
        w, h = trunk.diameter, trunk.length
        if head.side:
            pts = [(hx + r * 0.8, my + r * 0.2), (hx + r * 0.8 + h * 0.4, my - h * 0.2), (hx + r * 0.9 + h * 0.5, my - h * 0.7)]
        else:
            pts = [(hx, my + r * 0.1), (hx, my - h * 0.6), (hx + h * 0.25, my - h * 0.9)]
        scene.tube(pts, w, layer=2)
        scene.anchor("trunk", pts[-1][0], pts[-1][1])
    elif beak is not None:
        w, h = beak.circ / 2 * 0.8, beak.length
        if head.side:
            bx, by = hx + r * 0.9, hy - r * 0.15
            scene.poly([(bx, by + w / 2), (bx + h, by), (bx, by - w / 2)], fill=FILL_ALT, layer=2)
            scene.anchor("beak", bx + h * 0.6, by)
        else:
            by = hy - r * 0.15
            scene.poly([(hx - w / 2, by + w * 0.15), (hx, by - h), (hx + w / 2, by + w * 0.15)], fill=FILL_ALT, layer=3)
            scene.anchor("beak", hx + w * 0.2, by - h * 0.4)
    elif kit.face in {"nose", "nose_cat"}:
        scene.ellipse(hx + (r * 0.9 if head.side else 0), hy - r * 0.2, r * 0.08, r * 0.06, fill=TEXT, layer=3, width=1)
    if kit.face in {"mouth", "mouth_frog"}:
        span = r * (0.5 if kit.face == "mouth_frog" else 0.2)
        mx = hx + (r * 0.6 if head.side else 0)
        scene.poly([(mx - span, hy - r * 0.3), (mx, hy - r * 0.45), (mx + span, hy - r * 0.3)], closed=False, layer=3, width=1.5)


def _draw_hair(scene: _Scene, head: _Head, kit: FigureKit) -> None:
    hx, hy, r = head.x, head.y, head.r
    if kit.hair == "mane":
        n = 16
        pts = []
        for k in range(n * 2 + 1):
            a = 2 * pi * k / (n * 2)
            rr = r * (1.45 if k % 2 == 0 else 1.2)
            pts.append((hx + rr * cos(a), hy + rr * sin(a)))
        scene.poly(pts, fill=FILL_ALT, layer=0)
    elif kit.hair == "doll":
        scene.ellipse(hx, hy + r * 0.12, r * 1.12, r * 1.05, fill=FILL_ALT, layer=0)
        for side in (-1, 1):
            scene.tube([(hx + side * r * 0.9, hy), (hx + side * r * 1.0, hy - r * 1.2)], r * 0.4, layer=0, fill=FILL_ALT)
    elif kit.hair == "unicorn":
        if head.side:
            for k in range(5):
                y = hy + r * (0.8 - k * 0.3)
                bx = hx - r * (0.5 + 0.1 * k)
                scene.tube([(bx, y), (bx - r * 0.35, y - r * 0.25)], r * 0.12, layer=0, fill=FILL_ALT)
        else:
            for k in range(4):
                bx = hx - r * (0.05 + 0.15 * k)
                scene.tube([(bx, hy + r * 0.97), (bx - r * 0.3, hy + r * (0.55 - 0.1 * k))], r * 0.12, layer=2, fill=FILL_ALT)


def _draw_tail(scene: _Scene, kit: FigureKit, base: Point, direction: int, unit: float) -> None:
    """Cola desde `base`, hacia el lado `direction` (+1 derecha, -1 izquierda)."""
    tail = scene.get("tail")
    bx, by = base
    if tail is not None:
        kind = _kind(scene, "tail", kit)
        if kind == "tail_pompom":
            tr = tail.diameter / 2
            scene.ellipse(bx + direction * tr * 0.3, by, tr, tr, layer=0)
            scene.anchor("tail", bx + direction * tr, by)
        elif kind in {"tail_long", "tail_curly"}:
            L = tail.length
            if kind == "tail_curly":
                pts = [(bx, by)] + [
                    (bx + direction * (L * 0.15 + L * 0.12 * cos(a / 6 * pi)), by + L * 0.12 * sin(a / 6 * pi))
                    for a in range(0, 13)
                ]
            else:
                pts = [(bx, by), (bx + direction * L * 0.45, by + L * 0.05), (bx + direction * L * 0.6, by + L * 0.45)]
            scene.tube(pts, tail.diameter, layer=0)
            scene.anchor("tail", pts[-1][0], pts[-1][1])
        else:  # cono o muñon
            L, w = tail.length, tail.diameter
            tip = (bx + direction * L * 0.9, by + L * 0.35)
            scene.poly([(bx, by + w * 0.5), tip, (bx, by - w * 0.5)], layer=0)
            scene.anchor("tail", bx + direction * L * 0.6, by + L * 0.2)
    fluke = scene.get("fluke")
    if fluke is not None:
        w, L = fluke.circ / 2, fluke.length + fluke.diameter
        for s in (-1, 1):
            tip = (bx + direction * L * 0.9, by + s * L * 0.6)
            scene.poly([(bx, by), (tip[0] - direction * w * 0.2, tip[1] + s * w * 0.3), tip], layer=0)
        scene.anchor("fluke", bx + direction * L * 0.7, by + L * 0.4)
    if kit.hair == "unicorn":
        u = unit * 0.12
        scene.tube([(bx, by), (bx + direction * u, by - u * 0.5), (bx + direction * u * 1.2, by - u * 1.6)], u * 0.6, layer=0, fill=FILL_ALT)


def _draw_sides(scene: _Scene, cx: float, cy: float, half_w: float, side_view: bool) -> None:
    """Alas y aletas a los costados (o una de costado)."""
    for pid in ("wing", "fin"):
        part = scene.get(pid)
        if part is None:
            continue
        w, h = part.circ / 2, part.length
        sides = (1,) if side_view else (-1, 1)
        for side in sides:
            x = cx + (side * (half_w + w * 0.15) if not side_view else 0)
            scene.ellipse(x, cy, (w / 2 if not side_view else h / 2), (h / 2 if not side_view else w / 2),
                          layer=0 if not side_view else 2)
            scene.anchor(pid, x + w * 0.3, cy - h * 0.2)


def _draw_spines(scene: _Scene, pts: list[Point]) -> None:
    spine = scene.get("spine")
    if spine is None:
        return
    w, h = spine.circ / 2 * 0.8, spine.length
    for (x, y) in pts:
        scene.poly([(x - w / 2, y - h * 0.1), (x, y + h * 0.9), (x + w / 2, y - h * 0.1)], layer=0, fill=FILL_ALT)
    mid = pts[len(pts) // 2]
    scene.anchor("spine", mid[0], mid[1] + h * 0.5)


# ---------------------------------------------------------------------------
# Formas de cuerpo.
# ---------------------------------------------------------------------------


def _upright(scene: _Scene, kit: FigureKit, plan: str, craft: str, pattern: Pattern) -> None:
    """En piezas, de una pieza o de pie en dos piernas: de frente."""
    p = scene.pieces
    gauge = resolve_gauge(pattern.params)
    arm, leg = p["arm"], p["leg"]
    if plan == "seamless":
        one = p["head_body"]
        section = one.section
        counts = [s.stitch_count_end for s in section.steps]
        neck_count = min(counts[len(counts) // 3 : len(counts) * 5 // 6] or counts)
        neck = gauge.cm_for_stitches(neck_count) / pi
        bw = gauge.cm_for_stitches(max(counts[: len(counts) // 2])) / pi
        hd = gauge.cm_for_stitches(max(counts[len(counts) // 2 :])) / pi
        bh = max(bw * 0.9, one.length - hd * 1.4 - bw * 0.3)
        body_id, head_id = "head_body", "head_body"
    else:
        body = p["body"]
        hd = p["head"].diameter
        bw = body.diameter
        neck = gauge.cm_for_stitches(body.section.end_stitches) / pi
        base_units = body.section.meta.get("base_units", 0) * (1 if craft == "crochet" else 2)
        bh = 0.9 * (body.length - gauge.cm_for_rows(base_units))
        body_id, head_id = "body", "head"
    lift = 0.0
    if plan == "biped":
        lift = leg.length * 0.9 - leg.diameter * 0.3
    head_cy = lift + bh + hd / 2 - 0.1 * hd
    # Piernas.
    if plan == "biped":
        for side in (-1, 1):
            scene.capsule(side * bw * 0.22, lift + leg.diameter * 0.3, leg.diameter, lift + leg.diameter * 0.3)
        scene.anchor("leg", bw * 0.22 + leg.diameter * 0.3, lift * 0.4)
    # Brazos.
    aw = arm.diameter
    for side in (-1, 1):
        scene.capsule(side * (neck / 2 + aw * 0.45), lift + bh - aw * 0.2, aw, arm.length * 0.95, layer=0)
    scene.anchor("arm", neck / 2 + aw * 0.75, lift + bh - arm.length * 0.6)
    # Cuerpo (pera) y cabeza.
    scene.poly(
        [(0, lift), (-bw * 0.42, lift + bh * 0.08), (-bw * 0.5, lift + bh * 0.45), (-neck / 2, lift + bh),
         (neck / 2, lift + bh), (bw * 0.5, lift + bh * 0.45), (bw * 0.42, lift + bh * 0.08)],
    )
    scene.anchor(body_id, bw * 0.12, lift + bh * 0.4)
    scene.ellipse(0, head_cy, hd / 2, hd / 2)
    scene.anchor(head_id, hd * 0.3, head_cy + hd * 0.22)
    _draw_head(scene, _Head(0, head_cy, hd / 2, False), kit)
    _draw_sides(scene, 0, lift + bh * 0.55, bw * 0.45, False)
    _draw_tail(scene, kit, (bw * 0.45, lift + bh * 0.18), 1, bh)
    _draw_spines(scene, [(bw * 0.5 + 0.0, lift + bh * k) for k in (0.25, 0.45, 0.65, 0.85)] + [(hd * 0.35, head_cy + hd * 0.42)])
    if "shell" in p:
        shell = p["shell"]
        scene.ellipse(0, lift + bh * 0.5, shell.diameter * 0.5, bh * 0.5, fill=FILL_ALT, layer=0)
        scene.anchor("shell", -shell.diameter * 0.45, lift + bh * 0.5)
    if kit.hair == "fleece":
        _fleece(scene, 0, lift + bh * 0.5, bw * 0.5, bh * 0.5)
    if plan != "biped":
        ld = leg.diameter
        for side in (-1, 1):
            cx = side * bw * 0.26
            scene.ellipse(cx, ld * 0.3, ld / 2, ld * 0.55, layer=2)
            scene.ellipse(cx, ld * 0.25, ld * 0.25, ld * 0.3, fill=FILL_ALT, layer=2, width=1)
        scene.anchor("leg", bw * 0.26 + ld * 0.3, ld * 0.3)


def _fleece(scene: _Scene, cx: float, cy: float, rx: float, ry: float) -> None:
    """Lana de oveja: bolitas sobre el contorno."""
    for k in range(14):
        a = 2 * pi * k / 14
        scene.ellipse(cx + rx * cos(a), cy + ry * sin(a), rx * 0.18, rx * 0.18, fill=FILL_ALT, layer=0, width=1)


def _ball(scene: _Scene, kit: FigureKit) -> None:
    p = scene.pieces
    ball = p["ball"]
    d = 2 * ball.length / pi
    r = d / 2
    foot = p.get("foot")
    if "shell" in p:
        shell = p["shell"]
        scene.ellipse(0, r * 1.05, shell.diameter / 2, r * 0.75, fill=FILL_ALT, layer=0)
        scene.anchor("shell", -shell.diameter * 0.45, r * 1.2)
    if kit.hair == "fleece":
        _fleece(scene, 0, r, r, r)
    scene.ellipse(0, r, r, r)
    scene.anchor("ball", r * 0.45, r * 1.25)
    _draw_head(scene, _Head(0, r * 1.1, r * 0.75, False), kit)
    _draw_sides(scene, 0, r * 0.8, r * 0.95, False)
    _draw_tail(scene, kit, (r * 0.9, r * 0.5), 1, d)
    _draw_spines(scene, [(r * cos(a), r + r * sin(a)) for a in (0.2, 0.6, 1.0, 1.4, 1.8)])
    if foot is not None:
        fd = foot.diameter
        for side in (-1, 1):
            scene.ellipse(side * r * 0.4, fd * 0.15, fd / 2, fd * 0.4, layer=2)
        scene.anchor("foot", r * 0.4 + fd * 0.3, fd * 0.15)


def _quadruped(scene: _Scene, kit: FigureKit) -> None:
    """De costado: patas, cuerpo acostado, cabeza adelante (a la derecha)."""
    p = scene.pieces
    body, head, leg = p["body"], p["head"], p["leg"]
    bd = body.diameter
    bl = max(bd, body.length * 0.95)
    ld, ll = leg.diameter, leg.length
    leg_top = ll * 0.9 - ld / 2 + bd * 0.3
    body_cy = leg_top + bd * 0.2
    for k, x in enumerate((-bl * 0.32, -bl * 0.22, bl * 0.22, bl * 0.32)):
        scene.capsule(x, leg_top, ld, leg_top, layer=0 if k % 2 else 2)
    scene.anchor("leg", bl * 0.32 + ld * 0.4, leg_top * 0.4)
    scene.ellipse(0, body_cy, bl / 2, bd / 2)
    scene.anchor("body", -bl * 0.1, body_cy)
    if "shell" in p:
        shell = p["shell"]
        scene.ellipse(-bl * 0.05, body_cy + bd * 0.3, min(shell.diameter * 0.5, bl * 0.55), bd * 0.45, fill=FILL_ALT, layer=2)
        scene.anchor("shell", -bl * 0.05, body_cy + bd * 0.55)
    if kit.hair == "fleece":
        _fleece(scene, 0, body_cy, bl / 2, bd / 2)
    hd = head.diameter
    hx, hy = bl / 2 + hd * 0.15, body_cy + bd * 0.35
    scene.ellipse(hx, hy, hd / 2, hd / 2, layer=3)
    scene.anchor("head", hx + hd * 0.1, hy + hd * 0.35)
    head_box = _Head(hx, hy, hd / 2, True)
    _draw_tail(scene, kit, (-bl / 2, body_cy + bd * 0.15), -1, bd)
    _draw_spines(scene, [(x, body_cy + bd / 2 * (1 - (x / (bl / 2)) ** 2) ** 0.5 * 0.95) for x in (-bl * 0.3, -bl * 0.15, 0, bl * 0.15, bl * 0.3)])
    _draw_sides(scene, 0, body_cy, bl / 2, True)
    _draw_head_layer(scene, head_box, kit)


def _draw_head_layer(scene: _Scene, head: _Head, kit: FigureKit) -> None:
    """Partes de la cabeza por encima del cuerpo (vista de costado)."""
    before = len(scene.shapes)
    _draw_head(scene, head, kit)
    # La cabeza (capa 3) va delante del cuerpo: sus partes de atras quedan
    # entre el cuerpo y la cabeza, y las de adelante, encima.
    scene.shapes[before:] = [(layer + 2, emit) for layer, emit in scene.shapes[before:]]


def _snake(scene: _Scene, kit: FigureKit, pattern: Pattern) -> None:
    """De costado: tubo de la cola (izquierda) a la cabeza (derecha)."""
    p = scene.pieces
    long = p["long"]
    gauge = resolve_gauge(pattern.params)
    counts = [s.stitch_count_end for s in long.section.steps]
    body_d = gauge.cm_for_stitches(counts[len(counts) // 2]) / pi
    head_d = gauge.cm_for_stitches(max(counts[len(counts) * 2 // 3 :])) / pi
    total = long.length * 0.95
    r = body_d / 2
    hr = head_d / 2
    neck = total - head_d
    cy = max(r, hr)
    if kit.long == "segments":
        n = 5
        step = neck / n
        for k in range(n):
            scene.ellipse(step * (k + 0.5), cy, step * 0.62, r)
    else:
        # Serpiente ondulada: la cola se afina en el primer 40 % del largo.
        taper = total * 0.4
        amp = r * 1.3

        def center(x: float) -> float:
            return cy + amp * sin(2 * pi * x / (neck * 0.55)) * (1 - x / neck)

        n = 28
        xs = [neck * k / n for k in range(n + 1)]
        widths = [body_d * min(1.0, 0.25 + 0.75 * x / taper) for x in xs[1:]]
        scene.tapered([(x, center(x)) for x in xs], widths)
    scene.anchor("long", neck * 0.5, cy)
    hx = neck + hr * 0.8
    scene.ellipse(hx, cy, hr, hr, layer=3)
    head_box = _Head(hx, cy, hr, True)
    _draw_sides(scene, neck * 0.55, cy - r * 0.3, r, True)
    _draw_tail(scene, kit, (0.0, cy), -1, body_d)
    _draw_head_layer(scene, head_box, kit)


def _radial(scene: _Scene, kit: FigureKit) -> None:
    """De frente: cupula arriba, falda y tentaculos colgando."""
    p = scene.pieces
    dome, tentacle = p["dome"], p["tentacle"]
    d = 2 * dome.length / pi
    r = d / 2
    tl = tentacle.length * 0.9
    tw = tentacle.diameter * 0.8
    cy = tl + r * 0.75
    start = cy - r * 0.7
    for k in range(6):
        x = -r * 0.8 + r * 1.6 * k / 5
        pts = [(x, start)]
        for j in range(1, 13):
            pts.append((x + tw * 0.6 * sin(j * pi / 3 + k), start - tl * j / 12))
        scene.tube(pts, tw, layer=0)
    scene.anchor("tentacle", -r * 0.8 + r * 1.6 * 4 / 5, start - tl * 0.6)
    skirt = p.get("skirt")
    if skirt is not None:
        sr = r * 1.15
        pts = []
        for k in range(17):
            x = sr - 2 * sr * k / 16
            pts.append((x, cy - r * 0.68 - (r * 0.12 if k % 2 else 0)))
        scene.poly([(-sr * 0.9, cy - r * 0.38), (sr * 0.9, cy - r * 0.38), *pts], fill=FILL_ALT, layer=2)
        scene.anchor("skirt", sr * 0.85, cy - r * 0.6)
    scene.ellipse(0, cy, r, r * 0.95, layer=1)
    scene.anchor("dome", r * 0.45, cy + r * 0.45)
    _draw_head(scene, _Head(0, cy, r, False), kit)


def render_toy_svg(pattern: Pattern, lang: str) -> str:
    figure, plan = pattern_plan(pattern)
    kit = FIGURES[figure]
    craft = "crochet" if pattern.spec.tecnica.value == "crochet" else "knit"
    body = pattern.spec.cuerpo_juguete or FIGURES[figure].default
    variants = {piece.id: piece.variant or piece.id for piece in toy_pieces(figure, resolve_body(figure, body)[0])}
    scene = _Scene(_pieces(pattern), variants)
    side = plan in {"quadruped", "dachshund", "snake"}
    if plan == "ball":
        _ball(scene, kit)
    elif plan in {"quadruped", "dachshund"}:
        _quadruped(scene, kit)
    elif plan == "snake":
        _snake(scene, kit, pattern)
    elif plan == "radial":
        _radial(scene, kit)
    else:
        _upright(scene, kit, plan, craft, pattern)
    return _finish(pattern, lang, craft, scene, side, plan in {"dachshund", "snake"})


def _finish(pattern: Pattern, lang: str, craft: str, scene: _Scene, side: bool, long: bool) -> str:
    """Escala, rotulos, cota y documento: comun a todas las formas."""
    xs = [x for x, _ in scene.points]
    ys = [y for _, y in scene.points]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span_h = max(max_y - min_y, 1e-6)
    span_w = max(max_x - min_x, 1e-6)
    room_h = BOTTOM - TOP - (90 if long else 30)
    scale = min(room_h / span_h, FIG_W / span_w)
    base_y = BOTTOM - (75 if long else 15)

    def X(cm: float) -> float:
        return FIG_CX + (cm - (min_x + max_x) / 2) * scale

    def Y(cm: float) -> float:
        return base_y - (cm - min_y) * scale

    drawn = [emit(X, Y, scale) for _, emit in sorted(scene.shapes, key=lambda item: item[0])]

    # Rotulos: columna a la derecha, en el orden vertical de las piezas.
    rows_word = "schematic.toy_info." + craft
    labels: list[str] = []
    anchors: list[tuple[float, float, Section]] = []
    for section in pattern.sections:
        ax, ay = scene.anchors.get(section.id, ((min_x + max_x) / 2, (min_y + max_y) / 2))
        anchors.append((X(ax), Y(ay), section))
    anchors.sort(key=lambda item: item[1])
    spots = _spread_labels([a[1] for a in anchors], 42.0, TOP + 10, BOTTOM - 20)
    for (ax, ay, section), ly in zip(anchors, spots, strict=True):
        name = t(section.name_key, lang)
        info = t(
            rows_word,
            lang,
            sts=section.meta.get("max_stitches", 0),
            rows=section.meta.get("row_count", 0),
        )
        labels.append(f'<circle cx="{_f(ax)}" cy="{_f(ay)}" r="2.6" fill="{STROKE}"/>')
        labels.append(
            f'<path d="M {_f(ax)} {_f(ay)} L {_f(LABEL_X - 30)} {_f(ly)} L {_f(LABEL_X - 6)} {_f(ly)}" '
            f'fill="none" stroke="{STROKE}" stroke-width="0.8"/>'
        )
        labels.append(label(LABEL_X, ly + 4, name, size=12, anchor="start", weight="700", color=TEXT))
        labels.append(label(LABEL_X, ly + 19, info, size=10, anchor="start", color=TEXT_SOFT))

    # Tamano (alto a la izquierda, o largo debajo), fuera del dibujo.
    size = next((m.value_cm for m in pattern.measurements if m.key in TOY_SIZE_MEASURES), span_h)
    units = pattern.params.unidades
    shown = size / 2.54 if units == "in" else size
    value = f"{round_half_up(shown * 2) / 2:g} {units}"  # como la ficha tecnica
    if long:
        dims = dim_h(X(min_x), X(max_x), Y(min_y) + 48, (t("measure.length", lang), value), extension=-24)
    else:
        dims = dim_v(Y(max_y), Y(min_y), min(X(min_x) - 28, 190.0), (t("measure.height", lang), value), side="left", extension=12)

    title = t(pattern.meta.title_key, lang)
    unit = t("unit.cm" if units == "cm" else "unit.in", lang)
    note = "schematic.toy_note_side" if side else "schematic.toy_note"
    parts = [
        *title_block(WIDTH, 42, title, t("schematic.measures_in", lang, unit=unit)),
        *drawn,
        *dims,
        *labels,
        caption(WIDTH, HEIGHT - 20, t(note, lang)),
    ]
    return _svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), parts)


def render_round_chart_svg(pattern: Pattern, section_id: str, lang: str) -> str | None:
    """Grafico de simbolos de las vueltas de aumento de una pieza al crochet
    (anillo magico y aumentos repartidos), como el de los motivos: cada
    simbolo sale del punto donde se teje. Las vueltas parejas y las
    disminuciones siguen en el texto."""
    from engine.document import growth_rounds
    from engine.stitches.kinds import StitchKind
    from render.crochet_chart import draw_rounds
    from render.crochet_chart import legend as chart_legend

    section = next((s for s in pattern.sections if s.id == section_id), None)
    if section is None or not section.steps:
        return None
    grow = growth_rounds(section.steps)
    width, size = 900.0, 640.0
    fills = [FILL if index % 2 else FILL_ALT for index in range(len(grow))]
    parts, used = draw_rounds(
        grow,
        [StitchKind.SC] * len(grow),
        [False] * len(grow),
        fills,
        width / 2,
        110 + size / 2,
        size / 2,
    )
    y = 110 + size + 40
    parts.append(label(width / 2, y, t("chart.round_inc", lang), size=12, color=TEXT_SOFT))
    parts += chart_legend(used, lang, 90, y + 44, width - 180)
    title = t(section.name_key, lang)
    head = title_block(width, 42, title, t("doc.round_chart_sub", lang, n=len(grow)))
    return _svg_document(width, y + 110, title, t("doc.charts", lang), head + parts)
