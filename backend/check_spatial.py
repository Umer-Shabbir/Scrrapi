from app.api.deps import get_geo_db
from app.db.models.geo import City, ZipCode


def main():
    db_gen = get_geo_db()
    db = next(db_gen)
    print("Cities with lat:", db.query(City).filter(City.latitude.isnot(None)).count())
    print("Zips with lat:", db.query(ZipCode).filter(ZipCode.latitude.isnot(None)).count())

main()
