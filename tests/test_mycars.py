"""Tests for car_information.CarInformation/GetMyCars decoding."""

from unittest.mock import AsyncMock, MagicMock, patch

from polestar_api.backend import BackendProfile
from polestar_api.codec import (
    decode,
    encode_bool,
    encode_double,
    encode_float,
    encode_message,
    encode_string,
)
from polestar_api.models.mycars import CarDetails, MyCarEntry
from polestar_api.services import mycars as mycars_mod

VIN_A = "YSMTESTVIN0000001"
VIN_B = "YSMTESTVIN0000002"


def _car(vin: str, **over) -> bytes:
    fields = {
        "model_code": "359",
        "model_name": "Polestar 3",
        "model_year": "2025",
        "software": "3.0.33",
        "market": "AU",
        "kwh": 111.0,
        "weight": 3050.0,
        "options": "359-1105-1401-CJ03-C102-EV02-2025",
    }
    fields.update(over)
    return (
        encode_string(1, vin)
        + encode_string(5, fields["model_code"])
        + encode_string(6, fields["model_name"])
        + encode_string(7, fields["model_year"])
        + encode_string(9, fields["software"])
        + encode_string(10, fields["market"])
        + encode_message(40, encode_float(5, fields["kwh"]))
        + encode_double(44, fields["weight"])
        + encode_string(47, fields["options"])
    )


def _entry(vin: str, plate: str = "", **over) -> bytes:
    body = encode_message(1, _car(vin, **over)) + encode_bool(2, True) + encode_bool(3, True)
    if plate:
        body += encode_string(4, plate)
    return body


def _response(*entries: bytes) -> bytes:
    return b"".join(encode_message(1, e) for e in entries)


class TestModels:
    def test_decodes_details_and_derived_values(self):
        entry = MyCarEntry.from_bytes(_entry(VIN_A, plate="ABC123"))
        d = entry.details
        assert isinstance(d, CarDetails)
        assert d.vin == VIN_A
        assert d.model_code == "359"
        assert d.model_name == "Polestar 3"
        assert d.model_year == "2025"
        assert d.model_year_int == 2025
        assert d.installed_software_version == "3.0.33"
        assert d.market == "AU"
        assert d.battery_capacity_kwh == 111.0
        assert d.gross_weight_kg == 3050.0
        assert d.option_codes[:3] == ["359", "1105", "1401"]
        assert entry.user_is_linked is True
        assert entry.user_is_owner is True
        assert entry.registration_plate == "ABC123"

    def test_missing_optional_blocks(self):
        entry = MyCarEntry.from_bytes(encode_message(1, encode_string(1, VIN_A)))
        d = entry.details
        assert d.vin == VIN_A
        assert d.battery is None
        assert d.battery_capacity_kwh is None
        assert d.gross_weight_kg is None
        assert d.model_year_int is None
        assert d.option_codes == []
        assert entry.registration_plate == ""
        assert entry.user_is_owner is None

    def test_unknown_fields_are_ignored(self):
        extra = _car(VIN_A) + encode_string(99, "future") + encode_message(73, b"\x01\x02")
        d = CarDetails.from_bytes(extra)
        assert d.model_name == "Polestar 3"


def _service(response: bytes, vin: str) -> mycars_mod.MyCarsServiceClient:
    conn = MagicMock()
    conn.backend = BackendProfile()
    conn.channel = object()
    conn.get_metadata = AsyncMock(return_value={"authorization": "Bearer t"})
    svc = mycars_mod.MyCarsServiceClient(conn, vin)
    return svc


class TestService:
    async def test_single_car(self):
        svc = _service(_response(_entry(VIN_A)), VIN_A)
        call = AsyncMock(return_value=_response(_entry(VIN_A)))
        with patch.object(mycars_mod.grpc_call, "unary_unary", call):
            entry = await svc.get_mycars()
        assert entry.details.vin == VIN_A
        path = call.await_args.args[1]
        assert path == "/car_information.CarInformation/GetMyCars"
        req = decode(call.await_args.args[2], {1: ("id", "string"), 2: ("vin", "string")})
        assert req["vin"] == VIN_A
        assert call.await_args.kwargs["metadata"]["vin"] == VIN_A

    async def test_multi_car_picks_matching_vin(self):
        svc = _service(b"", VIN_B)
        resp = _response(_entry(VIN_A), _entry(VIN_B, model_name="Polestar 4", kwh=100.0))
        with patch.object(mycars_mod.grpc_call, "unary_unary", AsyncMock(return_value=resp)):
            entry = await svc.get_mycars()
        assert entry.details.vin == VIN_B
        assert entry.details.model_name == "Polestar 4"
        assert entry.details.battery_capacity_kwh == 100.0

    async def test_vin_match_is_case_insensitive(self):
        svc = _service(b"", VIN_A.lower())
        with patch.object(mycars_mod.grpc_call, "unary_unary", AsyncMock(return_value=_response(_entry(VIN_A)))):
            entry = await svc.get_mycars()
        assert entry.details.vin == VIN_A

    async def test_single_entry_without_vin_match_is_returned(self):
        svc = _service(b"", VIN_B)
        with patch.object(mycars_mod.grpc_call, "unary_unary", AsyncMock(return_value=_response(_entry(VIN_A)))):
            entry = await svc.get_mycars()
        assert entry.details.vin == VIN_A

    async def test_empty_response_returns_none(self):
        svc = _service(b"", VIN_A)
        with patch.object(mycars_mod.grpc_call, "unary_unary", AsyncMock(return_value=b"")):
            assert await svc.get_mycars() is None

    async def test_multi_car_no_match_returns_none(self):
        svc = _service(b"", "YSMOTHERVIN000000")
        resp = _response(_entry(VIN_A), _entry(VIN_B))
        with patch.object(mycars_mod.grpc_call, "unary_unary", AsyncMock(return_value=resp)):
            assert await svc.get_mycars() is None
