from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from backend.views import frontend_index, health

urlpatterns = [
    path("health", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.devices.urls")),
    path("api/v1/", include("apps.telemetry.urls")),
    path("api/v1/", include("apps.alarms.urls")),
    path("api/v1/", include("apps.audit.urls")),
    re_path(
        r"^assets/(?P<path>.*)$",
        serve,
        {"document_root": str(settings.FRONTEND_DIST_DIR / "assets")},
    ),
    path("", frontend_index, name="frontend-root"),
    re_path(r"^(?!api/|admin/|health$|assets/|ws/).*$", frontend_index, name="frontend-spa"),
]
