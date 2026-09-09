"""Models for the Polestar car-configurator specification endpoints.

Source: ``GET https://pc-api.polestar.com/eu-north-1/car-configurator-back/
configurator/api/car-info/{modelYear}/{pno34}/{structureWeek}/car-spec/...``.
This is the (unauthenticated) REST service the official iOS/Android apps
use for the "Specifications" screen since VDMS stopped carrying spec data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


@dataclass(frozen=True)
class SpecNumeric:
    value: float | None = None
    formatted: str | None = None
    unit: str | None = None
    unit_key: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> SpecNumeric | None:
        if not isinstance(data, dict):
            return None
        return cls(
            value=_float(data.get("value")),
            formatted=_str(data.get("formatted")),
            unit=_str(data.get("unit")),
            unit_key=_str(data.get("unitKey")),
        )


@dataclass(frozen=True)
class SpecValue:
    """One value inside a specification row (e.g. ``power-in-kilowatt``)."""

    key: str
    numeric: SpecNumeric | None = None
    text_key: str | None = None
    text: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> SpecValue | None:
        if not isinstance(data, dict):
            return None
        key = _str(data.get("key"))
        if key is None:
            return None
        text = data.get("text")
        text = text if isinstance(text, dict) else {}
        return cls(
            key=key,
            numeric=SpecNumeric.from_dict(data.get("numeric")),
            text_key=_str(text.get("key")),
            text=_str(text.get("content")),
        )


@dataclass(frozen=True)
class SpecRow:
    """One display row, e.g. ``power`` → ``"360 kW / 489 hp"``."""

    key: str
    label: str | None = None
    value: str | None = None
    values: list[SpecValue] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> SpecRow | None:
        if not isinstance(data, dict):
            return None
        key = _str(data.get("key"))
        if key is None:
            return None
        raw_values = data.get("specificationValues")
        values = (
            [v for v in (SpecValue.from_dict(x) for x in raw_values) if v]
            if isinstance(raw_values, list)
            else []
        )
        return cls(key=key, label=_str(data.get("label")), value=_str(data.get("value")), values=values)


@dataclass(frozen=True)
class CarSpecifications:
    """Parsed ``car-spec/specifications`` response."""

    request_id: str | None = None
    rows: list[SpecRow] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> CarSpecifications:
        if not isinstance(data, dict):
            data = {}
        raw_rows = data.get("specifications")
        rows = (
            [r for r in (SpecRow.from_dict(x) for x in raw_rows) if r]
            if isinstance(raw_rows, list)
            else []
        )
        return cls(request_id=_str(data.get("requestId")), rows=rows)

    # -- lookup helpers -------------------------------------------------

    def row(self, key: str) -> SpecRow | None:
        return next((r for r in self.rows if r.key == key), None)

    def text(self, key: str) -> str | None:
        """Formatted display string for a row (``"360 kW / 489 hp"``)."""
        r = self.row(key)
        return r.value if r else None

    def number(self, value_key: str) -> float | None:
        """Numeric value by inner value key (``"power-in-kilowatt"`` → 360.0)."""
        for r in self.rows:
            for v in r.values:
                if v.key == value_key and v.numeric is not None:
                    return v.numeric.value
        return None

    def text_key(self, value_key: str) -> str | None:
        """Machine key of a textual value (``"driveline"`` → ``"all-wheel-drive"``)."""
        for r in self.rows:
            for v in r.values:
                if v.key == value_key and v.text_key is not None:
                    return v.text_key
        return None

    # -- common conveniences --------------------------------------------

    @property
    def power_kw(self) -> float | None:
        return self.number("power-in-kilowatt")

    @property
    def power_hp(self) -> float | None:
        return self.number("power-in-horsepower")

    @property
    def torque_nm(self) -> float | None:
        return self.number("torque-in-newton-meter")

    @property
    def battery_capacity_kwh(self) -> float | None:
        return self.number("battery-capacity-in-kilowatt-hour")

    @property
    def battery_voltage(self) -> float | None:
        return self.number("battery-potential-in-volt")

    @property
    def battery_module_count(self) -> float | None:
        return self.number("battery-module-count")

    @property
    def range_km(self) -> float | None:
        return self.number("range-wltp-min-in-kilometer")

    @property
    def curb_weight_min_kg(self) -> float | None:
        return self.number("curb-weight-min-in-kilogram")

    @property
    def curb_weight_max_kg(self) -> float | None:
        return self.number("curb-weight-max-in-kilogram")

    @property
    def towing_capacity_kg(self) -> float | None:
        return self.number("towing-capacity-in-kilogram")

    @property
    def driveline(self) -> str | None:
        """Display text, e.g. ``"All-wheel drive"``."""
        return self.text("driveline")

    @property
    def driveline_key(self) -> str | None:
        return self.text_key("driveline")


@dataclass(frozen=True)
class CarFeature:
    """An option/package fitted to the car (from ``car-spec/en-fallback``)."""

    title: str
    code: str | None = None
    type: str | None = None
    description: str | None = None
    category_id: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> CarFeature | None:
        if not isinstance(data, dict):
            return None
        title = _str(data.get("title"))
        if title is None:
            return None
        pno = data.get("pnoId")
        pno = pno if isinstance(pno, dict) else {}
        return cls(
            title=title,
            code=_str(pno.get("code")),
            type=_str(pno.get("type")),
            description=_str(data.get("description")),
            category_id=_str(data.get("featureCategoryId")),
        )


@dataclass(frozen=True)
class CarFeatureCategory:
    id: str
    title: str | None = None
    key: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> CarFeatureCategory | None:
        if not isinstance(data, dict):
            return None
        cid = _str(data.get("id"))
        if cid is None:
            return None
        return cls(id=cid, title=_str(data.get("title")), key=_str(data.get("key")))


@dataclass(frozen=True)
class CarFeatures:
    """Parsed ``car-spec/en-fallback`` response (model name + fitted features)."""

    name: str | None = None
    features: list[CarFeature] = field(default_factory=list)
    categories: list[CarFeatureCategory] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> CarFeatures:
        if not isinstance(data, dict):
            data = {}
        raw_f = data.get("carFeatures")
        raw_c = data.get("carFeatureCategories")
        return cls(
            name=_str(data.get("name")),
            features=[f for f in (CarFeature.from_dict(x) for x in raw_f) if f] if isinstance(raw_f, list) else [],
            categories=[c for c in (CarFeatureCategory.from_dict(x) for x in raw_c) if c]
            if isinstance(raw_c, list)
            else [],
        )

    @property
    def titles(self) -> list[str]:
        return [f.title for f in self.features]

    def of_type(self, feature_type: str) -> list[CarFeature]:
        return [f for f in self.features if (f.type or "").lower() == feature_type.lower()]

    @property
    def motor(self) -> CarFeature | None:
        """The ``Engine`` feature, e.g. ``"Long range Dual motor"``."""
        return next(iter(self.of_type("Engine")), None)

    @property
    def packages(self) -> list[str]:
        """Titles of fitted option packages (``Options`` type), e.g. ``["Pilot", "Plus"]``."""
        return [f.title for f in self.of_type("Options")]
