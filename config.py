import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
DATABASE_DIR = BASE_DIR / "database"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

class Settings:
    PROJECT_NAME = "Influencer Content Intelligence & Fact-Checking Platform"
    OUTPUT_DIR = OUTPUT_DIR
    DATABASE_DIR = DATABASE_DIR
    DATABASE_PATH = Path(os.getenv("DATABASE_PATH", DATABASE_DIR / "influencer_intel.db"))
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
    DEFAULT_BATCH_SIZE = int(os.getenv("DEFAULT_BATCH_SIZE", "100"))
    MAX_ANALYSIS_CHARS = int(os.getenv("MAX_ANALYSIS_CHARS", "12000"))
    SUPPORTED_FILE_EXTENSIONS = [".pdf", ".docx", ".txt", ".mp4", ".mov", ".avi", ".wav", ".mp3"]
    SUPPORTED_URL_TYPES = ["youtube.com", "youtu.be", "http://", "https://"]

settings = Settings()
