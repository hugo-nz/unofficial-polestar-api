"""VDMS (Vehicle Data Management System) models.

Unlike the protobuf/gRPC models in this package, VDMS data comes from the
app-backend GraphQL endpoint as JSON, so these are plain frozen dataclasses
parsed via ``from_dict``. Every field tolerates null/missing values, which vary
by model, market, order state, and firmware.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, (int, float)) else None


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _model_year(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class VdmsLabelValue:
    """A labelled string value, e.g. ``{label: "Wheelbase", value: "2.985 mm"}``."""

    label: str | None = None
    value: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> VdmsLabelValue | None:
        if not isinstance(data, dict):
            return None
        return cls(label=_str(data.get("label")), value=_str(data.get("value")))


@dataclass(frozen=True)
class VdmsValueUnit:
    """A numeric value with a unit, e.g. ``{value: 2579, unit: "kg"}``."""

    value: int | float | None = None
    unit: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> VdmsValueUnit | None:
        if not isinstance(data, dict):
            return None
        return cls(value=_number(data.get("value")), unit=_str(data.get("unit")))


@dataclass(frozen=True)
class VdmsFeature:
    """A named feature, e.g. motor/trim/wheels/package ``{name: "..."}``."""

    name: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> VdmsFeature | None:
        if not isinstance(data, dict):
            return None
        return cls(name=_str(data.get("name")))


@dataclass(frozen=True)
class CarVisualisation:
    """A single car image (alt text, angle, url)."""

    alt: str | None = None
    angle: int | None = None
    url: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> CarVisualisation | None:
        if not isinstance(data, dict):
            return None
        angle = data.get("angle")
        return cls(
            alt=_str(data.get("alt")),
            angle=angle if isinstance(angle, int) and not isinstance(angle, bool) else None,
            url=_str(data.get("url")),
        )


def _visualisations(value: Any) -> list[CarVisualisation]:
    if not isinstance(value, list):
        return []
    result: list[CarVisualisation] = []
    for item in value:
        vis = CarVisualisation.from_dict(item)
        if vis is not None:
            result.append(vis)
    return result


@dataclass(frozen=True)
class VdmsImages:
    """Image sets returned for a vehicle."""

    interior: list[CarVisualisation] = field(default_factory=list)
    exterior: list[CarVisualisation] = field(default_factory=list)
    exterior_transparent: list[CarVisualisation] = field(default_factory=list)
    rims: list[CarVisualisation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> VdmsImages | None:
        if not isinstance(data, dict):
            return None
        return cls(
            interior=_visualisations(data.get("interior")),
            exterior=_visualisations(data.get("exterior")),
            exterior_transparent=_visualisations(data.get("exteriorTransparent")),
            rims=_visualisations(data.get("rims")),
        )


@dataclass(frozen=True)
class VdmsDimensions:
    """Body dimensions, wheelbase, and ground clearance label/value pairs."""

    body_dimensions: VdmsLabelValue | None = None
    ground_clearance_with_performance: VdmsLabelValue | None = None
    ground_clearance_without_performance: VdmsLabelValue | None = None
    wheelbase: VdmsLabelValue | None = None

    @classmethod
    def from_dict(cls, data: Any) -> VdmsDimensions | None:
        if not isinstance(data, dict):
            return None
        return cls(
            body_dimensions=VdmsLabelValue.from_dict(data.get("bodyDimensions")),
            ground_clearance_with_performance=VdmsLabelValue.from_dict(
                data.get("groundClearanceWithPerformance")
            ),
            ground_clearance_without_performance=VdmsLabelValue.from_dict(
                data.get("groundClearanceWithoutPerformance")
            ),
            wheelbase=VdmsLabelValue.from_dict(data.get("wheelbase")),
        )


@dataclass(frozen=True)
class VdmsPerformanceOptimizationSpecification:
    """Optional power/torque uplift from a performance optimization."""

    power: VdmsValueUnit | None = None
    torque_max: VdmsValueUnit | None = None

    @classmethod
    def from_dict(cls, data: Any) -> VdmsPerformanceOptimizationSpecification | None:
        if not isinstance(data, dict):
            return None
        return cls(
            power=VdmsValueUnit.from_dict(data.get("power")),
            torque_max=VdmsValueUnit.from_dict(data.get("torqueMax")),
        )


@dataclass(frozen=True)
class VdmsBatterySpec:
    """Structured view of the free-text ``specification.battery`` string.

    Example input: ``"400V lithium-ion battery, 111 kWh capacity, 17 modules"``.
    Parsed values are best-effort; ``raw`` is always preserved so nothing is lost
    if a model or market uses a different string format.
    """

    raw: str | None = None
    capacity_kwh: int | float | None = None
    voltage_v: int | None = None
    modules: int | None = None

    _CAPACITY = re.compile(r"(\d+(?:\.\d+)?)\s*kwh", re.IGNORECASE)
    _VOLTAGE = re.compile(r"(\d+)\s*v\b", re.IGNORECASE)
    _MODULES = re.compile(r"(\d+)\s*modules?", re.IGNORECASE)

    @classmethod
    def from_battery_str(cls, battery: Any) -> VdmsBatterySpec | None:
        raw = _str(battery)
        if raw is None:
            return None

        capacity: int | float | None = None
        if match := cls._CAPACITY.search(raw):
            number = float(match.group(1))
            capacity = int(number) if number.is_integer() else number

        voltage = int(match.group(1)) if (match := cls._VOLTAGE.search(raw)) else None
        modules = int(match.group(1)) if (match := cls._MODULES.search(raw)) else None

        return cls(raw=raw, capacity_kwh=capacity, voltage_v=voltage, modules=modules)


@dataclass(frozen=True)
class VdmsSpecification:
    """Drivetrain/spec sheet values (raw strings as shown in the app)."""

    battery: str | None = None
    electric_motors: str | None = None
    torque: str | None = None
    total_hp: str | None = None
    total_kw: str | None = None
    trunk_capacity: VdmsLabelValue | None = None

    @classmethod
    def from_dict(cls, data: Any) -> VdmsSpecification | None:
        if not isinstance(data, dict):
            return None
        return cls(
            battery=_str(data.get("battery")),
            electric_motors=_str(data.get("electricMotors")),
            torque=_str(data.get("torque")),
            total_hp=_str(data.get("totalHp")),
            total_kw=_str(data.get("totalKw")),
            trunk_capacity=VdmsLabelValue.from_dict(data.get("trunkCapacity")),
        )


@dataclass(frozen=True)
class VdmsVehicleInformation:
    """Full VDMS record for a vehicle from the app-backend ``GetVDMSCars`` query.

    Flattens the GraphQL ``content`` block so the commonly used values
    (model year, packages, battery, specification) are accessible directly.
    """

    vin: str | None = None
    internal_vehicle_identifier: str | None = None
    registration_no: str | None = None
    market: str | None = None
    model_name: str | None = None
    model_year: int | None = None
    variant: str | None = None
    edition: str | None = None
    factory_complete_date: str | None = None
    primary_driver: str | None = None
    belongs_to_fleet: bool | None = None
    packages: list[str] = field(default_factory=list)
    curb_weight: VdmsValueUnit | None = None
    max_trailer_weight: VdmsValueUnit | None = None
    dimensions: VdmsDimensions | None = None
    images: VdmsImages | None = None
    specification: VdmsSpecification | None = None
    battery_spec: VdmsBatterySpec | None = None
    exterior: VdmsFeature | None = None
    interior: VdmsFeature | None = None
    motor: VdmsFeature | None = None
    wheels: VdmsFeature | None = None
    pilot_package: VdmsFeature | None = None
    plus_package: VdmsFeature | None = None
    performance_package: VdmsFeature | None = None
    performance_optimization: VdmsPerformanceOptimizationSpecification | None = None
    software_performance_optimization: bool | None = None

    @classmethod
    def from_dict(cls, data: Any) -> VdmsVehicleInformation:
        if not isinstance(data, dict):
            data = {}

        content = data.get("content")
        content = content if isinstance(content, dict) else {}

        model = content.get("model")
        model = model if isinstance(model, dict) else {}

        software = data.get("software")
        software = software if isinstance(software, dict) else {}
        perf_opt = software.get("performanceOptimization")
        perf_opt = perf_opt if isinstance(perf_opt, dict) else {}

        packages_raw = data.get("packages")
        packages = [p for p in packages_raw if isinstance(p, str)] if isinstance(packages_raw, list) else []

        specification = VdmsSpecification.from_dict(content.get("specification"))
        motor = VdmsFeature.from_dict(content.get("motor"))

        return cls(
            vin=_str(data.get("vin")),
            internal_vehicle_identifier=_str(data.get("internalVehicleIdentifier")),
            registration_no=_str(data.get("registrationNo")),
            market=_str(data.get("market")),
            model_name=_str(model.get("name")),
            model_year=_model_year(data.get("modelYear")),
            variant=motor.name if motor else None,
            edition=_str(data.get("edition")),
            factory_complete_date=_str(data.get("factoryCompleteDate")),
            primary_driver=_str(data.get("primaryDriver")),
            belongs_to_fleet=_bool(data.get("belongsToFleet")),
            packages=packages,
            curb_weight=VdmsValueUnit.from_dict(data.get("curbWeight")),
            max_trailer_weight=VdmsValueUnit.from_dict(data.get("maxTrailerWeight")),
            dimensions=VdmsDimensions.from_dict(content.get("dimensions")),
            images=VdmsImages.from_dict(content.get("images")),
            specification=specification,
            battery_spec=(
                VdmsBatterySpec.from_battery_str(specification.battery) if specification else None
            ),
            exterior=VdmsFeature.from_dict(content.get("exterior")),
            interior=VdmsFeature.from_dict(content.get("interior")),
            motor=motor,
            wheels=VdmsFeature.from_dict(content.get("wheels")),
            pilot_package=VdmsFeature.from_dict(content.get("pilotPackage")),
            plus_package=VdmsFeature.from_dict(content.get("plusPackage")),
            performance_package=VdmsFeature.from_dict(content.get("performancePackage")),
            performance_optimization=VdmsPerformanceOptimizationSpecification.from_dict(
                content.get("performanceOptimizationSpecification")
            ),
            software_performance_optimization=_bool(perf_opt.get("value")),
        )
