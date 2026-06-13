from datetime import timedelta
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def csv_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


load_local_env(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-bearpi-nano-lab-dev")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"


def _detect_local_ip():
    """Auto-detect the LAN IP address of this machine."""
    import socket as _socket
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("10.0.0.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LOCAL_IP = os.getenv("LOCAL_IP", "") or _detect_local_ip()


# 生产环境必须替换默认SECRET_KEY
if not DEBUG and SECRET_KEY.startswith("django-insecure"):
    raise SystemExit(
        "FATAL: DJANGO_SECRET_KEY is still the default insecure value. "
        "Set a real secret in backend/.env before running in production."
    )
ALLOWED_HOSTS = csv_env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
if DEBUG:
    # Auto-inject detected LAN IP
    if LOCAL_IP and LOCAL_IP not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(LOCAL_IP)
    for host in (
        "10.212.180.213",
        "10.211.2.200",
        "10.211.141.163",
        "10.211.39.29",
        "10.211.110.10",
        "10.190.212.175",
        "192.168.137.1",
        "192.168.43.1",
        "192.168.1.1",
    ):
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)
if DEBUG and os.getenv("DJANGO_DEBUG_ALLOW_ANY_HOSTS", "false").lower() == "true":
    # 本地热点调试需要时显式打开，避免生产环境误放开 Host。
    ALLOWED_HOSTS.append("*")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "channels",
    "apps.accounts",
    "apps.devices",
    "apps.telemetry",
    "apps.alarms",
    "apps.cloud",
    "apps.audit",
    "apps.ai",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIST_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"
ASGI_APPLICATION = "backend.asgi.application"

_db_engine = os.getenv("DB_ENGINE", "sqlite")

if _db_engine == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("MYSQL_DATABASE", "bearpi_lab"),
            "USER": os.getenv("MYSQL_USER", "root"),
            "PASSWORD": os.getenv("MYSQL_PASSWORD", "password"),
            "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.getenv("MYSQL_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
                "connect_timeout": 5,
                "read_timeout": 10,
                "write_timeout": 10,
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "bearpi-lab-cache",
        "TIMEOUT": 30,
    }
}

CORS_ALLOWED_ORIGINS = csv_env(
    "CORS_ALLOWED_ORIGINS",
    ",".join(
        [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
            "http://10.212.180.213:5173",
            "http://10.212.180.213:5174",
            "http://10.212.180.213:8000",
            "http://10.211.2.200:5173",
            "http://10.211.2.200:8000",
            "http://10.211.141.163:5173",
            "http://10.211.141.163:5174",
            "http://10.211.141.163:8000",
            "http://10.190.212.175:5173",
            "http://10.190.212.175:5174",
            "http://10.190.212.175:8000",
            "http://10.211.39.29:5173",
            "http://10.211.39.29:8000",
            "http://10.211.110.10:5173",
            "http://10.211.110.10:5174",
            "http://10.211.110.10:8000",
            "http://192.168.137.1:5173",
            "http://192.168.137.1:8000",
        ]
    )
    if DEBUG
    else "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174",
)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://127\.0\.0\.1:517[0-9]$",
    r"^http://localhost:517[0-9]$",
    r"^http://192\.168\.\d+\.\d+:(517[0-9]|8000)$",
    r"^http://10\.\d+\.\d+\.\d+:5173$",
] if DEBUG else []
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = csv_env(
    "CSRF_TRUSTED_ORIGINS",
    "http://10.212.180.213:8000,http://10.212.180.213:5173,http://10.212.180.213:5174,http://10.211.2.200:8000,http://10.211.2.200:5173,http://10.211.141.163:8000,http://10.211.141.163:5173,http://10.211.141.163:5174,http://10.211.39.29:8000,http://10.211.39.29:5173,http://10.211.110.10:8000,http://10.211.110.10:5173,http://10.211.110.10:5174,http://10.190.212.175:8000,http://10.190.212.175:5173,http://10.190.212.175:5174,http://192.168.137.1:8000,http://192.168.137.1:5173"
    if DEBUG
    else "http://127.0.0.1:8000,http://localhost:8000",
)
# Auto-inject detected LAN IP into CORS and CSRF
if DEBUG and LOCAL_IP and LOCAL_IP not in ("127.0.0.1", ""):
    for _port in ("5173", "5174", "8000"):
        _origin = f"http://{LOCAL_IP}:{_port}"
        if _origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(_origin)
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": os.getenv("THROTTLE_AUTH_LOGIN", "5/min"),
        "auth_register": os.getenv("THROTTLE_AUTH_REGISTER", "3/min"),
        "auth_refresh": os.getenv("THROTTLE_AUTH_REFRESH", "30/min"),
        "telemetry_ingest": os.getenv("THROTTLE_TELEMETRY_INGEST", "120/min"),
        "device_commands": os.getenv("THROTTLE_DEVICE_COMMANDS", "60/min"),
        "ai_chat": os.getenv("THROTTLE_AI_CHAT", "10/min"),
        "ai_query": os.getenv("THROTTLE_AI_QUERY", "20/min"),
        "ai_command": os.getenv("THROTTLE_AI_COMMAND", "20/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

HUAWEI_IOTDA_ENDPOINT = os.getenv("HUAWEI_IOTDA_ENDPOINT", "")
HUAWEI_IOTDA_PROJECT_ID = os.getenv("HUAWEI_IOTDA_PROJECT_ID", "")
DEVICE_INGEST_TOKEN = os.getenv("DEVICE_INGEST_TOKEN", "")
DEVICE_TOKEN_SECRET = os.getenv("DEVICE_TOKEN_SECRET", "")
DEVICE_ACTIVE_TTL_SECONDS = int(os.getenv("DEVICE_ACTIVE_TTL_SECONDS", "45"))
DEVICE_BULK_SYNC_DELAY_MS = int(os.getenv("DEVICE_BULK_SYNC_DELAY_MS", "5000"))
DEVICE_BULK_SYNC_PER_DEVICE_MS = int(os.getenv("DEVICE_BULK_SYNC_PER_DEVICE_MS", "50"))
DEVICE_BULK_SYNC_MAX_DELAY_MS = int(os.getenv("DEVICE_BULK_SYNC_MAX_DELAY_MS", "30000"))
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"
REALTIME_GROUP_NAME = os.getenv("REALTIME_GROUP_NAME", "realtime")

# AI 分析服务配置（小米 MiMo API, Anthropic 兼容格式）
# 必须在 .env 中配置 XIAOMI_MIMO_API_KEY 才能使用 AI 功能
XIAOMI_MIMO_API_URL = os.getenv("XIAOMI_MIMO_API_URL", "https://token-plan-cn.xiaomimimo.com/anthropic")
XIAOMI_MIMO_API_KEY = os.getenv("XIAOMI_MIMO_API_KEY", "")
XIAOMI_MIMO_MODEL = os.getenv("XIAOMI_MIMO_MODEL", "mimo-v2.5-pro")
XIAOMI_MIMO_TIMEOUT = int(os.getenv("XIAOMI_MIMO_TIMEOUT", "30"))
AI_ENABLE_DEBUG_FALLBACK = os.getenv("AI_ENABLE_DEBUG_FALLBACK", "false").lower() == "true"

# 时序数据保留天数，超过此天数的原始采样点会被清理
RAWPOINT_RETENTION_DAYS = int(os.getenv("RAWPOINT_RETENTION_DAYS", "7"))

# 生产环境兜底警告：仍在使用默认弱凭据时给出明确告警
if not DEBUG:
    import warnings
    if SECRET_KEY.startswith("django-insecure"):
        warnings.warn("DJANGO_SECRET_KEY 仍是默认开发用key，生产环境必须替换。", RuntimeWarning)
    if not DEVICE_TOKEN_SECRET:
        warnings.warn("DEVICE_TOKEN_SECRET 未配置，无法启用每板独立上报 token。", RuntimeWarning)
    if DEVICE_INGEST_TOKEN in {"", "bearpi-dev-token"}:
        warnings.warn("DEVICE_INGEST_TOKEN 未配置或仍是默认值，旧全局 token 通道不可作为生产凭据。", RuntimeWarning)
    if "*" in ALLOWED_HOSTS:
        warnings.warn("ALLOWED_HOSTS 包含 '*'，生产环境必须收紧。", RuntimeWarning)
    for _name in ("DJANGO_ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS"):
        if not os.getenv(_name):
            warnings.warn(f"{_name} 未显式配置，生产环境默认仅允许本机 127.0.0.1/localhost 来源，请在 .env 中按部署地址配置。", RuntimeWarning)
