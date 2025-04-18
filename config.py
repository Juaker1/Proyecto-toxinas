import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev_key")

class Config:
    SECRET_KEY = SECRET_KEY
