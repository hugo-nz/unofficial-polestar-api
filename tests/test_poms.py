from polestar_api.models.poms import PomsOrder

ORDER = {
    "car": {
        "edition": None,
        "engine": "Long range Dual motor",
        "exterior": "Space",
        "interior": "Animal welfare Nappa leather in Zinc with Black ash deco",
        "model": "Polestar 3",
        "modelYear": "2025",
        "vin": "YSMTESTVIN0000001",
        "wheels": '20" Aero',
    },
    "countryCode": "AU",
    "orderId": "ORD-1",
    "orderState": "delivered",
    "orderV2": {
        "configuration": {
            "dimensions": [
                {"label": "Dimensions (L/H/W)", "value": "4.9m/1.61m/2.12m"},
                {"label": "Wheelbase", "value": "2.985 mm"},
            ],
            "specifications": [
                {"label": "Cargo capacity", "value": "516 litre (front and back combined)"},
                {"label": "Electric motors", "value": "2 Electric motors, front and rear "},
                {"label": "Power", "value": "360 kW / 489 hp"},
                {"label": "Battery", "value": "400V lithium-ion battery, 111 kWh capacity, 17 modules"},
                {"label": "0 - 100 km/h", "value": "5.0 sec"},
                {"label": "Torque", "value": "840 Nm"},
            ],
            "features": [
                {"displayType": "color", "title": "Space"},
                {"displayType": "rims", "title": '20" Aero'},
                {"displayType": "engine", "title": "Long range Dual motor"},
                {"displayType": "package", "title": "Pilot"},
                {"displayType": "package", "title": "Plus"},
                {"displayType": "option", "title": "Home charging cable"},
                {"displayType": "extra", "title": "Fully electrically retractable towbar"},
            ],
            "modelYear": "2025",
            "pno34": "359EAPP0E24671700RCG000      00000001162001226XPLUSS",
            "structureWeek": "202425",
        },
        "orderStatus": {"status": {"deliveryStage": "DELIVERED"}},
    },
    "placedAt": "2024-05-01T00:00:00Z",
    "type": "fleet",
}


def test_poms_order_maps_legacy_vdms_strings():
    order = PomsOrder.from_dict(ORDER)
    assert order is not None
    assert order.vin == "YSMTESTVIN0000001"
    assert order.country_code == "AU"
    assert order.delivery_stage == "DELIVERED"
    cfg = order.configuration
    assert cfg.model_year == 2025
    assert cfg.structure_week == "202425"
    assert cfg.motor_name == "Long range Dual motor"
    assert cfg.packages == ["Pilot", "Plus"]
    assert cfg.options == ["Home charging cable", "Fully electrically retractable towbar"]
    assert cfg.battery == "400V lithium-ion battery, 111 kWh capacity, 17 modules"
    assert cfg.battery_spec.capacity_kwh == 111
    assert cfg.total_kw == "360 kW"
    assert cfg.total_hp == "489 hp"
    assert cfg.torque == "840 Nm"
    assert cfg.spec("0 - 100 km/h") == "5.0 sec"
    assert cfg.electric_motors == "2 Electric motors, front and rear"


def test_poms_order_tolerates_missing_blocks():
    order = PomsOrder.from_dict({"orderId": "x", "car": None, "orderV2": None})
    assert order.vin is None
    assert order.configuration is None
