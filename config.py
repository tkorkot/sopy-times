import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = "sqlite:///sopy.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
