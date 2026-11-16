"""Graficos de jacquard (fair isle) para guardas horizontales.

Biblioteca chica de motivos geometricos ORIGINALES, definidos por reglas en
codigo (no se copia ningun grafico publicado): damero, puntitos, crucecitas,
zigzag, rombo, arbolito y estrella de simetria octogonal. Cada motivo se
genera para una altura disponible y se le aplica un "cortador de flotes" que
garantiza que ningun color quede sin tejer mas de `MAX_FLOAT` puntos seguidos
en una vuelta (contando la vuelta como circular, porque la repeticion da la
vuelta entera).

Todo es determinista y puro: la IA no elige numeros ni dibuja celdas.
"""

from __future__ import annotations

import colorsys
from collections.abc import Callable
from dataclasses import dataclass

from engine.i18n import t

# ASUNCION: flote maximo de 5 puntos, el limite habitual que se recomienda
# para jacquard en prendas (flotes mas largos se enganchan); ver
# docs/fuentes.md.
MAX_FLOAT = 5

FG = "#"
BG = "."

# Colores por defecto si la foto no trajo paleta suficiente.
DEFAULT_PALETTE = ("#efe8d8", "#2f3e5c", "#b0413e", "#c9a227")


@dataclass(frozen=True)
class ColorworkChart:
    """Un grafico de guarda: filas de abajo hacia arriba, `#` = contraste."""

    number: int  # numero del grafico en el documento (1, 2, ...)
    motif: str  # clave del motivo (i18n: colorwork.motif.<motif>)
    rows: tuple[str, ...]
    background: int  # indice de color en la paleta (0 = A)
    contrast: int

    def __post_init__(self) -> None:
        if not self.rows or len({len(r) for r in self.rows}) != 1:
            raise ValueError("el grafico necesita filas del mismo ancho")
        if any(set(r) - {FG, BG} for r in self.rows):
            raise ValueError("celdas invalidas en el grafico")

    @property
    def width(self) -> int:
        return len(self.rows[0])

    @property
    def height(self) -> int:
        return len(self.rows)

    def color_at(self, row: int, col: int) -> int:
        """Color (indice de paleta) de la fila `row` (1 = abajo) y la columna
        `col` (1 = derecha, como se lee el grafico)."""
        cell = self.rows[row - 1][self.width - col]
        return self.contrast if cell == FG else self.background

    def contrast_cells(self) -> int:
        return sum(r.count(FG) for r in self.rows)


def max_float(row: str) -> int:
    """Flote mas largo de una vuelta circular que repite `row`.

    Una vuelta de un solo color no tiene flotes (el otro hilo espera al
    comienzo de la vuelta).
    """
    if len(set(row)) < 2:
        return 0
    n = len(row)
    start = next(i for i in range(n) if row[i] != row[i - 1])
    longest = run = 0
    for k in range(n):
        cell = row[(start + k) % n]
        prev = row[(start + k - 1) % n]
        run = run + 1 if k and cell == prev else 1
        longest = max(longest, run)
    return longest


def _break_floats(row: str) -> str:
    """Corta cada tramo de un color mas largo que MAX_FLOAT poniendo un punto
    del otro color en el medio (los "puntitos de relleno" del jacquard)."""
    cells = list(row)
    n = len(cells)
    for _ in range(n):
        current = "".join(cells)
        if max_float(current) <= MAX_FLOAT:
            break
        start = next(i for i in range(n) if cells[i] != cells[i - 1])
        k = 0
        while k < n:
            color = cells[(start + k) % n]
            length = 1
            while k + length < n and cells[(start + k + length) % n] == color:
                length += 1
            if length > MAX_FLOAT:
                middle = (start + k + length // 2) % n
                cells[middle] = FG if color == BG else BG
                break
            k += length
    return "".join(cells)


def _grid(height: int, width: int, on: Callable[[int, int], bool]) -> tuple[str, ...]:
    return tuple(
        _break_floats("".join(FG if on(r, c) else BG for c in range(width)))
        for r in range(height)
    )


# --- Motivos (cada uno: altura pedida -> filas, o None si no entra) --------


def _checks(h: int) -> tuple[str, ...] | None:
    # Damero de 2 pts: 1 o 2 vueltas.
    if h < 1:
        return None
    return ("#.", ".#")[: min(h, 2)]


def _dots(h: int) -> tuple[str, ...] | None:
    # Puntitos alternados en una repeticion de 4.
    if h < 2:
        return None
    return ("#...", "..#.")


def _crosses(h: int) -> tuple[str, ...] | None:
    # Crucecita de 3x3 en una repeticion de 4.
    if h < 3:
        return None
    return _grid(3, 4, lambda r, c: (r == 1 and c in (0, 2)) or (r != 1 and c == 1))


def _zigzag(h: int) -> tuple[str, ...] | None:
    # Onda triangular de 1 pt de grosor: alto 3 o 4, repeticion 2*(alto-1).
    height = min(h, 4)
    if height < 3:
        return None
    width = 2 * (height - 1)
    return _grid(height, width, lambda r, c: c in (r, (width - r) % width))


def _diamond(h: int) -> tuple[str, ...] | None:
    # Rombo de contorno con un punto en el centro: alto impar 5-7.
    height = min(h, 7)
    if height % 2 == 0:
        height -= 1
    if height < 5:
        return None
    m = (height - 1) // 2
    width = 2 * m + 2

    def on(r: int, c: int) -> bool:
        d = abs(r - m)
        return abs(c - m) == m - d or (r == m and c == m)

    return _grid(height, width, on)


def _tree(h: int) -> tuple[str, ...] | None:
    # Abeto: tronco central y ramas en chevron que se acortan hacia arriba.
    height = min(h, 7)
    if height < 5:
        return None
    cx = height - 2
    width = 2 * cx + 2

    def on(r: int, c: int) -> bool:
        return c == cx or (r >= 1 and abs(c - cx) == height - 1 - r)

    return _grid(height, width, on)


def _star(h: int) -> tuple[str, ...] | None:
    # Estrella de 8 puntas por simetria: diagonales y brazos rectos (con un
    # hueco junto al centro), alto impar 7 o 9.
    height = min(h, 9)
    if height % 2 == 0:
        height -= 1
    if height < 7:
        return None
    m = (height - 1) // 2
    width = 2 * m + 2

    def on(r: int, c: int) -> bool:
        a, b = abs(r - m), abs(c - m)
        if c == width - 1:
            return False
        return (a == b and a <= m - 1) or (min(a, b) == 0 and 2 <= max(a, b) <= m)

    return _grid(height, width, on)


MOTIFS: dict[str, Callable[[int], tuple[str, ...] | None]] = {
    "checks": _checks,
    "dots": _dots,
    "crosses": _crosses,
    "zigzag": _zigzag,
    "diamond": _diamond,
    "tree": _tree,
    "star": _star,
}

# Orden de preferencia por papel de la guarda: el primero que entra en la
# altura disponible. Las guardas de borde (al final del canesu, con el conteo
# final fijo, siempre multiplo de 4) solo usan repeticiones de 2 o 4 pts.
ROLE_MOTIFS: dict[str, tuple[str, ...]] = {
    "main": ("star", "diamond", "zigzag", "crosses", "dots", "checks"),
    "medium": ("tree", "zigzag", "crosses", "dots", "checks"),
    "peerie": ("crosses", "dots", "checks"),
    "border": ("checks",),
}
ROLE_MAX_HEIGHT: dict[str, int] = {"main": 9, "medium": 5, "peerie": 3, "border": 2}


def pick_motif(role: str, height: int) -> tuple[str, tuple[str, ...]] | None:
    """Motivo para una guarda de `role` con `height` vueltas disponibles."""
    budget = min(height, ROLE_MAX_HEIGHT[role])
    for key in ROLE_MOTIFS[role]:
        rows = MOTIFS[key](budget)
        if rows is not None and len(rows) <= budget:
            return key, rows
    return None


def palette(colors: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Paleta efectiva: la de la foto, completada con colores por defecto
    hasta tener al menos dos (fondo y contraste)."""
    result = [c for c in colors if c]
    for default in DEFAULT_PALETTE:
        if len(result) >= 2:
            break
        if default not in result:
            result.append(default)
    return tuple(result)


# Nombres de color aproximados (para la leyenda); los tonos son los habituales
# del circulo cromatico, no una norma.
_HUES = (
    (15, "red"), (40, "orange"), (65, "yellow"), (160, "green"),
    (200, "teal"), (255, "blue"), (290, "purple"), (352, "pink"), (360, "red"),
)


def color_name(hex_color: str, lang: str) -> str:
    """Nombre aproximado de un color #rrggbb ("azul oscuro", "crudo")."""
    value = hex_color.lstrip("#")
    try:
        r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return hex_color
    hue, light, _ = colorsys.rgb_to_hls(r, g, b)
    chroma = max(r, g, b) - min(r, g, b)
    if chroma < 0.12:
        if light > 0.8:
            key = "cream" if r > b + 0.03 else ("white" if light > 0.9 else "light_gray")
        elif light > 0.3:
            key = "gray"
        elif light > 0.1:
            key = "charcoal"
        else:
            key = "black"
        return t(f"colorname.{key}", lang)
    degrees = hue * 360
    key = next(name for limit, name in _HUES if degrees < limit)
    if key == "orange" and light < 0.4:
        key = "brown"
    name = t(f"colorname.{key}", lang)
    if light < 0.3:
        return t("colorname.dark", lang, name=name)
    if light > 0.75:
        return t("colorname.light", lang, name=name)
    return name


def color_letter(index: int) -> str:
    return chr(65 + index)


def chart_text_lines(chart: ColorworkChart, lang: str) -> list[str]:
    """Grafico en texto: una letra de color por punto, la vuelta 1 abajo y el
    numero de vuelta a la derecha (para el texto plano y lectores de pantalla)."""
    name = t(f"colorwork.motif.{chart.motif}", lang)
    lines = [t("chart.colorwork_title", lang, n=chart.number, name=name)]
    for row in range(chart.height, 0, -1):
        cells = " ".join(color_letter(chart.color_at(row, col)) for col in range(chart.width, 0, -1))
        lines.append(f"{cells}  {row}")
    lines.append(t("chart.colorwork_repeat", lang, w=chart.width))
    return lines
