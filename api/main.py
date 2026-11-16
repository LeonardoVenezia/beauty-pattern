"""Aplicacion FastAPI: foto -> atributos -> patron verificado -> PDF/SVG."""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ai.config import AIConfig
from ai.critic import critique_pattern
from ai.errors import AIConfigError, AIError
from ai.extractor import DESCRIPTION_MAX, MAX_PHOTOS, Hints, extract_garment
from ai.guide import write_guide
from ai.probe import CapabilityProbe
from ai.writer import write_pattern_text
from api.ratelimit import limiter_from_env
from api.storage import database_from_env
from engine import ENGINE_VERSION
from engine.garments import GarmentError, generate
from engine.i18n import t
from engine.ir import Pattern
from engine.serialization import pattern_from_dict, pattern_to_dict
from engine.simulator import simulate
from engine.spec import Category, GarmentSpec, PatternParams
from engine.stitches.catalog import STITCH_PATTERNS
from engine.text import render_pattern_text
from render.pdf import GuideText, render_pattern_pdf
from render.schematic import render_schematic_svg
from vision.preprocess import ImageValidationError, PreparedImage, prepare_image


def _cors_origins() -> list[str]:
    raw = os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="Tejedora API", version=ENGINE_VERSION)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
limiter = limiter_from_env()


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    return response


class PatternRequest(BaseModel):
    spec: GarmentSpec
    params: PatternParams = Field(default_factory=PatternParams)


class RewriteRequest(BaseModel):
    lang: Literal["es", "en"] = "es"
    level: Literal["principiante", "experta"] | None = None


class CritiqueRequest(BaseModel):
    image_id: str
    lang: Literal["es", "en"] = "es"


def _max_upload_bytes() -> int:
    try:
        megabytes = float(os.environ.get("MAX_UPLOAD_MB", "12"))
    except ValueError:
        megabytes = 12.0
    return int(megabytes * 1024 * 1024)


def _image_ttl_hours() -> float:
    try:
        return float(os.environ.get("IMAGE_TTL_HOURS", "24"))
    except ValueError:
        return 24.0


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "engine_version": ENGINE_VERSION}


@app.get("/health/ai")
async def health_ai(refresh: bool = False) -> dict[str, object]:
    try:
        config = AIConfig.from_env()
    except AIConfigError as exc:
        return {
            "configured": False,
            "error": str(exc),
            "hint": "Defini AI_BASE_URL, AI_API_KEY y AI_MODEL, o usa FAKE_AI=1.",
        }
    probe = CapabilityProbe(config)
    try:
        capabilities = await probe.run(force=refresh)
    finally:
        await probe.aclose()
    return {"configured": True, **capabilities.model_dump()}


@app.post("/analyze")
async def analyze(
    request: Request,
    file: Annotated[UploadFile | None, File()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
    tejido: Annotated[Literal["knit", "crochet"] | None, Form()] = None,
    categoria: Annotated[Category | None, Form()] = None,
    descripcion: Annotated[str | None, Form(max_length=DESCRIPTION_MAX)] = None,
) -> dict[str, object]:
    """Una o varias fotos de la misma pieza (campo `files`, hasta 4; `file`
    sigue aceptado). Cada foto se valida y se le mide la calidad."""
    if not limiter.allow(_client_key(request)):
        raise HTTPException(status_code=429, detail="demasiadas solicitudes")
    uploads = [*([file] if file is not None else []), *(files or [])]
    if not uploads:
        raise HTTPException(status_code=422, detail="falta la foto")
    if len(uploads) > MAX_PHOTOS:
        raise HTTPException(status_code=422, detail=f"hasta {MAX_PHOTOS} fotos por analisis")
    datas: list[bytes] = []
    prepared_photos: list[PreparedImage] = []
    for index, upload in enumerate(uploads, start=1):
        data = await upload.read(_max_upload_bytes() + 1)
        if len(data) > _max_upload_bytes():
            raise HTTPException(status_code=413, detail=f"la foto {index} supera el maximo permitido")
        try:
            prepared_photos.append(prepare_image(data))
        except ImageValidationError as exc:
            raise HTTPException(status_code=422, detail=f"foto {index}: {exc}") from exc
        datas.append(data)
    data = datas[0]
    prepared = prepared_photos[0]
    try:
        config = AIConfig.from_env()
    except AIConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        result = await extract_garment(prepared_photos, config, hints=Hints(tejido, categoria, descripcion))
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    database = database_from_env()
    image_id = database.save_image(
        data, prepared.mime_type, ttl_hours=_image_ttl_hours()
    )
    return {
        "image_id": image_id,
        "spec": result.spec.model_dump(mode="json"),
        "confidence": result.confidence,
        "disagreements": {
            field: list(values) for field, values in result.disagreements.items()
        },
        "prompt_version": result.prompt_version,
        "photo_quality": [
            {"photo": index, "issues": list(photo.quality)}
            for index, photo in enumerate(prepared_photos, start=1)
        ],
        "cached": result.cached,
        "usage": asdict(result.usage),
    }


@app.post("/pattern")
async def create_pattern(
    request: Request, payload: PatternRequest
) -> dict[str, object]:
    if not limiter.allow(_client_key(request)):
        raise HTTPException(status_code=429, detail="demasiadas solicitudes")
    try:
        pattern = generate(payload.spec, payload.params)
    except GarmentError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": exc.key, "params": exc.params},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    report = simulate(pattern)
    if not report.ok:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "simulation_failed",
                "issues": [asdict(issue) for issue in report.issues],
            },
        )
    text_es = render_pattern_text(pattern, lang="es")
    text_en = render_pattern_text(pattern, lang="en")
    database = database_from_env()
    pattern_id = database.save_pattern(
        pattern_to_dict(pattern),
        text_es,
        text_en,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    return {
        "id": pattern_id,
        "pattern": pattern_to_dict(pattern),
        "text": {"es": text_es, "en": text_en},
        "simulation": {"ok": True, "issues": []},
    }


@app.get("/pattern/{pattern_id}")
async def get_pattern(pattern_id: str) -> dict[str, object]:
    record = database_from_env().get_pattern(pattern_id)
    if record is None:
        raise HTTPException(status_code=404, detail="patron no encontrado")
    return {
        "id": record.id,
        "pattern": record.pattern,
        "text": {"es": record.text_es, "en": record.text_en},
        "created_at": record.created_at,
    }


async def _guide(pattern: Pattern) -> GuideText | None:
    """Segunda pasada de IA: la voz humana del patron, sin numeros. Si no hay
    IA configurada o no cumple las reglas, el PDF sale igual sin guia."""
    try:
        notes = await write_guide(pattern, config=AIConfig.from_env())
    except AIConfigError:
        return None
    if notes is None:
        return None
    lang = pattern.params.idioma
    return GuideText(
        intro=notes.intro,
        sections={t(s.name_key, lang): notes.secciones[s.id] for s in pattern.sections if s.id in notes.secciones},
        closing=notes.cierre,
    )


@app.get("/pattern/{pattern_id}/pdf")
async def get_pattern_pdf(
    pattern_id: str,
    papel: Literal["A4", "Letter"] = "A4",
    imprimir: bool = False,
    foto: str | None = None,
    guia: bool = True,
) -> Response:
    database = database_from_env()
    record = database.get_pattern(pattern_id)
    if record is None:
        raise HTTPException(status_code=404, detail="patron no encontrado")
    pattern = pattern_from_dict(record.pattern)
    # ponytail: la foto vive lo que dura la imagen guardada (IMAGE_TTL_HOURS);
    # despues el PDF sale sin foto. Guardarla con el patron si hace falta mas.
    image = database.get_image(foto) if foto else None
    photo = prepare_image(image[0]).main if image else None  # sin EXIF y achicada
    pdf = render_pattern_pdf(
        pattern, paper=papel, print_mode=imprimir, photo=photo, guide=await _guide(pattern) if guia else None
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="patron-{pattern_id}.pdf"',
            "Cache-Control": "private, max-age=300",
        },
    )


@app.get("/pattern/{pattern_id}/svg")
async def get_pattern_svg(pattern_id: str) -> Response:
    record = database_from_env().get_pattern(pattern_id)
    if record is None:
        raise HTTPException(status_code=404, detail="patron no encontrado")
    pattern = pattern_from_dict(record.pattern)
    svg = render_schematic_svg(pattern)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, max-age=300"},
    )


@app.post("/pattern/{pattern_id}/rewrite")
async def rewrite_pattern(pattern_id: str, payload: RewriteRequest) -> dict[str, object]:
    record = database_from_env().get_pattern(pattern_id)
    if record is None:
        raise HTTPException(status_code=404, detail="patron no encontrado")
    try:
        config = AIConfig.from_env()
    except AIConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    pattern = pattern_from_dict(record.pattern)
    result = await write_pattern_text(
        pattern,
        language=payload.lang,
        level=payload.level,
        config=config,
    )
    return {
        "text": result.text,
        "fallback_used": result.fallback_used,
        "attempts": result.attempts,
        "validation_errors": list(result.validation_errors),
        "prompt_version": result.prompt_version,
        "usage": asdict(result.usage),
    }


@app.post("/pattern/{pattern_id}/critique")
async def critique_saved_pattern(
    pattern_id: str, payload: CritiqueRequest
) -> dict[str, object]:
    record = database_from_env().get_pattern(pattern_id)
    if record is None:
        raise HTTPException(status_code=404, detail="patron no encontrado")
    image = database_from_env().get_image(payload.image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="imagen no encontrada o vencida")
    try:
        config = AIConfig.from_env()
    except AIConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        prepared = prepare_image(image[0])
    except ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    pattern = pattern_from_dict(record.pattern)
    result = await critique_pattern(
        prepared,
        pattern.spec,
        pattern,
        language=payload.lang,
        config=config,
    )
    return {
        "observations": list(result.observations),
        "risks": list(result.risks),
        "fallback_used": result.fallback_used,
        "prompt_version": result.prompt_version,
        "usage": asdict(result.usage),
    }


@app.get("/stitches")
async def list_stitches() -> list[dict[str, object]]:
    return [
        {
            "id": stitch.id,
            "name_key": stitch.name_key,
            "technique": stitch.technique,
            "multiple": stitch.multiple,
            "rows": len(stitch.rows),
            "notes_key": stitch.notes_key,
        }
        for stitch in STITCH_PATTERNS.values()
    ]
