"""KML export (lat/long placemarks). Legacy equivalent: MainForm's KML export path.

No simplekml dependency -- KML is just XML, hand-built here.
"""

from xml.sax.saxutils import escape

from app.db.models.result import Result

_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
    "<Document>\n"
)
_FOOTER = "</Document>\n</kml>\n"


def write_kml(results: list[Result], output_path: str, *, columns: list[str] | None = None) -> str:
    # `columns` is accepted (not used) purely so every format shares one call
    # signature in workers.tasks._EXPORT_WRITERS. KML has one fixed shape --
    # name/description/coordinates -- there is no tabular column set to narrow.
    del columns
    placemarks = [_placemark(result) for result in results if _has_coords(result)]

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(_HEADER)
        fh.write("\n".join(placemarks))
        fh.write("\n" if placemarks else "")
        fh.write(_FOOTER)
    return output_path


def _has_coords(result: Result) -> bool:
    return result.latitude is not None and result.longitude is not None


def _placemark(result: Result) -> str:
    name = escape(result.name or "")
    description = escape(result.address or "")
    # KML coordinate order is lon,lat[,alt] -- easy to get backwards.
    coordinates = f"{result.longitude},{result.latitude},0"
    return (
        "  <Placemark>\n"
        f"    <name>{name}</name>\n"
        f"    <description>{description}</description>\n"
        "    <Point>\n"
        f"      <coordinates>{coordinates}</coordinates>\n"
        "    </Point>\n"
        "  </Placemark>"
    )
