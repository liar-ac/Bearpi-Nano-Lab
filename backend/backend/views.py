from django.conf import settings
from django.http import JsonResponse
from django.http.response import HttpResponse

_INDEX_HTML_CACHE = None


def health(request):
    return JsonResponse({"status": "ok"})


def frontend_index(request):
    global _INDEX_HTML_CACHE
    if _INDEX_HTML_CACHE is None:
        index_file = settings.FRONTEND_DIST_DIR / "index.html"
        if not index_file.exists():
            return JsonResponse(
                {
                    "detail": "frontend build not found. run `npm run build` in the frontend directory."
                },
                status=503,
            )
        _INDEX_HTML_CACHE = index_file.read_text(encoding="utf-8")
    return HttpResponse(_INDEX_HTML_CACHE, content_type="text/html; charset=utf-8")
