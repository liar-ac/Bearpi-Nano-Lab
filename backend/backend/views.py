from django.conf import settings
from django.http import JsonResponse
from django.http.response import HttpResponse

_INDEX_HTML_CACHE = None
_INDEX_HTML_MTIME = 0.0


def health(request):
    return JsonResponse({"status": "ok"})


def frontend_index(request):
    global _INDEX_HTML_CACHE, _INDEX_HTML_MTIME
    index_file = settings.FRONTEND_DIST_DIR / "index.html"
    if not index_file.exists():
        return JsonResponse(
            {
                "detail": "frontend build not found. run `npm run build` in the frontend directory."
            },
            status=503,
        )
    mtime = index_file.stat().st_mtime
    if _INDEX_HTML_CACHE is None or mtime != _INDEX_HTML_MTIME:
        _INDEX_HTML_CACHE = index_file.read_text(encoding="utf-8")
        _INDEX_HTML_MTIME = mtime
    return HttpResponse(_INDEX_HTML_CACHE, content_type="text/html; charset=utf-8")
