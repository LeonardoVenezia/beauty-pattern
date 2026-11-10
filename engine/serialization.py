"""Serializacion JSON de la IR para la API, la web y el almacenamiento."""

from __future__ import annotations

import json
from typing import Any

from engine.ir import (
    CountRef,
    Item,
    JoinCheck,
    Materials,
    Measurement,
    Op,
    Pattern,
    PatternMeta,
    Repeat,
    Section,
    SectionTarget,
    Step,
    Warning,
)
from engine.spec import GarmentSpec, PatternParams, YarnWeight
from engine.stitches.kinds import StitchKind


def _op_to_dict(op: Op) -> dict[str, Any]:
    return {"kind": op.kind.value, "times": op.times, "width": op.width}


def _item_to_dict(item: Item) -> dict[str, Any]:
    if isinstance(item, Op):
        return {"type": "op", **_op_to_dict(item)}
    return {
        "type": "repeat",
        "times": item.times,
        "ops": [_op_to_dict(op) for op in item.ops],
    }


def _step_to_dict(step: Step) -> dict[str, Any]:
    return {
        "number": step.number,
        "items": [_item_to_dict(item) for item in step.items],
        "stitch_count_end": step.stitch_count_end,
        "note_key": step.note_key,
    }


def _section_to_dict(section: Section) -> dict[str, Any]:
    target = None
    if section.target is not None:
        target = {
            "measurement_key": section.target.measurement_key,
            "target_cm": section.target.target_cm,
            "tolerance_cm": section.target.tolerance_cm,
            "dimension": section.target.dimension,
        }
    return {
        "id": section.id,
        "name_key": section.name_key,
        "mode": section.mode,
        "steps": [_step_to_dict(step) for step in section.steps],
        "start_stitches": section.start_stitches,
        "end_stitches": section.end_stitches,
        "target": target,
        "meta": dict(section.meta),
        "bind_off": section.bind_off,
        "note_keys": list(section.note_keys),
    }


def pattern_to_dict(pattern: Pattern) -> dict[str, Any]:
    return {
        "meta": {
            "id": pattern.meta.id,
            "family": pattern.meta.family,
            "title_key": pattern.meta.title_key,
            "size": pattern.meta.size,
            "created_at": pattern.meta.created_at,
            "engine_version": pattern.meta.engine_version,
        },
        "spec": pattern.spec.model_dump(mode="json"),
        "params": pattern.params.model_dump(mode="json"),
        "sections": [_section_to_dict(section) for section in pattern.sections],
        "measurements": [
            {
                "key": item.key,
                "value_cm": item.value_cm,
                "target_cm": item.target_cm,
                "tolerance_cm": item.tolerance_cm,
                "kind": item.kind,
            }
            for item in pattern.measurements
        ],
        "materials": {
            "yarn_weight": pattern.materials.yarn_weight.value,
            "needle_mm": pattern.materials.needle_mm,
            "hook_mm": pattern.materials.hook_mm,
            "meters": pattern.materials.meters,
            "grams": pattern.materials.grams,
            "notions": list(pattern.materials.notions),
            "colors": list(pattern.materials.colors),
        },
        "warnings": [
            {
                "code": warning.code,
                "message_key": warning.message_key,
                "params": dict(warning.params),
                "severity": warning.severity,
            }
            for warning in pattern.warnings
        ],
        "joins": [
            {
                "label_key": join.label_key,
                "left": [
                    {"section": ref.section, "field": ref.field}
                    for ref in join.left
                ],
                "right": [
                    {"section": ref.section, "field": ref.field}
                    for ref in join.right
                ],
            }
            for join in pattern.joins
        ],
        "notes": list(pattern.notes),
    }


def _op_from_dict(data: dict[str, Any]) -> Op:
    return Op(
        kind=StitchKind(data["kind"]),
        times=int(data.get("times", 1)),
        width=data.get("width"),
    )


def _item_from_dict(data: dict[str, Any]) -> Item:
    if data["type"] == "op":
        return _op_from_dict(data)
    return Repeat(
        times=int(data["times"]),
        ops=tuple(_op_from_dict(op) for op in data["ops"]),
    )


def _step_from_dict(data: dict[str, Any]) -> Step:
    return Step(
        number=int(data["number"]),
        items=tuple(_item_from_dict(item) for item in data["items"]),
        stitch_count_end=int(data["stitch_count_end"]),
        note_key=data.get("note_key"),
    )


def _section_from_dict(data: dict[str, Any]) -> Section:
    target_data = data.get("target")
    target = None
    if target_data is not None:
        target = SectionTarget(
            measurement_key=target_data["measurement_key"],
            target_cm=float(target_data["target_cm"]),
            tolerance_cm=float(target_data.get("tolerance_cm", 1.0)),
            dimension=target_data.get("dimension", "circumference"),
        )
    return Section(
        id=data["id"],
        name_key=data["name_key"],
        mode=data["mode"],
        steps=tuple(_step_from_dict(step) for step in data["steps"]),
        start_stitches=int(data["start_stitches"]),
        end_stitches=int(data["end_stitches"]),
        target=target,
        meta={key: int(value) for key, value in data.get("meta", {}).items()},
        bind_off=bool(data.get("bind_off", False)),
        note_keys=tuple(data.get("note_keys", ())),
    )


def pattern_from_dict(data: dict[str, Any]) -> Pattern:
    materials = data["materials"]
    return Pattern(
        meta=PatternMeta(**data["meta"]),
        spec=GarmentSpec.model_validate(data["spec"]),
        params=PatternParams.model_validate(data["params"]),
        sections=tuple(_section_from_dict(section) for section in data["sections"]),
        measurements=tuple(
            Measurement(
                key=item["key"],
                value_cm=float(item["value_cm"]),
                target_cm=item.get("target_cm"),
                tolerance_cm=float(item.get("tolerance_cm", 0.0)),
                kind=item.get("kind", "circumference"),
            )
            for item in data["measurements"]
        ),
        materials=Materials(
            yarn_weight=YarnWeight(materials["yarn_weight"]),
            needle_mm=materials.get("needle_mm"),
            hook_mm=materials.get("hook_mm"),
            meters=float(materials["meters"]),
            grams=materials.get("grams"),
            notions=tuple(materials.get("notions", ())),
            colors=tuple(materials.get("colors", ())),
        ),
        warnings=tuple(
            Warning(
                code=warning["code"],
                message_key=warning["message_key"],
                params=dict(warning.get("params", {})),
                severity=warning.get("severity", "warning"),
            )
            for warning in data.get("warnings", ())
        ),
        joins=tuple(
            JoinCheck(
                label_key=join["label_key"],
                left=tuple(
                    CountRef(section=ref["section"], field=ref["field"])
                    for ref in join["left"]
                ),
                right=tuple(
                    CountRef(section=ref["section"], field=ref["field"])
                    for ref in join["right"]
                ),
            )
            for join in data.get("joins", ())
        ),
        notes=tuple(data.get("notes", ())),
    )


def pattern_to_json(pattern: Pattern) -> str:
    return json.dumps(pattern_to_dict(pattern), ensure_ascii=False)


def pattern_from_json(payload: str) -> Pattern:
    return pattern_from_dict(json.loads(payload))
