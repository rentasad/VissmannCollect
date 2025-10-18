from sqlalchemy import create_engine, text
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

# row: Dict[str, Any] – nur vorhandene Spalten werden gesetzt
def insert_row(row: dict):
    cols = ", ".join(row.keys())
    params = ", ".join([f":{k}" for k in row.keys()])
    sql = text(f"INSERT INTO vitodata ({cols}) VALUES ({params})")
    with engine.begin() as conn:
        conn.execute(sql, row)
