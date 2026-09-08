"""MyCars models — vehicle identity, installed software version and static specs.

Source: ``car_information.CarInformation/GetMyCars`` on the C3 gRPC backend.
This is the service the official Polestar app uses for the "my cars" screen and
it is currently the only place that still exposes static vehicle data
(battery capacity, weight, factory option codes) after Polestar's app-backend
GraphQL (``GetVDMSCars``) started returning a VIN-only record.

Field numbers were established from:

* kildahldev/unofficial-polestar-api#32 / pypolestar/pypolestar#79
  (vin, model_name, model_year, installed_software_version, market)
* NicolasKheirallah/Hisingen ``PolestarGRPCCapabilities.swift``
  (MyCar wrapper fields, capability sub-messages)
* a live capture from a 2025 Polestar 3 (AU market): model_code,
  battery.capacity_kwh, gross_weight_kg, factory_options.

Only fields whose meaning is confirmed against known ground truth are
modelled; protobuf preserves unknown fields so the rest is safely ignored.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..wire import ProtoMessage


@dataclass(frozen=True)
class CarBattery(ProtoMessage, schema={5: "capacity_kwh"}):
    """Nested battery block (``Car`` field 40)."""

    capacity_kwh: float | None = None


@dataclass(frozen=True)
class CarDetails(ProtoMessage, schema={
    1: "vin",
    5: "model_code",
    6: "model_name",
    7: "model_year",
    9: "installed_software_version",
    10: "market",
    40: "battery",
    44: "gross_weight_kg",
    47: "factory_options",
}):
    vin: str = ""
    model_code: str = ""
    model_name: str = ""
    model_year: str = ""
    installed_software_version: str = ""
    market: str = ""
    battery: CarBattery | None = None
    gross_weight_kg: float | None = None
    factory_options: str = ""

    @property
    def model_year_int(self) -> int | None:
        try:
            return int(self.model_year)
        except (TypeError, ValueError):
            return None

    @property
    def battery_capacity_kwh(self) -> float | None:
        return self.battery.capacity_kwh if self.battery else None

    @property
    def option_codes(self) -> list[str]:
        """``factory_options`` split into its dash-separated PNO-style codes."""
        return [c for c in self.factory_options.split("-") if c] if self.factory_options else []


@dataclass(frozen=True)
class MyCarEntry(ProtoMessage, schema={
    1: "details",
    2: "user_is_linked",
    3: "user_is_owner",
    4: "registration_plate",
}):
    """A single entry of ``GetMyCarsResponse.cars``.

    ``registration_plate`` is market dependent and absent on at least AU
    accounts; prefer the mystar-v2 ``registrationNo`` when both exist.
    """

    details: CarDetails | None = None
    user_is_linked: bool | None = None
    user_is_owner: bool | None = None
    registration_plate: str = ""
