import json
import logging
import socket
import urllib.error
import urllib.request
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import resolve_role
from apps.alarms.models import Alarm
from apps.devices.models import Device, Sensor

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    "alarm_diagnosis": (
        "你是小熊派Nano实验室的AI运维助手,专门分析IoT设备告警。"
        "请用中文回答,格式清晰。分析告警时请给出:\n"
        "1. 可能原因(按可能性排序)\n"
        "2. 建议处理措施\n"
        "3. 紧急程度(低/中/高/紧急)\n"
        "4. 是否影响其他设备\n"
        "回答要简洁实用,适合嵌入式实验室场景。"
    ),
    "data_analysis": (
        "你是小熊派Nano实验室的AI数据分析助手,专门分析IoT传感器数据。"
        "请用中文回答,格式清晰。分析数据时请给出:\n"
        "1. 数据趋势总结\n"
        "2. 异常点识别\n"
        "3. 与正常范围的对比\n"
        "4. 操作建议\n"
        "回答要简洁实用,数据驱动。"
    ),
    "rule_suggestion": (
        "你是小熊派Nano实验室的AI配置助手,专门根据传感器历史数据推荐阈值规则。"
        "请用中文回答,格式清晰。推荐规则时请给出:\n"
        "1. 推荐的min/max阈值\n"
        "2. 推荐理由(基于数据分布)\n"
        "3. 调整幅度评估(保守/适中/激进)\n"
        "4. 可能的副作用\n"
        "回答要简洁实用,基于数据统计。"
    ),
    "data_query": (
        "你是小熊派Nano实验室的AI智能助手,可以回答关于实验室设备、传感器数据、告警、规则等任何问题。"
        "你会收到用户的自然语言问题和当前实验室的实时数据上下文。"
        "请根据上下文中的实际数据回答问题,不要编造不存在的设备或传感器数值。"
        "如果用户的问题涉及设备数据但上下文中没有相关数据,如实说明即可。"
        "如果用户的问题与设备数据无关(比如闲聊、通用问题),直接正常回答,不需要提及设备状态。"
        "回答简洁实用。"
    ),
}


def build_alarm_context(context):
    alarm = context.get("alarm", {})
    device = context.get("device", {})
    recent_sensors = context.get("recent_sensors", [])
    parts = [
        "## 告警信息",
        f"- 设备: {device.get('sn', '未知')} (槽位{device.get('slotNo', '?')})",
        f"- 状态: {device.get('status', '未知')}",
        f"- 告警级别: {alarm.get('level', '未知')}",
        f"- 告警消息: {alarm.get('message', '无')}",
        f"- 告警时间: {alarm.get('ts', '未知')}",
        f"- 异常原因: {device.get('abnormalReason', '无')}",
    ]
    if recent_sensors:
        parts.append("\n## 传感器最新数据")
        for s in recent_sensors:
            parts.append(f"- {s.get('name', '?')}: {s.get('value', '?')}{s.get('unit', '')} (阈值: {s.get('min', '无')}~{s.get('max', '无')})")
    return "\n".join(parts)


def build_data_analysis_context(context):
    device = context.get("device", {})
    sensor = context.get("sensor", {})
    stats = context.get("stats", {})
    points = context.get("points", [])
    parts = [
        "## 设备信息",
        f"- 设备: {device.get('sn', '未知')} (槽位{device.get('slotNo', '?')})",
        f"- 传感器: {sensor.get('name', '?')} ({sensor.get('code', '?')})",
        f"- 单位: {sensor.get('unit', '')}",
        f"- 阈值范围: {sensor.get('min', '无')}~{sensor.get('max', '无')}",
    ]
    if stats:
        parts.append("\n## 统计数据")
        parts.append(f"- 数据点数: {stats.get('count', 0)}")
        parts.append(f"- 最小值: {stats.get('min', '?')}")
        parts.append(f"- 最大值: {stats.get('max', '?')}")
        parts.append(f"- 平均值: {stats.get('average', '?')}")
        parts.append(f"- 累计电量: {stats.get('energy', '?')}Wh")
    if points:
        parts.append(f"\n## 最近{len(points)}个数据点(时间,值)")
        for p in points[-20:]:
            parts.append(f"- {p.get('ts', '?')}: {p.get('value', '?')}")
    return "\n".join(parts)


def build_rule_suggestion_context(context):
    rules = context.get("rules", [])
    device_stats = context.get("device_stats", [])
    parts = ["## 当前规则配置"]
    for r in rules:
        parts.append(f"- {r.get('deviceName', '?')}/{r.get('name', '?')} ({r.get('code', '?')}): min={r.get('min', '无')} max={r.get('max', '无')} 单位={r.get('unit', '')}")
    if device_stats:
        parts.append("\n## 传感器历史统计(最近7天)")
        for ds in device_stats:
            parts.append(f"- {ds.get('deviceName', '?')}/{ds.get('sensorName', '?')} ({ds.get('code', '?')}): 均值={ds.get('avg', '?')} 最小={ds.get('min', '?')} 最大={ds.get('max', '?')} 越界次数={ds.get('breachCount', 0)}")
    return "\n".join(parts)


CONTEXT_BUILDERS = {
    "alarm_diagnosis": build_alarm_context,
    "data_analysis": build_data_analysis_context,
    "rule_suggestion": build_rule_suggestion_context,
}


def _detect_data_source():
    """Detect whether current device data comes from live boards or demo seed."""
    from apps.telemetry.models import RawPoint
    devices = Device.objects.all()
    if not devices.count():
        return "empty"
    # If any device has recent raw points within last 2 minutes, it's live
    recent_cutoff = timezone.now() - timedelta(seconds=120)
    has_live = RawPoint.objects.filter(ts__gte=recent_cutoff).exists()
    if has_live:
        return "live"
    return "demo"


def gather_lab_context():
    now = timezone.now()
    cutoff = now - timedelta(seconds=settings.DEVICE_ACTIVE_TTL_SECONDS)
    data_source = _detect_data_source()

    parts = []
    if data_source == "demo":
        parts.append("## 数据来源说明\n- 当前数据来自演示/历史数据库记录,并非实时开发板上报")
    elif data_source == "empty":
        parts.append("## 数据来源说明\n- 当前没有任何设备接入,数据库为空")

    devices = list(Device.objects.select_related("cloud").prefetch_related("sensors").order_by("slot_no"))
    if devices:
        online = sum(1 for d in devices if d.status == "online")
        warning = sum(1 for d in devices if d.status == "warning")
        offline = sum(1 for d in devices if d.status == "offline")
        parts.append(f"## 实验室概况\n- 总设备数: {len(devices)}\n- 在线: {online}, 异常: {warning}, 离线: {offline}")
    else:
        parts.append("## 实验室概况\n- 当前没有任何设备接入,数据库为空,无设备数据可查")
        device_lines = []
        for d in devices[:40]:
            active = "活跃" if d.last_seen and d.last_seen >= cutoff else "不活跃"
            sensors = []
            for s in d.sensors.all():
                if s.latest_value is not None:
                    sensors.append(f"{s.name}={s.latest_value}{s.unit}")
            sensor_str = ", ".join(sensors[:6]) if sensors else "无数据"
            device_lines.append(f"- 槽位{d.slot_no} {d.sn} [{d.status}/{active}] 成员={d.member} 位置={d.location} 传感器: {sensor_str}")
        parts.append("## 设备列表(前40台)\n" + "\n".join(device_lines))
    recent_alarms = list(Alarm.objects.select_related("device").order_by("-ts")[:10])
    if recent_alarms:
        alarm_lines = [f"- [{a.level}] {a.device.sn}: {a.message} ({a.ts.strftime('%m-%d %H:%M')})" for a in recent_alarms]
        parts.append("## 最近告警(前10条)\n" + "\n".join(alarm_lines))
    rules = list(Sensor.objects.select_related("device").filter(code__in=["temp", "hum", "light", "voltage", "current", "power"]).exclude(min_value__isnull=True, max_value__isnull=True).order_by("device__slot_no")[:30])
    if rules:
        rule_lines = [f"- {r.device.sn}/{r.name}: min={r.min_value} max={r.max_value} 当前={r.latest_value}{r.unit}" for r in rules]
        parts.append("## 阈值规则\n" + "\n".join(rule_lines))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------

def normalize_mimo_anthropic_url(raw_url):
    """Normalize MiMo Anthropic-compatible base URL to a full /v1/messages endpoint."""
    if not raw_url or not raw_url.strip():
        return ""
    url = raw_url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    url = url.rstrip("/")
    if url.endswith("/v1/messages"):
        return url
    if url.endswith("/anthropic"):
        return url + "/v1/messages"
    return url + "/anthropic/v1/messages"


def _api_url_host(raw_url):
    try:
        return urlparse(raw_url).hostname or ""
    except Exception:
        return ""


def _mask_key(key):
    if not key or len(key) < 12:
        return "***"
    return key[:4] + "****" + key[-4:]


def _build_diagnostic(upstream_status, normalized_url, model, reason):
    return {
        "upstream_status": upstream_status,
        "normalized_url": normalized_url,
        "url_host": _api_url_host(normalized_url),
        "model": model,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# MiMo API call
# ---------------------------------------------------------------------------

def call_mimo_api(full_url, api_key, model, timeout, system_prompt, user_message):
    """Call MiMo Anthropic-compatible Messages API. Returns (status, body, error_summary)."""
    payload = json.dumps({
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [{"role": "user", "content": [{"type": "text", "text": user_message}]}],
        "stream": False,
        "temperature": 1.0,
        "top_p": 0.95,
        "thinking": {"type": "disabled"},
    }).encode("utf-8")

    req = urllib.request.Request(
        full_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
            "x-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body, None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        error_summary = body[:500]
        try:
            error_data = json.loads(body)
            error_summary = (
                error_data.get("error", {}).get("message", "")
                or error_data.get("error", {}).get("type", "")
                or error_data.get("detail", "")
                or error_data.get("message", "")
                or body[:500]
            )
        except (ValueError, TypeError, KeyError, AttributeError):
            pass
        return exc.code, body, error_summary
    except urllib.error.URLError as exc:
        reason = str(exc.reason)
        if isinstance(exc.reason, socket.timeout):
            raise TimeoutError("连接超时")
        raise ConnectionError(reason)
    except socket.timeout:
        raise TimeoutError("请求超时")


def parse_ai_reply(body):
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return body[:2000]
    reply = ""
    if isinstance(data.get("content"), list):
        reply = "".join(block.get("text", "") for block in data["content"] if block.get("type") == "text")
    elif isinstance(data.get("content"), str):
        reply = data["content"]
    elif isinstance(data.get("choices"), list) and data["choices"]:
        choice = data["choices"][0]
        if isinstance(choice.get("message"), dict):
            reply = choice["message"].get("content", "")
        elif isinstance(choice.get("text"), str):
            reply = choice["text"]
    if not reply:
        reply = json.dumps(data, ensure_ascii=False)[:2000]
    return reply


def _debug_fallback_enabled():
    return settings.DEBUG and getattr(settings, "AI_ENABLE_DEBUG_FALLBACK", False)


def _fallback_response(error_msg, diagnostic):
    """Return a 200 with fallback reply + diagnostic for dev mode."""
    return Response({
        "reply": (
            "AI云服务暂不可用，当前无法完成智能分析。\n\n"
            "请检查后端控制台日志获取详细错误信息。"
        ),
        "error": error_msg,
        "diagnostic": diagnostic,
    })


def call_ai_api(system_prompt, user_message):
    api_key = settings.XIAOMI_MIMO_API_KEY
    raw_url = settings.XIAOMI_MIMO_API_URL
    model = settings.XIAOMI_MIMO_MODEL
    timeout = settings.XIAOMI_MIMO_TIMEOUT

    if not api_key or api_key in ("your-api-key-here", "your-token-plan-api-key-here"):
        logger.warning("AI API key not configured (XIAOMI_MIMO_API_KEY)")
        return Response(
            {"error": "AI服务未配置APIKey，请在backend/.env中配置XIAOMI_MIMO_API_KEY", "reply": ""},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    full_url = normalize_mimo_anthropic_url(raw_url)
    if not full_url:
        return Response(
            {"error": "AI服务URL未配置，请在backend/.env中配置XIAOMI_MIMO_API_URL", "reply": ""},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        resp_status, body, upstream_error = call_mimo_api(
            full_url, api_key, model, timeout, system_prompt, user_message
        )
    except TimeoutError as exc:
        logger.error("AI upstream timeout (%ss), url=%s: %s", timeout, full_url, exc)
        diag = _build_diagnostic(0, full_url, model, f"请求超时({timeout}秒)")
        if _debug_fallback_enabled():
            return _fallback_response("AI服务超时", diag)
        return Response({"error": f"AI服务请求超时({timeout}秒)，请检查网络或增大XIAOMI_MIMO_TIMEOUT", "reply": "", "diagnostic": diag}, status=status.HTTP_502_BAD_GATEWAY)
    except ConnectionError as exc:
        logger.error("AI upstream connection failed, url=%s: %s", full_url, exc)
        diag = _build_diagnostic(0, full_url, model, f"连接失败: {exc}")
        if _debug_fallback_enabled():
            return _fallback_response("AI服务连接失败", diag)
        return Response({"error": f"AI服务连接失败：{exc}", "reply": "", "diagnostic": diag}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception as exc:
        logger.error("AI upstream unexpected error: %s", exc, exc_info=True)
        diag = _build_diagnostic(0, full_url, model, f"异常: {exc}")
        if _debug_fallback_enabled():
            return _fallback_response("AI服务请求异常", diag)
        return Response({"error": f"AI服务请求异常：{exc}", "reply": "", "diagnostic": diag}, status=status.HTTP_502_BAD_GATEWAY)

    # --- Upstream returned HTTP status ---
    if resp_status != 200:
        error_summary = upstream_error or body[:300]
        logger.error("AI upstream HTTP %d, url=%s, model=%s, key=%s: %s", resp_status, full_url, model, _mask_key(api_key), error_summary[:200])

        reason = f"上游返回HTTP {resp_status}"
        if resp_status == 400:
            reason = f"请求体错误(400): {error_summary[:120]}"
        elif resp_status == 401:
            reason = "认证失败(401): APIKey可能过期或不属于当前网关"
        elif resp_status == 403:
            reason = "拒绝访问(403): APIKey权限不足"
        elif resp_status == 404:
            reason = f"接口不存在(404): 请检查normalized_url={full_url}"
        elif resp_status == 429:
            reason = "频率超限(429): 额度用尽或请求过快"
        elif resp_status >= 500:
            reason = f"上游服务错误({resp_status}): {error_summary[:100]}"

        diag = _build_diagnostic(resp_status, full_url, model, reason)

        if resp_status == 401:
            error_msg = "AI服务认证失败(401)，请检查XIAOMI_MIMO_API_KEY是否正确且未过期"
        elif resp_status == 403:
            error_msg = "AI服务拒绝访问(403)，请检查APIKey权限"
        elif resp_status == 404:
            error_msg = f"AI服务接口不存在(404)，请求地址：{full_url}"
        elif resp_status == 429:
            error_msg = "AI服务请求频率超限(429)，请稍后重试"
        elif resp_status >= 500:
            error_msg = f"AI服务内部错误(HTTP {resp_status})"
        else:
            error_msg = f"AI服务返回错误(HTTP {resp_status}): {error_summary[:120]}"

        if _debug_fallback_enabled():
            return _fallback_response(error_msg, diag)
        return Response({"error": error_msg, "reply": "", "diagnostic": diag}, status=status.HTTP_502_BAD_GATEWAY)

    # --- Parse success reply ---
    reply = parse_ai_reply(body)
    if not reply:
        logger.warning("AI upstream returned 200 but empty reply, url=%s, body=%s", full_url, body[:300])
        diag = _build_diagnostic(200, full_url, model, "返回内容为空，可能模型名称不正确")
        if _debug_fallback_enabled():
            return _fallback_response("AI服务返回空内容", diag)
        return Response({"error": "AI服务返回内容为空，请检查XIAOMI_MIMO_MODEL是否正确", "reply": "", "diagnostic": diag}, status=status.HTTP_502_BAD_GATEWAY)

    return Response({"reply": reply, "format": "markdown", "data_source": _detect_data_source()})


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class AiHealthView(APIView):
    permission_classes = []

    def get(self, request):
        api_key = settings.XIAOMI_MIMO_API_KEY
        raw_url = settings.XIAOMI_MIMO_API_URL
        configured = bool(api_key and api_key not in ("your-api-key-here", "your-token-plan-api-key-here"))
        return Response({
            "configured": configured,
            "provider": "xiaomi-mimo",
            "raw_url": raw_url,
            "normalized_url": normalize_mimo_anthropic_url(raw_url) if configured else "",
            "url_host": _api_url_host(raw_url),
            "model": settings.XIAOMI_MIMO_MODEL,
            "timeout": settings.XIAOMI_MIMO_TIMEOUT,
            "debug": settings.DEBUG,
            "debug_fallback": _debug_fallback_enabled(),
        })


class AiPingView(APIView):
    """Debug-only endpoint to test AI upstream connectivity."""
    def post(self, request):
        if not settings.DEBUG:
            return Response({"error": "仅在DEBUG模式下可用"}, status=status.HTTP_403_FORBIDDEN)

        api_key = settings.XIAOMI_MIMO_API_KEY
        raw_url = settings.XIAOMI_MIMO_API_URL
        model = settings.XIAOMI_MIMO_MODEL
        timeout = settings.XIAOMI_MIMO_TIMEOUT

        if not api_key or api_key in ("your-api-key-here", "your-token-plan-api-key-here"):
            return Response({"ok": False, "error": "XIAOMI_MIMO_API_KEY未配置"})

        full_url = normalize_mimo_anthropic_url(raw_url)
        if not full_url:
            return Response({"ok": False, "error": "XIAOMI_MIMO_API_URL未配置"})

        try:
            resp_status, body, upstream_error = call_mimo_api(
                full_url, api_key, model, timeout,
                "你是一个测试助手。",
                "ping，请只回复pong",
            )
        except TimeoutError as exc:
            return Response({
                "ok": False,
                "upstream_status": 0,
                "normalized_url": full_url,
                "model": model,
                "error_summary": f"超时: {exc}",
                "raw_response_preview": "",
            })
        except ConnectionError as exc:
            return Response({
                "ok": False,
                "upstream_status": 0,
                "normalized_url": full_url,
                "model": model,
                "error_summary": f"连接失败: {exc}",
                "raw_response_preview": "",
            })
        except Exception as exc:
            return Response({
                "ok": False,
                "upstream_status": 0,
                "normalized_url": full_url,
                "model": model,
                "error_summary": f"异常: {exc}",
                "raw_response_preview": "",
            })

        preview = body[:500] if body else ""
        ok = resp_status == 200
        if ok:
            reply = parse_ai_reply(body)
            if reply:
                preview = reply[:500]

        return Response({
            "ok": ok,
            "upstream_status": resp_status,
            "normalized_url": full_url,
            "model": model,
            "error_summary": upstream_error[:200] if upstream_error else "",
            "raw_response_preview": preview,
        })


class AiChatView(APIView):
    def post(self, request):
        role = resolve_role(request.user)
        if role not in ("admin", "experimenter"):
            raise PermissionDenied("仅管理员和实验员可使用AI分析功能")
        feature = request.data.get("feature")
        if feature not in SYSTEM_PROMPTS:
            raise ValidationError({"feature": f"不支持的AI功能: {feature}"})
        context = request.data.get("context")
        if not isinstance(context, dict) or not context:
            raise ValidationError({"context": "缺少分析上下文"})
        result = call_ai_api(SYSTEM_PROMPTS[feature], CONTEXT_BUILDERS[feature](context))
        if isinstance(result, Response) and result.status_code != 200:
            return result
        result.data["feature"] = feature
        return result


class AiQueryView(APIView):
    def post(self, request):
        role = resolve_role(request.user)
        if role not in ("admin", "experimenter", "viewer"):
            raise PermissionDenied("登录后即可使用AI问答")
        question = request.data.get("question", "").strip()
        if not question:
            raise ValidationError({"question": "请输入问题"})
        if len(question) > 500:
            raise ValidationError({"question": "问题长度不能超过500字"})
        lab_context = gather_lab_context()
        user_message = f"## 用户问题\n{question}\n\n{lab_context}"
        result = call_ai_api(SYSTEM_PROMPTS["data_query"], user_message)
        if isinstance(result, Response) and result.status_code != 200:
            return result
        result.data["question"] = question
        return result
