from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from common.constants import DATA_PATH

DB_PATH = DATA_PATH / f"gamedata.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
