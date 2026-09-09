"""Models for the app-backend ``GetOrdersV2`` (POMS) query.

POMS is Polestar's order-management system. Its per-order ``configuration``
block carries the human-readable spec strings that the VDMS ``content``
block used to expose (``"400V lithium-ion battery, 111 kWh capacity, 17
modules"``, ``"360 kW / 489 hp"``, ``"Long range Dual motor"`` ...), so it is
the most faithful replacement now that VDMS returns VIN-only records. Only
available to the account that placed the order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .vdms import VdmsBatterySpec, VdmsLabelValue


def _str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _label_values(raw: Any) -> list[VdmsLabelValue]:
    if not isinstance(raw, list):
        return []
    out: list[VdmsLabelValue] = []
    for item in raw:
        lv = VdmsLabelValue.from_dict(item)
        if lv and (lv.label or lv.value):
            out.append(lv)
    return out


@dataclass(frozen=True)
class PomsFeature:
    """A configured feature: ``display_type`` is ``engine``/``package``/``option``/``color``/``interior``/``rims``/``extra``."""

    title: str
    display_type: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> PomsFeature | None:
        if not isinstance(data, dict):
            return None
        title = _str(data.get("title"))
        if title is None:
            return None
        return cls(title=title, display_type=_str(data.get("displayType")))


@dataclass(frozen=True)
class PomsConfiguration:
    model_year: int | None = None
    pno34: str | None = None
    structure_week: str | None = None
    dimensions: list[VdmsLabelValue] = field(default_factory=list)
    specifications: list[VdmsLabelValue] = field(default_factory=list)
    features: list[PomsFeature] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> PomsConfiguration | None:
        if not isinstance(data, dict):
            return None
        raw_features = data.get("features")
        features = (
            [f for f in (PomsFeature.from_dict(x) for x in raw_features) if f]
            if isinstance(raw_features, list)
            else []
        )
        my = data.get("modelYear")
        try:
            model_year = int(my) if my not in (None, "") else None
        except (TypeError, ValueError):
            model_year = None
        return cls(
            model_year=model_year,
            pno34=_str(data.get("pno34")),
            structure_week=_str(data.get("structureWeek")),
            dimensions=_label_values(data.get("dimensions")),
            specifications=_label_values(data.get("specifications")),
            features=features,
        )

    def spec(self, label: str) -> str | None:
        """Value of the specification row whose label matches (case-insensitive)."""
        want = label.strip().lower()
        for lv in self.specifications:
            if (lv.label or "").strip().lower() == want:
                return _str(lv.value)
        return None

    def features_of(self, display_type: str) -> list[str]:
        return [f.title for f in self.features if (f.display_type or "").lower() == display_type.lower()]

    # -- VDMS-compatible conveniences --------------------------------------

    @property
    def battery(self) -> str | None:
        return self.spec("Battery")

    @property
    def battery_spec(self) -> VdmsBatterySpec | None:
        return VdmsBatterySpec.from_battery_str(self.battery)

    @property
    def power(self) -> str | None:
        """``"360 kW / 489 hp"``"""
        return self.spec("Power")

    @property
    def total_kw(self) -> str | None:
        """Kilowatt part of :attr:`power` (``"360 kW"``)."""
        p = self.power
        if not p:
            return None
        first = p.split("/")[0].strip()
        return first or None

    @property
    def total_hp(self) -> str | None:
        p = self.power
        if not p or "/" not in p:
            return None
        return p.split("/", 1)[1].strip() or None

    @property
    def torque(self) -> str | None:
        return self.spec("Torque")

    @property
    def electric_motors(self) -> str | None:
        return self.spec("Electric motors")

    @property
    def motor_name(self) -> str | None:
        """``"Long range Dual motor"``"""
        return next(iter(self.features_of("engine")), None)

    @property
    def packages(self) -> list[str]:
        return self.features_of("package")

    @property
    def options(self) -> list[str]:
        return self.features_of("option") + self.features_of("extra")


@dataclass(frozen=True)
class PomsCar:
    vin: str | None = None
    model: str | None = None
    model_year: int | None = None
    edition: str | None = None
    engine: str | None = None
    exterior: str | None = None
    interior: str | None = None
    wheels: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> PomsCar | None:
        if not isinstance(data, dict):
            return None
        my = data.get("modelYear")
        try:
            model_year = int(my) if my not in (None, "") else None
        except (TypeError, ValueError):
            model_year = None
        return cls(
            vin=_str(data.get("vin")),
            model=_str(data.get("model")),
            model_year=model_year,
            edition=_str(data.get("edition")),
            engine=_str(data.get("engine")),
            exterior=_str(data.get("exterior")),
            interior=_str(data.get("interior")),
            wheels=_str(data.get("wheels")),
        )


@dataclass(frozen=True)
class PomsOrder:
    order_id: str | None = None
    order_state: str | None = None
    country_code: str | None = None
    placed_at: str | None = None
    delivery_stage: str | None = None
    car: PomsCar | None = None
    configuration: PomsConfiguration | None = None

    @classmethod
    def from_dict(cls, data: Any) -> PomsOrder | None:
        if not isinstance(data, dict):
            return None
        order_v2 = data.get("orderV2")
        order_v2 = order_v2 if isinstance(order_v2, dict) else {}
        status = ((order_v2.get("orderStatus") or {}).get("status") or {}) if isinstance(order_v2.get("orderStatus"), dict) else {}
        return cls(
            order_id=_str(data.get("orderId")),
            order_state=_str(data.get("orderState")),
            country_code=_str(data.get("countryCode")),
            placed_at=_str(data.get("placedAt")),
            delivery_stage=_str(status.get("deliveryStage")) if isinstance(status, dict) else None,
            car=PomsCar.from_dict(data.get("car")),
            configuration=PomsConfiguration.from_dict(order_v2.get("configuration")),
        )

    @property
    def vin(self) -> str | None:
        return self.car.vin if self.car else None
