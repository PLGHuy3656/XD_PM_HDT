from app.alerting import _anomaly_check, _threshold_checks


def test_threshold_checks_use_control_config_for_temperature_humidity_and_co2():
    checks = _threshold_checks(
        (
            "node-01",
            None,
            38.0,
            50.0,
            1200.0,
            100.0,
            25.0,
            2.0,
            60.0,
            5.0,
            1000.0,
        ),
    )

    assert checks == {
        "temperature": (38.0, 27.0, "above"),
        "humidity": (50.0, 55.0, "below"),
        "co2": (1200.0, 1000.0, "above"),
    }


def test_anomaly_detection_needs_30_samples_and_exceeds_three_mad():
    assert _anomaly_check("temperature", 40.0, (29, 25.0, 1.0)) is None
    assert _anomaly_check("temperature", 28.0, (30, 25.0, 1.0)) is None

    check = _anomaly_check("temperature", 28.1, (30, 25.0, 1.0))

    assert check is not None
    assert check[1] == 28.0
    assert check[2] == "above"
    assert check[3]["method"] == "rolling_median_mad"


def test_zero_mad_flags_only_a_different_value():
    assert _anomaly_check("humidity", 50.0, (30, 50.0, 0.0)) is None
    assert _anomaly_check("humidity", 50.1, (30, 50.0, 0.0))[2] == "above"
