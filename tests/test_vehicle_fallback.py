"""Tests for the mystar-v2 enrichment of VIN-only VDMS responses."""

from unittest.mock import AsyncMock, patch

from polestar_api import client as client_mod
from polestar_api.discovery import VehicleInfo
from polestar_api.exceptions import ApiError
from polestar_api.models.vdms import VdmsVehicleInformation


def _api() -> client_mod.PolestarApi:
    api = client_mod.PolestarApi(email="a@b.c", password="x")
    api._auth = AsyncMock()
    api._auth.ensure_valid_token = AsyncMock(return_value="tok")
    api._connection = object()
    return api


class TestGetVehiclesEnrichment:
    async def test_vin_only_vdms_is_enriched_from_v2(self):
        vdms = [VehicleInfo(vin="VIN1")]
        v2 = [VehicleInfo(vin="vin1", model_name="Polestar 2", model_year=2022, registration_no="ABC123")]
        with patch.object(client_mod, "get_vehicles", AsyncMock(return_value=vdms)), patch.object(
            client_mod, "get_vehicles_v2", AsyncMock(return_value=v2)
        ):
            cars = await _api().get_vehicles()
        assert len(cars) == 1
        assert cars[0].vin == "VIN1"
        assert cars[0].model_name == "Polestar 2"
        assert cars[0].model_year == 2022
        assert cars[0].registration_no == "ABC123"

    async def test_complete_vdms_does_not_call_v2(self):
        vdms = [VehicleInfo(vin="VIN1", model_name="Polestar 3", model_year=2025)]
        v2_mock = AsyncMock()
        with patch.object(client_mod, "get_vehicles", AsyncMock(return_value=vdms)), patch.object(
            client_mod, "get_vehicles_v2", v2_mock
        ):
            cars = await _api().get_vehicles()
        v2_mock.assert_not_called()
        assert cars[0].model_name == "Polestar 3"

    async def test_v2_failure_keeps_vdms_result(self):
        vdms = [VehicleInfo(vin="VIN1")]
        with patch.object(client_mod, "get_vehicles", AsyncMock(return_value=vdms)), patch.object(
            client_mod, "get_vehicles_v2", AsyncMock(side_effect=ApiError("boom"))
        ):
            cars = await _api().get_vehicles()
        assert [c.vin for c in cars] == ["VIN1"]


class TestSpecificationsEnrichment:
    async def test_vin_only_specs_enriched(self):
        vdms = [VdmsVehicleInformation(vin="VIN1")]
        v2 = [VdmsVehicleInformation.from_dict({
            "vin": "VIN1", "modelName": "Polestar 2", "modelYear": 2022, "registrationNo": "ABC123",
            "content": {"specification": {"battery": "78 kWh", "torque": "660 Nm"}},
        })]
        with patch.object(client_mod, "_fetch_specifications", AsyncMock(return_value=vdms)), patch.object(
            client_mod, "_fetch_specifications_v2", AsyncMock(return_value=v2)
        ):
            specs = await _api().get_vehicle_specifications()
        spec = specs["VIN1"]
        assert spec.model_name == "Polestar 2"
        assert spec.model_year == 2022
        assert spec.registration_no == "ABC123"
        assert spec.specification is not None and spec.specification.battery == "78 kWh"

    async def test_vdms_error_falls_back_to_v2(self):
        v2 = [VdmsVehicleInformation(vin="VIN1", model_name="Polestar 4")]
        with patch.object(client_mod, "_fetch_specifications", AsyncMock(side_effect=ApiError("bad"))), patch.object(
            client_mod, "_fetch_specifications_v2", AsyncMock(return_value=v2)
        ):
            specs = await _api().get_vehicle_specifications()
        assert specs["VIN1"].model_name == "Polestar 4"


def test_from_dict_accepts_flat_model_name_and_v2_dimensions():
    spec = VdmsVehicleInformation.from_dict({
        "vin": "V", "modelName": "Polestar2",
        "content": {"dimensions": {"dimensions": {"label": "L", "value": "4606 mm"}}},
    })
    assert spec.model_name == "Polestar2"
    assert spec.dimensions is not None and spec.dimensions.body_dimensions.value == "4606 mm"
