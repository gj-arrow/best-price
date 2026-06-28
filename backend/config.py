import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/scraper")
SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "30"))
