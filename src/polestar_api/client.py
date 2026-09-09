"""Main entry point for the Polestar API client."""

from __future__ import annotations

from .auth import WEB_CLIENT, AuthManager, FileTokenStore, MemoryTokenStore, TokenStore
from .connection import GrpcConnection
from dataclasses import fields, replace

from .discovery import (
    VehicleInfo,
    discover_c3_endpoint,
    get_vehicle_specifications as _fetch_specifications,
    get_vehicle_specifications_v2 as _fetch_specifications_v2,
    get_orders,
    get_vehicles,
    get_vehicles_v2,
)
from .exceptions import ApiError, AuthError
from .models.poms import PomsOrder
from .models.vdms import VdmsVehicleInformation
from .vehicle import Vehicle


class PolestarApi:
    """Async client for the Polestar vehicle API.

    Usage::

        async with PolestarApi(email="...", password="...") as api:
            vehicles = await api.get_vehicles()
            battery = await vehicles[0].get_battery()
            if battery is not None:
                print(battery.charge_level)
    """

    def __init__(
        self,
        email: str,
        password: str,
        *,
        token_store: TokenStore | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._auth = AuthManager(token_store=token_store)
        # Second identity for the mystar-v2 consumer endpoint, which rejects
        # mobile-app tokens (401). Created lazily on first use so accounts
        # that never need the fallback don't pay for a second login.
        self._web_auth = AuthManager(
            token_store=_web_token_store(token_store), client=WEB_CLIENT
        )
        self._web_authenticated = False
        self._connection: GrpcConnection | None = None
        self._vehicle_cache: list[VehicleInfo] | None = None

    async def async_init(self) -> None:
        """Authenticate and discover endpoints. Must be called before use."""
        await self._auth.authenticate(self._email, self._password)
        token = await self._auth.ensure_valid_token()
        endpoint = await discover_c3_endpoint(token)
        self._connection = GrpcConnection(
            host=endpoint.host,
            port=endpoint.port,
            auth=self._auth,
        )

    async def _mystar_token(self) -> str:
        """Return a web-client token for mystar-v2, logging in on first use."""
        if not self._web_authenticated:
            await self._web_auth.authenticate(self._email, self._password)
            self._web_authenticated = True
        return await self._web_auth.ensure_valid_token()

    async def get_vehicles(self) -> list[Vehicle]:
        """Fetch the user's vehicles.

        Tries the app-backend VDMS vehicle-listing query first. If that
        fails with an :class:`ApiError` (e.g. after a Polestar schema
        change — see
        https://github.com/kildahldev/unofficial-polestar-api/issues/30),
        falls back to the mystar-v2 ``GetConsumerCarsV2`` endpoint, which
        still returns real ``model_name``/``model_year``/``registration_no``
        metadata even when VDMS discovery is broken. Only if both sources
        fail does this raise; callers can fall back further to
        :meth:`vehicle_from_vin` at that point.
        """
        token = await self._auth.ensure_valid_token()
        try:
            infos = await get_vehicles(token)
        except ApiError:
            infos = await get_vehicles_v2(await self._mystar_token())
        else:
            # VDMS can also "succeed" with VIN-only records (every other
            # field null) for some accounts/markets. Enrich from mystar-v2
            # in that case; ignore its failures since we already have VINs.
            if not infos or any(_vehicle_info_incomplete(i) for i in infos):
                try:
                    infos = _merge_vehicle_infos(
                        infos, await get_vehicles_v2(await self._mystar_token())
                    )
                except (ApiError, AuthError):
                    pass
        self._vehicle_cache = infos
        return [
            Vehicle(
                vin=info.vin,
                connection=self._connection,
                internal_id=info.internal_id,
                registration_no=info.registration_no,
                model_year=info.model_year,
                model_name=info.model_name,
                pno34=info.pno34,
                structure_week=info.structure_week,
            )
            for info in infos
        ]

    async def get_vehicle(self, vin: str) -> Vehicle:
        """Get a specific vehicle by VIN."""
        vehicles = await self.get_vehicles()
        for v in vehicles:
            if v.vin == vin:
                return v
        raise ValueError(f"Vehicle not found: {vin}")

    def vehicle_from_vin(self, vin: str) -> Vehicle:
        """Build a ``Vehicle`` directly from a known VIN, bypassing
        :meth:`get_vehicles`.

        Use this as a fallback when the account's vehicle-listing
        GraphQL query (``get_vehicles``) fails with an :class:`ApiError`
        (for example when Polestar changes the app-backend schema) but
        the vehicle's VIN is already known. All live telemetry and
        controls still work normally since they go through the gRPC/C3
        connection established in :meth:`async_init`, which is
        independent of the vehicle-listing call. Metadata that would
        normally come from the listing response (``internal_id``,
        ``registration_no``, ``model_year``, ``model_name``) will be
        left unset.
        """
        if self._connection is None:
            raise ApiError("Cannot build a vehicle before async_init() has completed")
        return Vehicle(vin=vin, connection=self._connection)

    async def get_orders(self) -> list[PomsOrder]:
        """POMS orders for this account, each with its car configuration
        (battery/power/torque strings, motor variant, packages, pno34)."""
        return await get_orders(await self._auth.ensure_valid_token())

    async def get_order_for_vin(self, vin: str) -> PomsOrder | None:
        """The POMS order whose car matches ``vin`` (``None`` if not ordered by this account)."""
        want = vin.upper()
        return next((o for o in await self.get_orders() if (o.vin or "").upper() == want), None)

    async def get_vehicle_specifications(self) -> dict[str, VdmsVehicleInformation]:
        """Fetch full VDMS specifications (model year, packages, battery,
        specifications, dimensions, images) for the account, keyed by VIN.

        Additive helper that reuses the existing app-backend endpoint and token;
        it does not require the gRPC connection and leaves ``get_vehicles`` and
        all live gRPC methods unchanged.
        """
        token = await self._auth.ensure_valid_token()
        try:
            specs = await _fetch_specifications(token)
        except ApiError:
            specs = await _fetch_specifications_v2(await self._mystar_token())
        else:
            # Same VIN-only failure mode as in get_vehicles(): fill any
            # missing fields from the consumer (mystar-v2) endpoint.
            if not specs or any(_spec_incomplete(s) for s in specs):
                try:
                    specs = _merge_specs(
                        specs, await _fetch_specifications_v2(await self._mystar_token())
                    )
                except (ApiError, AuthError):
                    pass
        return {spec.vin: spec for spec in specs if spec.vin}

    async def close(self) -> None:
        """Close all connections."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> PolestarApi:
        await self.async_init()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()


def _vehicle_info_incomplete(info: VehicleInfo) -> bool:
    # VDMS never returns pno34/structureWeek, which the configurator spec
    # lookup needs, so a VDMS-only record always warrants mystar-v2 enrichment.
    return (
        info.model_name is None and info.model_year is None and info.registration_no is None
    ) or info.pno34 is None


def _spec_incomplete(spec: VdmsVehicleInformation) -> bool:
    return spec.model_name is None and spec.model_year is None and spec.specification is None


def _merge_vehicle_infos(primary: list[VehicleInfo], secondary: list[VehicleInfo]) -> list[VehicleInfo]:
    """Fill ``None`` fields of ``primary`` records from ``secondary`` (matched by VIN).

    Vehicles only present in ``secondary`` are appended.
    """
    by_vin = {v.vin.upper(): v for v in secondary if v.vin}
    merged: list[VehicleInfo] = []
    seen: set[str] = set()
    for info in primary:
        key = info.vin.upper()
        seen.add(key)
        other = by_vin.get(key)
        merged.append(_fill_missing(info, other) if other else info)
    merged.extend(v for k, v in by_vin.items() if k not in seen)
    return merged


def _merge_specs(
    primary: list[VdmsVehicleInformation], secondary: list[VdmsVehicleInformation]
) -> list[VdmsVehicleInformation]:
    by_vin = {s.vin.upper(): s for s in secondary if s.vin}
    merged: list[VdmsVehicleInformation] = []
    seen: set[str] = set()
    for spec in primary:
        key = (spec.vin or "").upper()
        seen.add(key)
        other = by_vin.get(key)
        merged.append(_fill_missing(spec, other) if other else spec)
    merged.extend(s for k, s in by_vin.items() if k not in seen)
    return merged


def _fill_missing(primary, secondary):
    """Return ``primary`` with every ``None``/empty-list field taken from ``secondary``."""
    updates = {}
    for f in fields(primary):
        value = getattr(primary, f.name)
        if value is None or value == []:
            other = getattr(secondary, f.name, None)
            if other is not None and other != []:
                updates[f.name] = other
    return replace(primary, **updates) if updates else primary


def _web_token_store(token_store: TokenStore | None) -> TokenStore:
    """Persist the web-client tokens next to the caller's mobile-client ones.

    Tokens from the two OIDC clients are not interchangeable, so they can't
    share a store. For a :class:`FileTokenStore` use a sibling ``.web`` file
    so the second login is also cached across processes; otherwise fall back
    to memory.
    """
    path = getattr(token_store, "_path", None) if isinstance(token_store, FileTokenStore) else None
    if path is not None:
        return FileTokenStore(path.with_name(path.name + ".web"))
    return MemoryTokenStore()
