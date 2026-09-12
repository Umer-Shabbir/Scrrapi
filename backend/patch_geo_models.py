
path = "G:/Scrrapi/backend/app/db/models/geo.py"
with open(path, encoding="utf-8") as f:
    text = f.read()

# Add latitude and longitude to City and ZipCode
if "latitude: Mapped[float" not in text:
    text = text.replace(
        "name: Mapped[str] = mapped_column(String(255), index=True)",
        "name: Mapped[str] = mapped_column(String(255), index=True)\n    latitude: Mapped[float | None] = mapped_column(index=True)\n    longitude: Mapped[float | None] = mapped_column(index=True)"
    )
    text = text.replace(
        "code: Mapped[str] = mapped_column(String(20), index=True)",
        "code: Mapped[str] = mapped_column(String(20), index=True)\n    latitude: Mapped[float | None] = mapped_column(index=True)\n    longitude: Mapped[float | None] = mapped_column(index=True)"
    )

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

