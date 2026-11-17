"""Graficos de puntos en SVG, generados desde el catalogo declarativo."""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

from engine.i18n import t
from engine.stitches.catalog import StitchPattern
from engine.stitches.chart import ChartSymbol

CELL = 22
MARGIN_LEFT = 48
MARGIN_TOP = 46
MARGIN_RIGHT = 18
MARGIN_BOTTOM = 18
STROKE = "#222222"
GRID = "#b9b9b9"


def _f(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _symbol_svg(symbol: ChartSymbol, x: float, y: float, size: float) -> str:
    cx = x + size / 2
    cy = y + size / 2
    pad = max(3.0, size * 0.18)
    parts: list[str] = []
    line = (
        f'stroke="{STROKE}" stroke-width="{_f(max(1.0, size / 14))}" '
        'stroke-linecap="round" fill="none"'
    )
    if symbol is ChartSymbol.KNIT:
        return ""
    if symbol is ChartSymbol.PURL:
        parts.append(
            f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(size * 0.1)}" fill="{STROKE}"/>'
        )
    elif symbol is ChartSymbol.K2TOG:
        parts.append(
            f'<line x1="{_f(x + pad)}" y1="{_f(y + pad)}" '
            f'x2="{_f(x + size - pad)}" y2="{_f(y + size - pad)}" {line}/>'
        )
    elif symbol is ChartSymbol.SSK:
        parts.append(
            f'<line x1="{_f(x + size - pad)}" y1="{_f(y + pad)}" '
            f'x2="{_f(x + pad)}" y2="{_f(y + size - pad)}" {line}/>'
        )
    elif symbol is ChartSymbol.YO:
        parts.append(
            f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(size * 0.2)}" '
            f'stroke="{STROKE}" stroke-width="1.3" fill="none"/>'
        )
    elif symbol in {ChartSymbol.CABLE_FRONT, ChartSymbol.CABLE_BACK}:
        span_width = size
        parts.append(
            f'<line x1="{_f(x + pad)}" y1="{_f(y + pad)}" '
            f'x2="{_f(x + span_width - pad)}" y2="{_f(y + size - pad)}" {line}/>'
        )
        parts.append(
            f'<line x1="{_f(x + span_width - pad)}" y1="{_f(y + pad)}" '
            f'x2="{_f(x + pad)}" y2="{_f(y + size - pad)}" {line}/>'
        )
        arrow_y = y + 3
        if symbol is ChartSymbol.CABLE_FRONT:
            points = f"{_f(cx - 7)},{_f(arrow_y)} {_f(cx - 2)},{_f(arrow_y)} {_f(cx - 4.5)},{_f(arrow_y + 5)}"
        else:
            points = f"{_f(cx + 7)},{_f(arrow_y)} {_f(cx + 2)},{_f(arrow_y)} {_f(cx + 4.5)},{_f(arrow_y + 5)}"
        parts.append(f'<polygon points="{points}" fill="#0a7a4a"/>')
    elif symbol is ChartSymbol.BOBBLE:
        parts.append(
            f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(size * 0.28)}" '
            f'fill="#444444" stroke="{STROKE}" stroke-width="1"/>'
        )
    elif symbol is ChartSymbol.SLIP:
        parts.append(
            f'<line x1="{_f(x + pad)}" y1="{_f(cy)}" '
            f'x2="{_f(x + size - pad)}" y2="{_f(cy)}" {line}/>'
        )
    elif symbol in {ChartSymbol.INCREASE_LEFT, ChartSymbol.INCREASE_RIGHT}:
        label = "M1L" if symbol is ChartSymbol.INCREASE_LEFT else "M1R"
        parts.append(
            f'<text x="{_f(cx)}" y="{_f(cy + 2.5)}" text-anchor="middle" '
            f'font-family="system-ui, sans-serif" font-size="{_f(size * 0.33)}" '
            f'fill="{STROKE}">{label}</text>'
        )
    elif symbol is ChartSymbol.KFB:
        parts.append(
            f'<text x="{_f(cx)}" y="{_f(cy + 2.5)}" text-anchor="middle" '
            f'font-family="system-ui, sans-serif" font-size="{_f(size * 0.33)}" '
            f'fill="{STROKE}">kfb</text>'
        )
    elif symbol is ChartSymbol.SC:
        parts.append(
            f'<line x1="{_f(x + pad)}" y1="{_f(y + pad)}" '
            f'x2="{_f(x + size - pad)}" y2="{_f(y + size - pad)}" {line}/>'
        )
        parts.append(
            f'<line x1="{_f(x + size - pad)}" y1="{_f(y + pad)}" '
            f'x2="{_f(x + pad)}" y2="{_f(y + size - pad)}" {line}/>'
        )
    elif symbol in {ChartSymbol.HDC, ChartSymbol.DC}:
        parts.append(
            f'<line x1="{_f(x + pad)}" y1="{_f(y + size * 0.35)}" '
            f'x2="{_f(x + size - pad)}" y2="{_f(y + size * 0.35)}" {line}/>'
        )
        parts.append(
            f'<line x1="{_f(cx)}" y1="{_f(y + size * 0.35)}" '
            f'x2="{_f(cx)}" y2="{_f(y + size - pad)}" {line}/>'
        )
        if symbol is ChartSymbol.DC:
            parts.append(
                f'<line x1="{_f(x + pad)}" y1="{_f(y + size * 0.55)}" '
                f'x2="{_f(x + size - pad)}" y2="{_f(y + size * 0.55)}" {line}/>'
            )
    elif symbol is ChartSymbol.CH:
        parts.append(
            f'<ellipse cx="{_f(cx)}" cy="{_f(cy)}" rx="{_f(size * 0.24)}" '
            f'ry="{_f(size * 0.16)}" stroke="{STROKE}" stroke-width="1.3" fill="none"/>'
        )
    elif symbol is ChartSymbol.MAGIC_RING:
        parts.append(
            f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(size * 0.3)}" '
            f'stroke="{STROKE}" stroke-width="1.2" fill="none"/>'
        )
        parts.append(
            f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(size * 0.12)}" '
            f'stroke="{STROKE}" stroke-width="1.2" fill="none"/>'
        )
    elif symbol in {ChartSymbol.BRIOCHE_KNIT, ChartSymbol.BRIOCHE_PURL}:
        label = "brk" if symbol is ChartSymbol.BRIOCHE_KNIT else "brp"
        parts.append(
            f'<text x="{_f(cx)}" y="{_f(cy + 2.5)}" text-anchor="middle" '
            f'font-family="system-ui, sans-serif" font-size="{_f(size * 0.3)}" '
            f'fill="{STROKE}">{label}</text>'
        )
    elif symbol is ChartSymbol.CROCHET_INC:
        parts.append(
            f'<line x1="{_f(cx - size * 0.2)}" y1="{_f(cy)}" '
            f'x2="{_f(cx + size * 0.2)}" y2="{_f(cy)}" {line}/>'
        )
        parts.append(
            f'<line x1="{_f(cx)}" y1="{_f(cy - size * 0.2)}" '
            f'x2="{_f(cx)}" y2="{_f(cy + size * 0.2)}" {line}/>'
        )
    elif symbol is ChartSymbol.CROCHET_DEC:
        parts.append(
            f'<line x1="{_f(cx - size * 0.2)}" y1="{_f(cy)}" '
            f'x2="{_f(cx + size * 0.2)}" y2="{_f(cy)}" {line}/>'
        )
    else:
        parts.append(_new_symbol_svg(symbol, x, y, size, line))
    return "".join(parts)


def _new_symbol_svg(symbol: ChartSymbol, x: float, y: float, size: float, line: str) -> str:
    """Simbolos de la ampliacion de puntos (convenciones CYC: retorcido = lazo
    cruzado, pb por la hebra de atras = + con un arco abajo, abanico y V = pa
    que salen de un mismo punto)."""
    cx, cy = x + size / 2, y + size / 2
    pad = max(3.0, size * 0.18)
    top, bottom = y + pad, y + size - pad

    def ln(x1: float, y1: float, x2: float, y2: float) -> str:
        return f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}" {line}/>'

    def dc(x_top: float) -> str:  # pa inclinado desde la base central
        tick_y = top + (bottom - top) * 0.45
        tick_x = cx + (x_top - cx) * 0.55
        return ln(cx, bottom, x_top, top) + ln(tick_x - size * 0.08, tick_y, tick_x + size * 0.08, tick_y)

    if symbol in {ChartSymbol.TWISTED_KNIT, ChartSymbol.TWISTED_PURL}:
        loop = (
            f'<path d="M {_f(cx - size * 0.18)} {_f(bottom)} C {_f(cx + size * 0.3)} {_f(cy)}, '
            f'{_f(cx + size * 0.3)} {_f(top)}, {_f(cx)} {_f(top)} C {_f(cx - size * 0.3)} {_f(top)}, '
            f'{_f(cx - size * 0.3)} {_f(cy)}, {_f(cx + size * 0.18)} {_f(bottom)}" {line}/>'
        )
        if symbol is ChartSymbol.TWISTED_PURL:
            loop += f'<line x1="{_f(x + pad)}" y1="{_f(y + pad * 0.6)}" x2="{_f(x + size - pad)}" y2="{_f(y + pad * 0.6)}" {line}/>'
        return loop
    if symbol is ChartSymbol.SLIP_WYIF:
        return ln(x + pad, cy, x + size - pad, cy) + ln(cx, cy, cx, bottom)
    if symbol is ChartSymbol.SC_BLO:
        arc = (
            f'<path d="M {_f(x + pad)} {_f(bottom)} Q {_f(cx)} {_f(bottom - size * 0.25)} '
            f'{_f(x + size - pad)} {_f(bottom)}" {line}/>'
        )
        return ln(cx, top, cx, cy + size * 0.12) + ln(x + pad, cy - size * 0.05, x + size - pad, cy - size * 0.05) + arc
    if symbol is ChartSymbol.TR:
        return (
            ln(cx, top, cx, bottom)
            + ln(x + pad, top, x + size - pad, top)
            + ln(cx - size * 0.15, cy - size * 0.08, cx + size * 0.15, cy - size * 0.02)
            + ln(cx - size * 0.15, cy + size * 0.06, cx + size * 0.15, cy + size * 0.12)
        )
    if symbol is ChartSymbol.V_STITCH:
        dot = f'<circle cx="{_f(cx)}" cy="{_f(top + 1)}" r="{_f(size * 0.06)}" fill="none" stroke="#222222"/>'
        return dc(x + pad) + dc(x + size - pad) + dot
    if symbol is ChartSymbol.SHELL:
        return "".join(dc(x + pad + (size - 2 * pad) * k / 4) for k in range(5))
    if symbol is ChartSymbol.GRANNY_GROUP:
        return "".join(dc(x + pad + (size - 2 * pad) * k / 2) for k in range(3))
    if symbol is ChartSymbol.TSS:
        return ln(cx, top, cx, bottom) + ln(cx - size * 0.12, top, cx + size * 0.12, top)
    if symbol is ChartSymbol.C2C_BLOCK:
        block = (
            f'<rect x="{_f(x + pad)}" y="{_f(top)}" width="{_f(size - 2 * pad)}" '
            f'height="{_f(bottom - top)}" fill="none" stroke="#222222" stroke-width="1"/>'
        )
        return block + ln(x + pad, bottom, x + size - pad, top)
    return ""


def _cable_svg(symbol: ChartSymbol, x: float, y: float, width: float, height: float) -> str:
    pad = max(3.0, height * 0.18)
    line = (
        f'stroke="{STROKE}" stroke-width="1.4" stroke-linecap="round" fill="none"'
    )
    cx = x + width / 2
    parts = [
        f'<line x1="{_f(x + pad)}" y1="{_f(y + pad)}" '
        f'x2="{_f(x + width - pad)}" y2="{_f(y + height - pad)}" {line}/>',
        f'<line x1="{_f(x + width - pad)}" y1="{_f(y + pad)}" '
        f'x2="{_f(x + pad)}" y2="{_f(y + height - pad)}" {line}/>',
    ]
    arrow_y = y + 3
    if symbol is ChartSymbol.CABLE_FRONT:
        points = (
            f"{_f(cx - 7)},{_f(arrow_y)} {_f(cx - 2)},{_f(arrow_y)} "
            f"{_f(cx - 4.5)},{_f(arrow_y + 5)}"
        )
    else:
        points = (
            f"{_f(cx + 7)},{_f(arrow_y)} {_f(cx + 2)},{_f(arrow_y)} "
            f"{_f(cx + 4.5)},{_f(arrow_y + 5)}"
        )
    parts.append(f'<polygon points="{points}" fill="#0a7a4a"/>')
    return "".join(parts)


def _legend_symbols(pattern: StitchPattern, *, in_the_round: bool) -> list[ChartSymbol]:
    seen: list[ChartSymbol] = []
    for row in range(1, pattern.row_count(in_the_round=in_the_round) + 1):
        for cell in pattern.chart_cells(row, in_the_round=in_the_round):
            if cell.symbol not in seen:
                seen.append(cell.symbol)
    return seen


def render_stitch_chart_svg(
    pattern: StitchPattern,
    *,
    repeats: int = 2,
    lang: str = "es",
    in_the_round: bool = False,
) -> str:
    """Renderiza un grafico de punto autocontenido en SVG."""
    if repeats < 1:
        raise ValueError("repeats debe ser >= 1")
    rows = pattern.row_count(in_the_round=in_the_round)
    chart_width = pattern.multiple * repeats * CELL
    legend_symbols = _legend_symbols(pattern, in_the_round=in_the_round)
    legend_columns = 2 if chart_width >= 300 else 1
    legend_rows = math.ceil(len(legend_symbols) / legend_columns)
    legend_height = 26 + legend_rows * 22
    width = MARGIN_LEFT + chart_width + MARGIN_RIGHT
    height = MARGIN_TOP + rows * CELL + legend_height + MARGIN_BOTTOM + 24

    title = t(pattern.name_key, lang)
    caption = t("chart.repeat", lang, n=repeats)
    row_note = t("chart.row_numbers", lang)
    legend_title = t("chart.legend", lang)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(width)}" '
        f'height="{_f(height)}" viewBox="0 0 {_f(width)} {_f(height)}" '
        f'role="img" aria-label="{escape(title)}">',
        f"<title>{escape(title)}</title>",
        f"<desc>{escape(caption + '. ' + row_note)}</desc>",
        f'<rect x="0" y="0" width="{_f(width)}" height="{_f(height)}" fill="#ffffff"/>',
        f'<text x="{MARGIN_LEFT}" y="26" font-family="system-ui, sans-serif" '
        f'font-size="15" font-weight="700" fill="#111111">{escape(title)}</text>',
        f'<text x="{MARGIN_LEFT}" y="41" font-family="system-ui, sans-serif" '
        f'font-size="10" fill="#555555">{escape(caption)}</text>',
    ]

    for row_index in range(rows):
        y = MARGIN_TOP + (rows - 1 - row_index) * CELL
        row_number = row_index + 1
        parts.append(
            f'<text x="{MARGIN_LEFT - 10}" y="{_f(y + CELL / 2 + 3.5)}" '
            f'text-anchor="end" font-family="system-ui, sans-serif" '
            f'font-size="10" fill="#555555">{row_number}</text>'
        )
        cells = pattern.chart_cells(row_number, in_the_round=in_the_round)
        for repeat_index in range(repeats):
            x = MARGIN_LEFT + repeat_index * pattern.multiple * CELL
            for cell in cells:
                cell_width = cell.span * CELL
                parts.append(
                    f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(cell_width)}" '
                    f'height="{CELL}" fill="#ffffff" stroke="{GRID}" '
                    'stroke-width="0.7"/>'
                )
                if cell.symbol in {ChartSymbol.CABLE_FRONT, ChartSymbol.CABLE_BACK}:
                    parts.append(_cable_svg(cell.symbol, x, y, cell_width, CELL))
                else:
                    icon_x = x + (cell_width - CELL) / 2
                    symbol_svg = _symbol_svg(cell.symbol, icon_x, y, CELL)
                    if symbol_svg:
                        parts.append(symbol_svg)
                x += cell_width

    # Recuadro de la repeticion (estandar: la repeticion se marca en color) y
    # numeracion de puntos abajo, de derecha a izquierda.
    box_w = pattern.multiple * CELL
    parts.append(
        f'<rect x="{_f(MARGIN_LEFT)}" y="{_f(MARGIN_TOP)}" width="{_f(box_w)}" '
        f'height="{_f(rows * CELL)}" fill="none" stroke="#c0392b" stroke-width="2"/>'
    )
    total_cols = pattern.multiple * repeats
    for col in range(total_cols):
        number = total_cols - col
        parts.append(
            f'<text x="{_f(MARGIN_LEFT + col * CELL + CELL / 2)}" '
            f'y="{_f(MARGIN_TOP + rows * CELL + 12)}" text-anchor="middle" '
            f'font-family="system-ui, sans-serif" font-size="8.5" fill="#555555">{number}</text>'
        )

    legend_y = MARGIN_TOP + rows * CELL + 46
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="{_f(legend_y - 10)}" '
        f'font-family="system-ui, sans-serif" font-size="12" '
        f'font-weight="700" fill="#111111">{escape(legend_title)}</text>'
    )
    column_width = chart_width / legend_columns
    for index, symbol in enumerate(legend_symbols):
        column = index % legend_columns
        line = index // legend_columns
        x = MARGIN_LEFT + column * column_width
        y = legend_y + line * 22
        parts.append(
            f'<rect x="{_f(x)}" y="{_f(y)}" width="16" height="16" '
            f'fill="#ffffff" stroke="{GRID}" stroke-width="0.7"/>'
        )
        parts.append(_symbol_svg(symbol, x, y, 16))
        label = t(f"chart.{symbol.value}", lang)
        parts.append(
            f'<text x="{_f(x + 22)}" y="{_f(y + 12)}" '
            f'font-family="system-ui, sans-serif" font-size="10.5" '
            f'fill="#333333">{escape(label)}</text>'
        )

    note_y = legend_y + legend_rows * 22 + 16
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="{_f(note_y)}" '
        f'font-family="system-ui, sans-serif" font-size="9.5" '
        f'fill="#666666">{escape(row_note)}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)
