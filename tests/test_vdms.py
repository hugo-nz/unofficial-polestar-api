import json
from pathlib import Path

from polestar_api.models.vdms import VdmsBatterySpec, VdmsVehicleInformation

DATA = Path(__file__).parent / "data" / "vdms_response.json"


def _load_first_car() -> VdmsVehicleInformation:
    payload = json.loads(DATA.read_text())
    cars = payload["data"]["vdms"]["getVehiclesInformation"]
    return VdmsVehicleInformation.from_dict(cars[0])


class TestVdmsParsing:
    def test_top_level_fields(self):
        car = _load_first_car()
        assert car.vin == "YSMYK00000TEST0000"
        assert car.market == "AU"
        assert car.model_name == "Polestar 3"
        assert car.model_year == 2025
        assert car.registration_no == "TEST123"
        assert car.factory_complete_date == "2024-07-05"
        assert car.edition is None
        assert car.belongs_to_fleet is None

    def test_packages(self):
        car = _load_first_car()
        assert car.packages == ["Pilot", "Plus"]
        assert car.pilot_package is not None and car.pilot_package.name == "Pilot"
        assert car.plus_package is not None and car.plus_package.name == "Plus"
        assert car.performance_package is None

    def test_specification(self):
        spec = _load_first_car().specification
        assert spec is not None
        assert spec.battery == "400V lithium-ion battery, 111 kWh capacity, 17 modules"
        assert spec.electric_motors == "2 Electric motors, front and rear "
        assert spec.torque == "840 Nm"
        assert spec.total_hp == "489 hp"
        assert spec.total_kw == "360 kW"
        assert spec.trunk_capacity is not None
        assert spec.trunk_capacity.value == "516 litre (front and back combined)"

    def test_battery_spec_parsed(self):
        bs = _load_first_car().battery_spec
        assert bs is not None
        assert bs.capacity_kwh == 111
        assert bs.voltage_v == 400
        assert bs.modules == 17
        assert bs.raw == "400V lithium-ion battery, 111 kWh capacity, 17 modules"

    def test_weights_and_dimensions(self):
        car = _load_first_car()
        assert car.curb_weight is not None
        assert car.curb_weight.value == 2579
        assert car.curb_weight.unit == "kg"
        assert car.max_trailer_weight is not None
        assert car.max_trailer_weight.value == 2200
        assert car.dimensions is not None
        assert car.dimensions.wheelbase is not None
        assert car.dimensions.wheelbase.value == "2.985 mm"

    def test_features(self):
        car = _load_first_car()
        assert car.motor is not None and car.motor.name == "Long range Dual motor"
        assert car.variant == "Long range Dual motor"
        assert car.wheels is not None and car.wheels.name == '20" Aero'
        assert car.exterior is not None and car.exterior.name == "Space"

    def test_images(self):
        images = _load_first_car().images
        assert images is not None
        assert len(images.exterior) == 1
        assert images.exterior[0].url.endswith("exterior/0.jpg")
        assert images.exterior[0].angle == 0
        assert len(images.exterior_transparent) == 1
        assert images.exterior_transparent[0].alt is None

    def test_software_performance_optimization(self):
        assert _load_first_car().software_performance_optimization is False


class TestVdmsNullHandling:
    def test_empty_dict(self):
        car = VdmsVehicleInformation.from_dict({})
        assert car.vin is None
        assert car.model_year is None
        assert car.packages == []
        assert car.specification is None
        assert car.battery_spec is None
        assert car.images is None

    def test_non_dict_input(self):
        car = VdmsVehicleInformation.from_dict(None)
        assert car.vin is None
        assert car.packages == []

    def test_null_nested_fields(self):
        car = VdmsVehicleInformation.from_dict(
            {
                "vin": "X",
                "packages": None,
                "content": {"performancePackage": None, "specification": None},
            }
        )
        assert car.vin == "X"
        assert car.packages == []
        assert car.performance_package is None
        assert car.specification is None
        assert car.battery_spec is None


class TestVdmsBatterySpec:
    def test_unparseable_string_keeps_raw(self):
        bs = VdmsBatterySpec.from_battery_str("mystery battery")
        assert bs is not None
        assert bs.raw == "mystery battery"
        assert bs.capacity_kwh is None
        assert bs.voltage_v is None
        assert bs.modules is None

    def test_none_returns_none(self):
        assert VdmsBatterySpec.from_battery_str(None) is None

    def test_decimal_capacity(self):
        bs = VdmsBatterySpec.from_battery_str("400V battery, 78.3 kWh capacity, 27 modules")
        assert bs is not None
        assert bs.capacity_kwh == 78.3
        assert bs.voltage_v == 400
        assert bs.modules == 27
