"""
In-Memory Mock Analytics Repository.

Provenance:
Preloaded with verified test fixtures directly matching frontend contract:
- frontend/src/components/features/farm-owner/analytics/analyticsMockData.js
- Standard edge-case scenarios (zero exits, missing sensor, baseline 0, camera outage)

Strict Separation:
Contains ONLY mock fixtures for Phase 2 API contract testing and offline development.
Zero connection to production databases or live NiFi pipelines.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.domain.enums import AlertSeverity, MetricType, PeriodEnum
from app.domain.models import BirdActivityBucket
from app.ports.analytics_repository import IAnalyticsRepository


class InMemoryAnalyticsRepository(IAnalyticsRepository):
    """
    Mock repository implementing IAnalyticsRepository using in-memory state.
    """

    def __init__(self):
        self._farms: Dict[str, Dict[str, Any]] = {
            "farm-binh-an": {
                "id": "farm-binh-an",
                "name": "Nhà yến Bình An",
                "zones": [
                    {"id": "zone-a", "name": "Khu vực A - Cửa chính"},
                    {"id": "zone-b", "name": "Khu vực B - Tầng 2"},
                    {"id": "zone-c", "name": "Khu vực C - Tầng 3"},
                ],
            },
            "farm-phu-an": {
                "id": "farm-phu-an",
                "name": "Nhà yến Phú An",
                "zones": [
                    {"id": "zone-a", "name": "Khu vực A - Tầng 1"},
                    {"id": "zone-d", "name": "Khu vực D - Tầng 2"},
                ],
            },
            "farm-zero-activity": {
                "id": "farm-zero-activity",
                "name": "Nhà yến Mới Xây (Zero Activity)",
                "zones": [{"id": "zone-z", "name": "Khu vực Thử nghiệm"}],
            },
            "farm-zero-exits": {
                "id": "farm-zero-exits",
                "name": "Nhà yến Trú Đông (Zero Exits)",
                "zones": [{"id": "zone-1", "name": "Khu vực Trú"}],
            },
            "farm-camera-down": {
                "id": "farm-camera-down",
                "name": "Nhà yến Mất Camera (Camera Outage)",
                "zones": [{"id": "zone-c1", "name": "Khu vực Cửa"}],
            },
        }

    async def get_farm_metadata(self, farm_id: str) -> Optional[Dict[str, Any]]:
        return self._farms.get(farm_id)

    async def get_bird_activity_buckets(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> Tuple[List[BirdActivityBucket], Optional[int], Dict[str, bool]]:
        dt_base = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)

        if farm_id == "farm-binh-an":
            # Matches analyticsMockData.js hourlyBirdActivity: sum entries=428, exits=391, prev=395
            buckets = [
                BirdActivityBucket(bucket_start=dt_base, label="05h", entries=184, exits=326),
                BirdActivityBucket(bucket_start=dt_base, label="07h", entries=142, exits=412),
                BirdActivityBucket(bucket_start=dt_base, label="09h", entries=206, exits=238),
                BirdActivityBucket(bucket_start=dt_base, label="11h", entries=231, exits=196),
                BirdActivityBucket(bucket_start=dt_base, label="13h", entries=258, exits=172),
                BirdActivityBucket(bucket_start=dt_base, label="15h", entries=284, exits=151),
                BirdActivityBucket(bucket_start=dt_base, label="17h", entries=391, exits=118),
                BirdActivityBucket(bucket_start=dt_base, label="19h", entries=428, exits=96),
                BirdActivityBucket(bucket_start=dt_base, label="21h", entries=317, exits=82),
            ]
            coverage = {b.label: True for b in buckets}
            return buckets, 2251, coverage

        if farm_id == "farm-phu-an":
            # Baseline = 0 (tests percentage change with zero baseline -> None)
            buckets = [
                BirdActivityBucket(bucket_start=dt_base, label="08h", entries=100, exits=90),
                BirdActivityBucket(bucket_start=dt_base, label="12h", entries=110, exits=105),
            ]
            coverage = {"08h": True, "12h": True}
            return buckets, 0, coverage

        if farm_id == "farm-zero-activity":
            # Zero activity
            buckets = [
                BirdActivityBucket(bucket_start=dt_base, label="10h", entries=0, exits=0),
            ]
            coverage = {"10h": True}
            return buckets, 0, coverage

        if farm_id == "farm-zero-exits":
            # 50 entries, 0 exits (tests return_rate == None when exits == 0)
            buckets = [
                BirdActivityBucket(bucket_start=dt_base, label="06h", entries=50, exits=0),
            ]
            coverage = {"06h": True}
            return buckets, None, coverage

        if farm_id == "farm-camera-down":
            # Outage: unobserved intervals
            buckets = []
            coverage = {"05h": False, "07h": False, "09h": False}
            return buckets, None, coverage

        # Default fallback for any newly added farm
        return [], None, {}

    async def get_zone_climate_averages(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> List[Dict[str, Any]]:
        if farm_id == "farm-binh-an":
            return [
                {
                    "zone_id": "zone-a",
                    "zone_name": "Khu vực A",
                    "avg_temperature": 28.8,
                    "avg_humidity": 86.0,
                    "avg_co2": 520.0,
                },
                {
                    "zone_id": "zone-b",
                    "zone_name": "Khu vực B",
                    "avg_temperature": 32.5,
                    "avg_humidity": 76.0,
                    "avg_co2": 650.0,
                },
                {
                    "zone_id": "zone-c",
                    "zone_name": "Khu vực C",
                    "avg_temperature": 29.5,
                    "avg_humidity": 84.0,
                    "avg_co2": 490.0,
                },
            ]

        if farm_id == "farm-phu-an":
            return [
                {
                    "zone_id": "zone-a",
                    "zone_name": "Khu vực A",
                    "avg_temperature": 29.0,
                    "avg_humidity": 85.0,
                    "avg_co2": None,  # Missing CO2
                },
                {
                    "zone_id": "zone-d",
                    "zone_name": "Khu vực D",
                    "avg_temperature": None,  # All missing
                    "avg_humidity": None,
                    "avg_co2": None,
                },
            ]

        if farm_id in ("farm-zero-activity", "farm-zero-exits"):
            return [
                {
                    "zone_id": "zone-z",
                    "zone_name": "Khu vực Thử nghiệm",
                    "avg_temperature": 29.0,
                    "avg_humidity": 85.0,
                    "avg_co2": 500.0,
                }
            ]

        if farm_id == "farm-camera-down":
            return [
                {
                    "zone_id": "zone-c1",
                    "zone_name": "Khu vực Cửa",
                    "avg_temperature": None,
                    "avg_humidity": None,
                    "avg_co2": None,
                }
            ]

        return []

    async def get_alerts(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> List[AlertSeverity]:
        if farm_id == "farm-binh-an":
            # Matches alertDistribution: 2 CRITICAL, 4 HIGH, 7 MEDIUM, 3 LOW
            return (
                [AlertSeverity.CRITICAL] * 2
                + [AlertSeverity.HIGH] * 4
                + [AlertSeverity.MEDIUM] * 7
                + [AlertSeverity.LOW] * 3
            )

        if farm_id == "farm-phu-an":
            return [AlertSeverity.LOW, AlertSeverity.MEDIUM]

        return []

    async def get_yield_data(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> Optional[Dict[str, Any]]:
        if farm_id == "farm-binh-an":
            # Matches analyticsMockData.js yieldSummary
            return {
                "total_nests": 1268,
                "harvested_nests": 184,
                "current_yield": 14.8,
                "previous_yield": 13.2,
            }

        # Other farms have no harvest data yet
        return None

    async def get_trends_data(
        self,
        farm_id: Optional[str],
        period: PeriodEnum,
        zone_id: Optional[str] = None,
        metric: Optional[MetricType] = None,
    ) -> Dict[str, Any]:
        # Matches analyticsMockData.js trends
        labels_hourly = ["05h", "07h", "09h", "11h", "13h", "15h", "17h", "19h", "21h"]
        labels_daily = ["10/10", "11/10", "12/10", "13/10", "14/10", "15/10", "16/10"]
        labels_yield = ["T5", "T6", "T7", "T8", "T9", "T10"]

        if farm_id == "farm-camera-down":
            # Outage simulated: all events are null
            return {
                "hourly_bird_activity": [{"label": lb, "entries": None, "exits": None} for lb in labels_hourly],
                "environment_comparison": [{"label": lb, "zones": {}} for lb in labels_hourly],
                "bird_trend_analytics": [{"label": lb, "entries": None, "exits": None} for lb in labels_daily],
                "alert_trend": [
                    {"label": lb, "critical": None, "high": None, "medium": None, "low": None} for lb in labels_daily
                ],
                "yield_trend": [],
                "has_data_gaps": True,
            }

        # Standard healthy trends matching mock UI
        hourly_activity = [
            {"label": "05h", "entries": 184, "exits": 326},
            {"label": "07h", "entries": 142, "exits": 412},
            {"label": "09h", "entries": 206, "exits": 238},
            {"label": "11h", "entries": 231, "exits": 196},
            {"label": "13h", "entries": 258, "exits": 172},
            {"label": "15h", "entries": 284, "exits": 151},
            {"label": "17h", "entries": 391, "exits": 118},
            {"label": "19h", "entries": 428, "exits": 96},
            {"label": "21h", "entries": 317, "exits": 82},
        ]

        env_comparison = [
            {
                "label": lb,
                "zones": {
                    "zone-a": {
                        "temperature": 28.5,
                        "humidity": 86.0,
                        "co2": 520.0,
                        "light": 15.0,
                        "audio": 42.0,
                    },
                    "zone-b": {
                        "temperature": 31.0,
                        "humidity": 80.0,
                        "co2": 580.0,
                        "light": 20.0,
                        "audio": 45.0,
                    },
                },
            }
            for lb in labels_hourly
        ]

        bird_trend = [
            {"label": "10/10", "entries": 380, "exits": 350},
            {"label": "11/10", "entries": 395, "exits": 365},
            {"label": "12/10", "entries": 410, "exits": 380},
            {"label": "13/10", "entries": 405, "exits": 375},
            {"label": "14/10", "entries": 420, "exits": 390},
            {"label": "15/10", "entries": 415, "exits": 385},
            {"label": "16/10", "entries": 428, "exits": 391},
        ]

        alert_trend = [
            {"label": "10/10", "critical": 0, "high": 1, "medium": 1, "low": 0},
            {"label": "11/10", "critical": 0, "high": 0, "medium": 2, "low": 1},
            {"label": "12/10", "critical": 1, "high": 0, "medium": 1, "low": 0},
            {"label": "13/10", "critical": 0, "high": 1, "medium": 0, "low": 1},
            {"label": "14/10", "critical": 1, "high": 0, "medium": 1, "low": 0},
            {"label": "15/10", "critical": 0, "high": 0, "medium": 1, "low": 0},
            {"label": "16/10", "critical": 0, "high": 0, "medium": 1, "low": 0},
        ]

        yield_trend = [
            {"label": "T5", "value": 10.4},
            {"label": "T6", "value": 11.2},
            {"label": "T7", "value": 12.6},
            {"label": "T8", "value": 12.1},
            {"label": "T9", "value": 13.2},
            {"label": "T10", "value": 14.8},
        ]

        return {
            "hourly_bird_activity": hourly_activity,
            "environment_comparison": env_comparison,
            "bird_trend_analytics": bird_trend,
            "alert_trend": alert_trend,
            "yield_trend": yield_trend,
            "has_data_gaps": False,
        }
