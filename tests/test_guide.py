"""La guia (voz humana) acompana al patron sin poder contradecir sus numeros."""

from __future__ import annotations

import asyncio
import json

from ai.config import AIConfig
from ai.fake import FakeAIClient
from ai.guide import Guide, guide_problems, write_guide
from engine.garments import generate
from engine.spec import Category, GarmentSpec, PatternParams, Technique
from render.pdf import GuideText, render_pattern_pdf

HAT = generate(GarmentSpec(categoria=Category.HAT, tecnica=Technique.NEEDLES), PatternParams())
FAKE = AIConfig.from_env({"FAKE_AI": "1"})


def test_numbers_in_any_form_are_rejected_but_dos_agujas_is_fine() -> None:
    ids = {"brim", "body", "crown"}
    ok = Guide(intro="Un gorro a dos agujas, tejido en redondo.", secciones={"brim": "Contar al terminar."})
    assert guide_problems(ok, ids) == []
    for bad in ("Son 72 puntos.", "Tejer doce vueltas.", "Llega a la mitad del alto."):
        assert guide_problems(Guide(intro=bad), ids)
    assert guide_problems(Guide(intro="Hola.", secciones={"sleeve": "x"}), ids)


def test_guide_is_repaired_or_dropped_never_wrong() -> None:
    good = {"intro": "Un gorro calentito.", "secciones": {"crown": "Al final se cierra pasando la hebra."}, "cierre": ""}
    client = FakeAIClient(responses=[json.dumps({"intro": "Montar 72 puntos."}), json.dumps(good)])
    guide = asyncio.run(write_guide(HAT, config=FAKE, client=client))
    assert guide is not None and guide.secciones["crown"].startswith("Al final")
    assert "72" in client.calls[1].messages[-1].parts[0].text  # se le dijo que numero sobraba
    always_bad = FakeAIClient(handler=lambda *_: json.dumps({"intro": "Son 3 vueltas."}))
    assert asyncio.run(write_guide(HAT, config=FAKE, client=always_bad)) is None


def test_pdf_carries_the_guide() -> None:
    guide = GuideText(intro="Un gorro pensado para regalar.", sections={"Corona": "La coronilla se cierra al final."})
    assert render_pattern_pdf(HAT, guide=guide).startswith(b"%PDF")
