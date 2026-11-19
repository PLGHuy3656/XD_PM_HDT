import csv
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


METRICS = (
    ("temperature", "Temperature", "°C"),
    ("humidity", "Humidity", "%"),
    ("co2", "CO2", "ppm"),
    ("lux", "Illuminance", "lux"),
    ("audio_rms", "Audio RMS", ""),
)

_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe_cell(value):
    """Neutralize spreadsheet formula injection on string cells without altering numeric values."""
    if value is None or isinstance(value, (int, float)):
        return value
    text = str(value)
    if text and text[0] in _CSV_FORMULA_PREFIXES:
        return f"'{text}"
    return text


def telemetry_csv(analytics: dict) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "section",
            "metric",
            "timestamp",
            "samples",
            "average",
            "minimum",
            "maximum",
        ],
    )
    for metric, label, unit in METRICS:
        stats = analytics["summary"][metric]
        writer.writerow(
            [
                "summary",
                _csv_safe_cell(f"{label} ({unit})" if unit else label),
                "",
                analytics["sample_count"],
                _csv_safe_cell(stats["average"]),
                _csv_safe_cell(stats["minimum"]),
                _csv_safe_cell(stats["maximum"]),
            ],
        )
    for point in analytics["series"]:
        for metric, label, unit in METRICS:
            stats = point[metric]
            writer.writerow(
                [
                    "series",
                    _csv_safe_cell(f"{label} ({unit})" if unit else label),
                    _csv_safe_cell(point["timestamp"]),
                    point["samples"],
                    _csv_safe_cell(stats["average"]),
                    _csv_safe_cell(stats["minimum"]),
                    _csv_safe_cell(stats["maximum"]),
                ],
            )
    return output.getvalue().encode("utf-8-sig")


def telemetry_pdf(analytics: dict) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("SwiftletCare Environmental Analytics Report", styles["Title"]),
        Spacer(1, 5 * mm),
        Paragraph(
            (
                f"Period: {escape(str(analytics['period']))} | "
                f"From: {escape(str(analytics['start']))} | "
                f"To: {escape(str(analytics['end']))}"
            ),
            styles["BodyText"],
        ),
        Paragraph(
            (
                f"Authorized devices: {int(analytics['device_count'])} | "
                f"Telemetry samples: {int(analytics['sample_count'])}"
            ),
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
    ]

    summary_rows = [["Metric", "Average", "Minimum", "Maximum"]]
    for metric, label, unit in METRICS:
        stats = analytics["summary"][metric]
        summary_rows.append(
            [
                f"{label} ({unit})" if unit else label,
                _format_number(stats["average"]),
                _format_number(stats["minimum"]),
                _format_number(stats["maximum"]),
            ],
        )
    story.extend(
        [
            Paragraph("Summary", styles["Heading2"]),
            _styled_table(summary_rows),
            Spacer(1, 5 * mm),
        ],
    )

    series_rows = [["Timestamp", "Samples", "Metric", "Average", "Min", "Max"]]
    for point in analytics["series"]:
        for metric, label, unit in METRICS:
            stats = point[metric]
            series_rows.append(
                [
                    str(point["timestamp"]),
                    str(point["samples"]),
                    f"{label} ({unit})" if unit else label,
                    _format_number(stats["average"]),
                    _format_number(stats["minimum"]),
                    _format_number(stats["maximum"]),
                ],
            )
    story.extend(
        [
            Paragraph("Time series", styles["Heading2"]),
            _styled_table(series_rows, repeat_rows=1),
        ],
    )
    document.build(story)
    return output.getvalue()


def _format_number(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}".rstrip("0").rstrip(".")


def _styled_table(
    rows: list[list[str]],
    repeat_rows: int = 0,
) -> Table:
    table = Table(rows, repeatRows=repeat_rows)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8d8d8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f2f5f7")],
                ),
            ],
        ),
    )
    return table
