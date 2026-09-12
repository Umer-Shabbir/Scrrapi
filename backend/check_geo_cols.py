from sqlalchemy import create_engine, text

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.geo_db_url)
with engine.connect() as conn:
    print([r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='zip_code'")).fetchall()])
    print([r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='city'")).fetchall()])
