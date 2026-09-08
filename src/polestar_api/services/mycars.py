"""MyCars service — vehicle identity, installed software version and static specs.

Unlike ``OtaDiscoveryService/GetSoftwareInfo`` (ota.py), which only reports a
*pending* update and returns an empty message when nothing is queued, this
service always reports the currently installed software version. It is also
the last remaining source of static vehicle specs (battery capacity, weight,
factory options) now that the app-backend GraphQL returns VIN-only records.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.mycars import MyCarEntry

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_LOGGER = logging.getLogger(__name__)


class MyCarsServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _service(self) -> str:
        return self._connection.backend.mycars_svc

    async def _metadata(self) -> dict:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        return metadata

    async def get_mycars(self) -> MyCarEntry | None:
        """Return the ``GetMyCars`` entry for this VIN, or ``None`` if unavailable."""
        req = encode(
            {"id": (1, "string"), "vin": (2, "string")},
            {"id": str(uuid.uuid4()), "vin": self._vin},
        )
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._service}/GetMyCars",
            req,
            metadata=await self._metadata(),
        )

        # GetMyCarsResponse.cars is `repeated MyCarEntry` (field 1). codec.decode()
        # yields a single bytes blob for one car and a list for several.
        raw = decode(data, {1: ("car", "message")})
        car_field = raw.get("car")
        if car_field is None:
            _LOGGER.warning("GetMyCars vin=%s: no car entry in response", self._vin)
            return None

        raw_entries = car_field if isinstance(car_field, list) else [car_field]
        entries = [MyCarEntry.from_bytes(b) for b in raw_entries]

        wanted = self._vin.upper()
        matching = next(
            (e for e in entries if e.details and e.details.vin.upper() == wanted),
            None,
        )
        if matching is None and len(entries) == 1:
            matching = entries[0]
        if matching is None:
            _LOGGER.warning(
                "GetMyCars vin=%s: %d entries in response, none matched this VIN",
                self._vin,
                len(entries),
            )
        return matching
