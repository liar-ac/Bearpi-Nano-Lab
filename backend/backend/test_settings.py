"""Minimal settings for automated tests."""
from datetime import timedelta
import os

os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEVICE_TOKEN_SECRET", "test-device-token-secret")
from .settings import *  # noqa: F401,F403

SECRET_KEY = "test-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "bearpi-lab-test-cache",
        "TIMEOUT": 1,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ()  # noqa: F405
# 视图级ScopedRateThrottle仍会查找scope速率，置空会抛ImproperlyConfigured，改为超高速率
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    scope: "10000/min" for scope in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]  # noqa: F405
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

DEVICE_INGEST_TOKEN = "test-token"
DEVICE_TOKEN_SECRET = "test-device-token-secret"
DEVICE_ACTIVE_TTL_SECONDS = 45
DEVICE_BULK_SYNC_DELAY_MS = 5000
DEVICE_BULK_SYNC_PER_DEVICE_MS = 50
DEVICE_BULK_SYNC_MAX_DELAY_MS = 30000
TRUST_PROXY_HEADERS = False
REALTIME_GROUP_NAME = "realtime"

XIAOMI_MIMO_API_URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
XIAOMI_MIMO_API_KEY = "test-ai-key"
XIAOMI_MIMO_MODEL = "mimo-v2.5-pro"
XIAOMI_MIMO_TIMEOUT = 30
AI_ENABLE_DEBUG_FALLBACK = False
RAWPOINT_RETENTION_DAYS = 7
