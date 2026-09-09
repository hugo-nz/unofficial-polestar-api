"""Service discovery for Polestar gRPC endpoints and vehicle listing."""

from __future__ import annotations

import ssl
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from .exceptions import ApiError
from .models.carspec import CarFeatures, CarSpecifications
from .models.poms import PomsOrder
from .models.vdms import VdmsVehicleInformation

_SSL_CONTEXT = ssl.create_default_context()

C3_DISCOVERY_URL = "https://cnepmob.volvocars.com/"
C3_ACCEPT_HEADER = "application/volvo.cloud.cnepmob.v1+json"

APP_BACKEND_GRAPHQL_URL = "https://pc-api.polestar.com/eu-north-1/app-backend/api/graphql"
APP_BACKEND_ACCEPT_HEADER = "multipart/mixed;deferSpec=20220824, application/graphql-response+json, application/json"
APP_BACKEND_OPERATION_NAME = "GetVDMSCars"
APP_BACKEND_CLIENT_LIBRARY = {"name": "apollo-kotlin", "version": "4.4.1"}
APP_FORCE_UPDATE_VERSION = "5.11.0"
APP_LOCALE = "SE"
APP_USER_AGENT = "PolestarApp/5.11.0b1111 Android/14"

APP_BACKEND_GET_VEHICLES_QUERY = """
query GetVDMSCars {
    vdms {
        getVehiclesInformation {
            vin
            internalVehicleIdentifier
            registrationNo
            modelYear
            content { model { name } }
        }
    }
}
"""

# ── mystar-v2 fallback ──────────────────────────────────────────
# Separate "consumer" GraphQL endpoint (used by pypolestar/pypolestar)
# that lists vehicles via a different operation (GetConsumerCarsV2) and
# schema than the app-backend VDMS endpoint above. When Polestar changes
# the VDMS schema and APP_BACKEND_GET_VEHICLES_QUERY starts failing (see
# https://github.com/kildahldev/unofficial-polestar-api/issues/30), this
# endpoint has historically kept working, so it is used as a fallback
# vehicle-listing source that still yields real model/registration data
# instead of falling all the way back to a bare VIN.
MYSTAR_V2_URL = "https://pc-api.polestar.com/eu-north-1/mystar-v2/"
MYSTAR_LOCALE = "en-GB"

MYSTAR_GET_CONSUMER_CARS_QUERY = """
query GetConsumerCarsV2 {
    getConsumerCarsV2 {
        vin
        internalVehicleIdentifier
        registrationNo
        modelYear
        modelName
        pno34
        structureWeek
    }
}
"""

# ── POMS orders ─────────────────────────────────────────────────
# Order-management query used by the official app. Its ``configuration``
# block carries the same human-readable spec strings VDMS ``content`` used
# to have (battery, power, torque, motor variant, packages), so it is the
# preferred source for those once VDMS returns VIN-only records. Only the
# ordering account sees its orders.
APP_BACKEND_GET_ORDERS_OPERATION = "GetOrdersV2"
APP_BACKEND_GET_ORDERS_QUERY = """
query GetOrdersV2 {
    poms {
        getOrders {
            data {
                car { edition engine exterior interior model modelYear vin wheels }
                configurationId
                countryCode
                orderId
                orderState
                orderV2 {
                    configuration {
                        dimensions { label value }
                        specifications { label value }
                        features { displayType title }
                        modelYear
                        pno34
                        structureWeek
                    }
                    orderStatus { status { deliveryStage } }
                }
                placedAt
                type
            }
        }
    }
}
"""

# ── car-configurator specifications ─────────────────────────────
# Unauthenticated REST service used by the official iOS/Android apps for
# the "Specifications" screen (power, torque, battery, range, weights,
# dimensions) and the fitted-features list (motor variant, packages,
# colour, upholstery, wheels). Keyed by the vehicle's model year, PNO34
# and structure week (all from GetConsumerCarsV2 / CarInformationByVins).
# NOTE: ``locale`` is the *market code* (``au``, ``se``), not a BCP-47
# locale — ``en-AU`` returns 404.
CAR_CONFIGURATOR_URL = "https://pc-api.polestar.com/eu-north-1/car-configurator-back/"
CAR_CONFIGURATOR_SENDER = "polestar-app-android"

# Richer GetConsumerCarsV2 selection used as a fallback for the deep VDMS
# specifications query. The mystar-v2 record shape mirrors the VDMS one
# (same ``content { model, motor, specification, dimensions ... }`` block and
# top-level ``curbWeight``/``maxTrailerWeight``/``edition``/``software``), so
# it can be parsed by ``VdmsVehicleInformation.from_dict`` directly. Car
# images are intentionally not requested. If Polestar trims this schema the
# caller retries with MYSTAR_GET_CONSUMER_CARS_QUERY.
MYSTAR_GET_CONSUMER_CARS_FULL_QUERY = """
query GetConsumerCarsV2 {
    getConsumerCarsV2 {
        vin
        internalVehicleIdentifier
        registrationNo
        market
        modelYear
        modelName
        edition
        factoryCompleteDate
        primaryDriver
        belongsToFleet
        curbWeight { value unit }
        maxTrailerWeight { value unit }
        software { performanceOptimization { value } }
        content {
            model { name }
            motor { name }
            exterior { name }
            interior { name }
            wheels { name }
            pilotPackage { name }
            plusPackage { name }
            performancePackage { name }
            performanceOptimizationSpecification { power { value unit } torqueMax { value unit } }
            dimensions {
                dimensions { label value }
                groundClearanceWithPerformance { label value }
                groundClearanceWithoutPerformance { label value }
                wheelbase { label value }
            }
            specification {
                battery
                electricMotors
                torque
                totalHp
                totalKw
                trunkCapacity { label value }
            }
        }
    }
}
"""

APP_BACKEND_GET_VDMS_FULL_QUERY = """
query GetVDMSCars {
    vdms {
        getVehiclesInformation {
            vin
            internalVehicleIdentifier
            registrationNo
            market
            modelYear
            edition
            factoryCompleteDate
            primaryDriver
            belongsToFleet
            packages
            curbWeight { value unit }
            maxTrailerWeight { value unit }
            software { performanceOptimization { value } }
            content {
                model { name }
                motor { name }
                exterior { name }
                interior { name }
                wheels { name }
                pilotPackage { name }
                plusPackage { name }
                performancePackage { name }
                performanceOptimizationSpecification { power { value unit } torqueMax { value unit } }
                dimensions {
                    bodyDimensions { label value }
                    groundClearanceWithPerformance { label value }
                    groundClearanceWithoutPerformance { label value }
                    wheelbase { label value }
                }
                images {
                    interior { alt angle url }
                    exterior { alt angle url }
                    exteriorTransparent { alt angle url }
                    rims { alt angle url }
                }
                specification {
                    battery
                    electricMotors
                    torque
                    totalHp
                    totalKw
                    trunkCapacity { label value }
                }
            }
        }
    }
}
"""

@dataclass
class GrpcEndpoint:
    host: str
    port: int
    keep_alive_time: int | None = None


@dataclass
class VehicleInfo:
    vin: str
    internal_id: str | None = None
    registration_no: str | None = None
    model_year: int | None = None
    model_name: str | None = None
    pno34: str | None = None
    structure_week: str | None = None


async def discover_c3_endpoint(access_token: str) -> GrpcEndpoint:
    """Discover the C3 gRPC endpoint via the Volvo Cloud discovery service."""
    async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
        r = await client.get(
            C3_DISCOVERY_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": C3_ACCEPT_HEADER,
            },
        )
        if r.status_code != 200:
            raise ApiError(f"C3 discovery failed: {r.status_code}", r.status_code)

        data = r.json()

    # The response contains c3 and c3Lbs environments
    c3 = data.get("c3", {})
    host = c3.get("grpcHost")
    port = c3.get("grpcPort", 443)
    keep_alive = c3.get("grpcKeepAliveTime")

    if not host:
        raise ApiError("C3 discovery response missing grpcHost")

    return GrpcEndpoint(host=host, port=int(port), keep_alive_time=keep_alive)


async def get_vehicles(access_token: str) -> list[VehicleInfo]:
    """Fetch the user's vehicles.

    The current mobile app uses the app-backend GraphQL endpoint with the
    X-PolestarId-Authorization header and Apollo-style request metadata.
    """
    async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
        response = await client.post(
            APP_BACKEND_GRAPHQL_URL,
            headers={
                **_app_backend_headers(access_token),
                "Accept": APP_BACKEND_ACCEPT_HEADER,
                "Content-Type": "application/json",
            },
            json=_app_backend_payload(),
        )
        if response.status_code != 200:
            raise ApiError(f"Vehicle list failed (app-backend: {_http_failure(response)})", response.status_code)

        data = response.json()
        graphql_error = _graphql_error_text(data.get("errors"))
        if graphql_error:
            raise ApiError(f"Vehicle list failed (app-backend: {graphql_error})")

        return _extract_app_backend_vehicles(data)


async def get_vehicle_specifications(access_token: str) -> list[VdmsVehicleInformation]:
    """Fetch full VDMS specifications for the user's vehicles.

    Uses the same app-backend GraphQL endpoint and ``X-PolestarId-Authorization``
    header as :func:`get_vehicles`, but selects the full VDMS field set (model
    year, packages, battery, specifications, dimensions, images, etc.).
    """
    async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
        response = await client.post(
            APP_BACKEND_GRAPHQL_URL,
            headers={
                **_app_backend_headers(access_token),
                "Accept": APP_BACKEND_ACCEPT_HEADER,
                "Content-Type": "application/json",
            },
            json={
                "operationName": APP_BACKEND_OPERATION_NAME,
                "variables": {},
                "query": APP_BACKEND_GET_VDMS_FULL_QUERY,
                "extensions": {"clientLibrary": APP_BACKEND_CLIENT_LIBRARY},
            },
        )
        if response.status_code != 200:
            raise ApiError(
                f"VDMS specifications failed (app-backend: {_http_failure(response)})",
                response.status_code,
            )

        data = response.json()
        graphql_error = _graphql_error_text(data.get("errors"))
        if graphql_error:
            raise ApiError(f"VDMS specifications failed (app-backend: {graphql_error})")

        cars = ((data.get("data") or {}).get("vdms") or {}).get("getVehiclesInformation") or []
        return [VdmsVehicleInformation.from_dict(car) for car in cars if isinstance(car, dict)]


async def _post_mystar_v2(access_token: str, query: str, what: str) -> list[Any]:
    """POST a ``GetConsumerCarsV2`` query to mystar-v2 and return the car list."""
    async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
        response = await client.post(
            MYSTAR_V2_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "operationName": "GetConsumerCarsV2",
                "variables": {"locale": MYSTAR_LOCALE},
                "query": query,
            },
        )
        if response.status_code != 200:
            raise ApiError(f"{what} failed (mystar-v2: {_http_failure(response)})", response.status_code)

        data = response.json()
        graphql_error = _graphql_error_text(data.get("errors"))
        if graphql_error:
            raise ApiError(f"{what} failed (mystar-v2: {graphql_error})")

        cars = (data.get("data") or {}).get("getConsumerCarsV2") or []
        return cars if isinstance(cars, list) else []


async def get_vehicles_v2(access_token: str) -> list[VehicleInfo]:
    """Fetch the user's vehicles from the mystar-v2 endpoint.

    Fallback for :func:`get_vehicles` used when the app-backend VDMS
    vehicle-listing query fails (e.g. after a Polestar schema change, see
    https://github.com/kildahldev/unofficial-polestar-api/issues/30) or
    succeeds but returns records with no metadata (VIN only). Uses the
    same consumer GraphQL endpoint and ``GetConsumerCarsV2`` operation as
    pypolestar/pypolestar, with simple bearer-token auth instead of the
    app-backend's Apollo/``X-PolestarId-Authorization`` headers. Returns
    the same fields as ``get_vehicles`` (vin, internal id, registration
    number, model year, model name) so callers don't need to know which
    endpoint served the data.
    """
    cars = await _post_mystar_v2(access_token, MYSTAR_GET_CONSUMER_CARS_QUERY, "Vehicle list")
    return _build_vehicle_list_v2(cars)


async def get_vehicle_specifications_v2(access_token: str) -> list[VdmsVehicleInformation]:
    """Fetch vehicle specifications from mystar-v2 ``GetConsumerCarsV2``.

    Fallback for :func:`get_vehicle_specifications`. Polestar's VDMS
    backend may answer the deep ``GetVDMSCars`` query with a record that
    only carries the VIN (every other field ``null``) for some accounts /
    markets, while the consumer endpoint still has the full model,
    registration and specification data. Tries the rich selection first
    and retries with the minimal one if the rich schema is rejected.
    """
    try:
        cars = await _post_mystar_v2(
            access_token, MYSTAR_GET_CONSUMER_CARS_FULL_QUERY, "Vehicle specifications"
        )
    except ApiError as rich_err:
        if rich_err.status_code in (401, 403):
            raise
        cars = await _post_mystar_v2(
            access_token, MYSTAR_GET_CONSUMER_CARS_QUERY, "Vehicle specifications"
        )
    return [VdmsVehicleInformation.from_dict(car) for car in cars if isinstance(car, dict)]


def _build_vehicle_list_v2(cars: list[Any]) -> list[VehicleInfo]:
    """Normalize mystar-v2 vehicle records (flat modelName, no content wrapper)."""
    vehicles: list[VehicleInfo] = []
    for car in cars:
        if not isinstance(car, dict):
            continue
        vin = car.get("vin")
        if not isinstance(vin, str) or not vin:
            continue

        vehicles.append(
            VehicleInfo(
                vin=vin,
                internal_id=_string_or_none(car.get("internalVehicleIdentifier")),
                registration_no=_string_or_none(car.get("registrationNo")),
                model_year=_parse_model_year(car.get("modelYear")),
                model_name=_string_or_none(car.get("modelName")),
                pno34=_string_or_none(car.get("pno34")),
                structure_week=_string_or_none(car.get("structureWeek")),
            )
        )
    return vehicles


async def get_orders(access_token: str) -> list[PomsOrder]:
    """Fetch the account's POMS orders (with per-car configuration specs)."""
    async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
        response = await client.post(
            APP_BACKEND_GRAPHQL_URL,
            headers={
                **_app_backend_headers(access_token),
                "X-APOLLO-OPERATION-NAME": APP_BACKEND_GET_ORDERS_OPERATION,
                "Accept": APP_BACKEND_ACCEPT_HEADER,
                "Content-Type": "application/json",
            },
            json={
                "operationName": APP_BACKEND_GET_ORDERS_OPERATION,
                "variables": {},
                "query": APP_BACKEND_GET_ORDERS_QUERY,
                "extensions": {"clientLibrary": APP_BACKEND_CLIENT_LIBRARY},
            },
        )
    if response.status_code != 200:
        raise ApiError(f"Orders failed (app-backend: {_http_failure(response)})", response.status_code)
    data = response.json()
    graphql_error = _graphql_error_text(data.get("errors"))
    if graphql_error:
        raise ApiError(f"Orders failed (app-backend: {graphql_error})")
    orders = (((data.get("data") or {}).get("poms") or {}).get("getOrders") or {}).get("data") or []
    if not isinstance(orders, list):
        return []
    return [o for o in (PomsOrder.from_dict(x) for x in orders) if o]


def _configurator_car_info_url(model_year: int | str, pno34: str, structure_week: str, suffix: str) -> str:
    # pno34 contains embedded spaces that must survive as %20 in the path.
    return (
        f"{CAR_CONFIGURATOR_URL}configurator/api/car-info/"
        f"{quote(str(model_year), safe='')}/{quote(pno34, safe='')}/{quote(structure_week, safe='')}/{suffix}"
    )


async def _get_configurator(url: str, market: str, what: str) -> Any:
    async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
        r = await client.get(
            url,
            params={"locale": market.lower()},
            headers={"Accept": "application/json", "sender": CAR_CONFIGURATOR_SENDER},
        )
    if r.status_code != 200:
        raise ApiError(f"{what} failed: {r.status_code} {r.text[:200]}", r.status_code)
    try:
        return r.json()
    except ValueError as e:
        raise ApiError(f"{what}: invalid JSON response") from e


async def get_car_specifications(
    model_year: int | str, pno34: str, structure_week: str, market: str
) -> CarSpecifications:
    """Fetch the configurator specification table for one car configuration.

    ``market`` is the two-letter market code (e.g. ``"AU"``) as returned by
    GetMyCars / VDMS ``market``.
    """
    url = _configurator_car_info_url(model_year, pno34, structure_week, "car-spec/specifications/en-fallback")
    return CarSpecifications.from_dict(await _get_configurator(url, market, "Car specifications"))


async def get_car_features(
    model_year: int | str, pno34: str, structure_week: str, market: str
) -> CarFeatures:
    """Fetch the fitted-features list (motor variant, packages, colour, wheels...)."""
    url = _configurator_car_info_url(model_year, pno34, structure_week, "car-spec/en-fallback")
    return CarFeatures.from_dict(await _get_configurator(url, market, "Car features"))


def _extract_app_backend_vehicles(data: dict[str, Any]) -> list[VehicleInfo]:
    """Parse vehicles from the app-backend GraphQL response."""
    cars = ((data.get("data") or {}).get("vdms") or {}).get("getVehiclesInformation") or []
    return _build_vehicle_list(cars)


def _app_backend_headers(access_token: str) -> dict[str, str]:
    """Return the headers the mobile app adds around GraphQL calls."""
    return {
        "User-Agent": APP_USER_AGENT,
        "X-Polestar-Force-Update-Version": APP_FORCE_UPDATE_VERSION,
        "X-Polestar-Locale": APP_LOCALE,
        "X-PolestarId-Authorization": f"Bearer {access_token}",
        "X-APOLLO-OPERATION-NAME": APP_BACKEND_OPERATION_NAME,
        "X-APOLLO-REQUEST-UUID": str(uuid.uuid4()),
    }


def _app_backend_payload() -> dict[str, Any]:
    """Return the POST body Apollo sends for the vehicle discovery query."""
    return {
        "operationName": APP_BACKEND_OPERATION_NAME,
        "variables": {},
        "query": APP_BACKEND_GET_VEHICLES_QUERY,
        "extensions": {"clientLibrary": APP_BACKEND_CLIENT_LIBRARY},
    }


def _build_vehicle_list(cars: list[Any]) -> list[VehicleInfo]:
    """Normalize GraphQL vehicle records into VehicleInfo objects."""
    vehicles: list[VehicleInfo] = []
    for car in cars:
        if not isinstance(car, dict):
            continue
        vin = car.get("vin")
        if not isinstance(vin, str) or not vin:
            continue

        content = car.get("content") or {}
        model = content.get("model") if isinstance(content, dict) else {}
        model_name = model.get("name") if isinstance(model, dict) else None
        vehicles.append(
            VehicleInfo(
                vin=vin,
                internal_id=_string_or_none(car.get("internalVehicleIdentifier")),
                registration_no=_string_or_none(car.get("registrationNo")),
                model_year=_parse_model_year(car.get("modelYear")),
                model_name=_string_or_none(model_name),
            )
        )
    return vehicles


def _graphql_error_text(errors: object) -> str | None:
    """Return a compact GraphQL error summary."""
    if not isinstance(errors, list) or not errors:
        return None

    messages = []
    for error in errors:
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                messages.append(message)

    if messages:
        return "; ".join(messages)
    return "graphql error"


def _http_failure(response: httpx.Response) -> str:
    """Return a compact HTTP failure summary including body message when present."""
    detail: str | None = None
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        if text:
            detail = text.replace("\n", " ")[:200]
    else:
        if isinstance(payload, dict):
            detail = _graphql_error_text(payload.get("errors"))
            if detail is None:
                for key in ("message", "error", "detail"):
                    value = payload.get(key)
                    if isinstance(value, str) and value:
                        detail = value
                        break

    if detail:
        return f"{response.status_code} ({detail})"
    return str(response.status_code)


def _parse_model_year(value: object) -> int | None:
    """Normalize model year strings to integers when possible."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _string_or_none(value: object) -> str | None:
    """Return strings unchanged and coerce everything else to None."""
    return value if isinstance(value, str) and value else None
