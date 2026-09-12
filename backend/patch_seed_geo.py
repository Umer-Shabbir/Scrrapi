
path = "G:/Scrrapi/backend/scripts/seed_geo.py"
with open(path, encoding="utf-8") as f:
    text = f.read()

# For pass 1: add latitude and longitude when creating countries, regions, cities (if available - actually country/region/city lat/lon can just be null, but let's see places)
# Wait, for country/region/city we don't strictly need lat/lon, but maybe we do?
# Usually radius search is just over zip_code (where cities have them) or city (where they don't, aka "areas")
