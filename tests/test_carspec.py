from polestar_api.models.carspec import CarFeatures, CarSpecifications

SPECS = {
    "requestId": "r",
    "specifications": [
        {
            "key": "power",
            "label": "Power",
            "value": "360 kW / 489 hp",
            "specificationValues": [
                {"key": "power-in-kilowatt", "numeric": {"value": 360, "formatted": "360", "unitKey": "kw", "unit": "kW"}},
                {"key": "power-in-horsepower", "numeric": {"value": 489, "formatted": "489", "unitKey": "hp", "unit": "hp"}},
            ],
        },
        {
            "key": "battery",
            "label": "Battery",
            "value": "111 kWh",
            "specificationValues": [
                {"key": "battery-capacity-in-kilowatt-hour", "numeric": {"value": 111}},
                {"key": "battery-module-count", "numeric": {"value": 17}},
                {"key": "battery-potential-in-volt", "numeric": {"value": 400}},
            ],
        },
        {
            "key": "driveline",
            "label": "Driveline",
            "value": "All-wheel drive",
            "specificationValues": [{"key": "driveline", "text": {"key": "awd", "content": "All-wheel drive"}}],
        },
    ],
}

FEATURES = {
    "name": "Polestar 3",
    "carFeatures": [
        {"pnoId": {"type": "Engine", "code": "EA"}, "featureCategoryId": "c1", "title": "Long range Dual motor"},
        {"pnoId": {"type": "Options", "code": "001162"}, "featureCategoryId": "c2", "title": "Pilot"},
        {"pnoId": {"type": "Options", "code": "XPLUSS"}, "featureCategoryId": "c2", "title": "Plus"},
        {"pnoId": {"type": "Standard", "code": "R101"}, "featureCategoryId": "c3", "title": '20" Aero'},
    ],
    "carFeatureCategories": [{"id": "c2", "title": "Packages", "key": "packages"}],
}


def test_specifications_numeric_and_text():
    spec = CarSpecifications.from_dict(SPECS)
    assert spec.power_kw == 360
    assert spec.power_hp == 489
    assert spec.battery_capacity_kwh == 111
    assert spec.battery_module_count == 17
    assert spec.battery_voltage == 400
    assert spec.driveline == "All-wheel drive"
    assert spec.driveline_key == "awd"
    assert spec.text("power") == "360 kW / 489 hp"
    assert spec.torque_nm is None


def test_features_motor_and_packages():
    feats = CarFeatures.from_dict(FEATURES)
    assert feats.name == "Polestar 3"
    assert feats.motor.title == "Long range Dual motor"
    assert feats.motor.code == "EA"
    assert feats.packages == ["Pilot", "Plus"]
    assert '20" Aero' in feats.titles
