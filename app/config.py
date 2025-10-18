import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["CLIENT_ID"]
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:53682/callback")
API_BASE = "https://api.viessmann-climatesolutions.com"
IAM_BASE = "https://iam.viessmann-climatesolutions.com/idp/v2"
AUTH_URL = f"{IAM_BASE}/authorize"
TOKEN_URL = f"{IAM_BASE}/token"
SCOPES = "IoT User offline_access"

# feste IDs, wenn bekannt
GATEWAY_SERIAL = os.environ.get("GATEWAY_SERIAL")
DEVICE_ID = os.environ.get("DEVICE_ID")

# DB
DATABASE_URL = os.environ.get("DATABASE_URL", "mysql+pymysql://root:root@db:3306/vito")
