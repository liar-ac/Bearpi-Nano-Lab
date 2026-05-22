from django.conf import settings
from django.http import JsonResponse
from django.http.response import HttpResponse


def health(request):
    return JsonResponse({"status": "ok"})


def frontend_index(request):
    index_file = settings.FRONTEND_DIST_DIR / "index.html"
    if not index_file.exists():
        return JsonResponse(
            {
                "detail": "frontend build not found. run `npm run build` in the frontend directory."
            },
            status=503,
        )
    return HttpResponse(index_file.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")
