import json
import logging

from django.conf import settings

from apps.audit.models import AuditLog


logger = logging.getLogger(__name__)


# audit metadata 字段写入上限（默认 8KB JSON），避免恶意/失控调用塞入超大对象
AUDIT_METADATA_MAX_BYTES = 8 * 1024


def _sanitize_metadata(metadata):
    if not isinstance(metadata, dict):
        return {}
    try:
        serialized = json.dumps(metadata, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return {"_serialize_error": "metadata not JSON-serializable"}
    if len(serialized.encode("utf-8")) <= AUDIT_METADATA_MAX_BYTES:
        return metadata
    # 超限：截断详情，保留 key 列表方便排查
    keys = list(metadata.keys())[:32]
    return {"_truncated": True, "_keys": keys, "_size": len(serialized)}


def record_audit(request, action, target, detail, metadata=None, actor_name=None):
    user = getattr(request, "user", None)
    is_authenticated = bool(user and user.is_authenticated)
    try:
        return AuditLog.objects.create(
            actor=user if is_authenticated else None,
            actor_name=(actor_name or (user.get_username() if is_authenticated else "device"))[:150],
            action=action,
            target=(target or "")[:160],
            detail=(detail or "")[:255],
            metadata=_sanitize_metadata(metadata),
            ip_address=client_ip(request),
        )
    except Exception:
        logger.exception("audit write failed: %s %s", action, target)
        return None


def client_ip(request):
    remote_addr = request.META.get("REMOTE_ADDR")
    trust_proxy = getattr(settings, "TRUST_PROXY_HEADERS", False)
    if trust_proxy:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            # 取最左侧客户端 IP，再 fallback 到 REMOTE_ADDR
            return forwarded_for.split(",")[0].strip() or remote_addr
    return remote_addr
