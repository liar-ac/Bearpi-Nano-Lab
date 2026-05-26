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
        "请基于实际数据回答问题,如果数据中没有相关信息请如实说明。"
        "回答要简洁实用,数据驱动,适合嵌入式实验室场景。"
        "如果用户问的是某个具体设备,请在回答中包含该设备的槽位、状态和关键传感器数据。"
    ),
}

DEBUG_FALLBACK_REPLY = (
    "AI云服务暂不可用,当前无法完成智能分析。\n\n"
    "请检查以下几点:\n"
    "1. backend/.env 中 XIAOMI_MIMO_API_KEY 是否已配置\n"
    "2. XIAOMI_MIMO_MODEL 模型名称是否正确\n"
    "3. XIAOMI_MIMO_API_URL 网络是否可达\n"
    "4. 后端控制台日志中的具体错误信息\n\n"
    "当前为开发演示模式(DEBUG=true, AI_ENABLE_DEBUG_FALLBACK=true),"
    "已返回此兜底提示代替502错误页。"
)


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
            parts.append(
                f"- {s.get('name', '?')}: {s.get('value', '?')}{s.get('unit', '')} "
                f"(阈值: {s.get('min', '无')}~{s.get('max', '无')})"
            )

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
        parts.append(
            f"- {r.get('deviceName', '?')}/{r.get('name', '?')} ({r.get('code', '?')}): "
            f"min={r.get('min', '无')} max={r.get('max', '无')} 单位={r.get('unit', '')}"
        )

    if device_stats:
        parts.append("\n## 传感器历史统计(最近7天)")
        for ds in device_stats:
            parts.append(
                f"- {ds.get('deviceName', '?')}/{ds.get('sensorName', '?')} ({ds.get('code', '?')}): "
                f"均值={ds.get('avg', '?')} 最小={ds.get('min', '?')} 最大={ds.get('max', '?')} "
                f"越界次数={ds.get('breachCount', 0)}"
            )

    return "\n".join(parts)


CONTEXT_BUILDERS = {
    "alarm_diagnosis": build_alarm_context,
    "data_analysis": build_data_analysis_context,
    "rule_suggestion": build_rule_suggestion_context,
}


def gather_lab_context():
    now = timezone.now()
    cutoff = now - timedelta(seconds=settings.DEVICE_ACTIVE_TTL_SECONDS)
    parts = []

    devices = list(
        Device.objects.select_related("cloud").prefetch_related("sensors").order_by("slot_no")
    )
    if devices:
        online = sum(1 for d in devices if d.status == "online")
        warning = sum(1 for d in devices if d.status == "warning")
        offline = sum(1 for d in devices if d.status == "offline")
        parts.append(
            f"## 实验室概况\n"
            f"- 总设备数: {len(devices)}\n"
            f"- 在线: {online}, 异常: {warning}, 离线: {offline}"
        )

        device_lines = []
        for d in devices[:40]:
            active = "活跃" if d.last_seen and d.last_seen >= cutoff else "不活跃"
            sensors = []
            for s in d.sensors.all():
                if s.latest_value is not None:
                    sensors.append(f"{s.name}={s.latest_value}{s.unit}")
            sensor_str = ", ".join(sensors[:6]) if sensors else "无数据"
            device_lines.append(
                f"- 槽位{d.slot_no} {d.sn} [{d.status}/{active}] "
                f"成员={d.member} 位置={d.location} "
                f"传感器: {sensor_str}"
            )
        parts.append("## 设备列表(前40台)\n" + "\n".join(device_lines))

    recent_alarms = list(
        Alarm.objects.select_related("device").order_by("-ts")[:10]
    )
    if recent_alarms:
        alarm_lines = [
            f"- [{a.level}] {a.device.sn}: {a.message} ({a.ts.strftime('%m-%d %H:%M')})"
            for a in recent_alarms
        ]
        parts.append("## 最近告警(前10条)\n" + "\n".join(alarm_lines))

    rules = list(
        Sensor.objects.select_related("device")
        .filter(code__in=["temp", "hum", "light", "voltage", "current", "power"])
        .exclude(min_value__isnull=True, max_value__isnull=True)
        .order_by("device__slot_no")[:30]
    )
    if rules:
        rule_lines = [
            f"- {r.device.sn}/{r.name}: min={r.min_value} max={r.max_value} 当前={r.latest_value}{r.unit}"
            for r in rules
        ]
        parts.append("## 阈值规则\n" + "\n".join(rule_lines))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------

def normalize_mimo_anthropic_url(raw_url):
    """Normalize MiMo Anthropic-compatible base URL to a full /v1/messages endpoint.

    Accepted inputs:
      - token-plan-cn.xiaomimimo.com
      - https://token-plan-cn.xiaomimimo.com
      - https://token-plan-cn.xiaomimimo.com/anthropic
      - https://token-plan-cn.xiaomimimo.com/anthropic/v1/messages
      - https://api.xiaomimimo.com/anthropic
    """
    if not raw_url or not raw_url.strip():
        return ""

    url = raw_url.strip()

    # Auto-add https:// if missing
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    # Remove trailing slash
    url = url.rstrip("/")

    # Already has /v1/messages — leave as-is
    if url.endswith("/v1/messages"):
        return url

    # Has /anthropic but not /v1/messages — append
    if url.endswith("/anthropic"):
        return url + "/v1/messages"

    # Has neither /anthropic nor /v1/messages — append both
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


# ---------------------------------------------------------------------------
# MiMo API call
# ---------------------------------------------------------------------------

def call_mimo_api(full_url, api_key, model, timeout, system_prompt, user_message):
    """Call MiMo Anthropic-compatible Messages API.

    full_url should already be normalized via normalize_mimo_anthropic_url().
    """
    payload = json.dumps({
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_message},
                ],
            }
        ],
        "stream": False,
        "temperature": 0.7,
    }).encode("utf-8")

    req = urllib.request.Request(
        full_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
            "x-api-key": api_key,
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            resp_status = resp.status
            return resp_status, body, None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        resp_status = exc.code
        error_summary = body[:300]
        try:
            error_data = json.loads(body)
            error_summary = (
                error_data.get("error", {}).get("message", "")
                or error_data.get("detail", "")
                or error_data.get("message", "")
                or body[:300]
            )
        except (ValueError, TypeError, KeyError, AttributeError):
            pass
        return resp_status, body, error_summary
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
    # Anthropic format: content[{type:"text", text:"..."}]
    if isinstance(data.get("content"), list):
        reply = "".join(
            block.get("text", "")
            for block in data["content"]
            if block.get("type") == "text"
        )
    # Anthropic flat string
    elif isinstance(data.get("content"), str):
        reply = data["content"]
    # OpenAI-compatible format: choices[0].message.content
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


def call_ai_api(system_prompt, user_message):
    api_key = settings.XIAOMI_MIMO_API_KEY
    raw_url = settings.XIAOMI_MIMO_API_URL
    model = settings.XIAOMI_MIMO_MODEL
    timeout = settings.XIAOMI_MIMO_TIMEOUT
    url_host = _api_url_host(raw_url)

    if not api_key or api_key == "your-api-key-here":
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
        logger.error("AI API timeout (%ss) to %s: %s", timeout, full_url, exc)
        if _debug_fallback_enabled():
            return Response({"reply": DEBUG_FALLBACK_REPLY, "error": "AI服务超时"})
        return Response(
            {"error": f"AI服务请求超时({timeout}秒)，请检查网络或增大XIAOMI_MIMO_TIMEOUT", "reply": ""},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except ConnectionError as exc:
        logger.error("AI API connection failed to %s: %s", full_url, exc)
        if _debug_fallback_enabled():
            return Response({"reply": DEBUG_FALLBACK_REPLY, "error": "AI服务连接失败"})
        return Response(
            {"error": f"AI服务连接失败({url_host})：{exc}。请检查XIAOMI_MIMO_API_URL和网络连通性", "reply": ""},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:
        logger.error("AI API unexpected error: %s", exc, exc_info=True)
        if _debug_fallback_enabled():
            return Response({"reply": DEBUG_FALLBACK_REPLY, "error": "AI服务请求异常"})
        return Response(
            {"error": f"AI服务请求异常：{exc}", "reply": ""},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if resp_status != 200:
        logger.error(
            "AI upstream HTTP %d, url=%s, model=%s, key=%s: %s",
            resp_status, full_url, model, _mask_key(api_key),
            (upstream_error or body[:200]),
        )
        if _debug_fallback_enabled():
            return Response({"reply": DEBUG_FALLBACK_REPLY, "error": f"AI服务返回HTTP {resp_status}"})

        error_msg = f"AI服务返回错误(HTTP {resp_status})"
        if upstream_error:
            error_msg += f"：{upstream_error[:120]}"
        if resp_status == 401:
            error_msg = "AI服务认证失败，请检查XIAOMI_MIMO_API_KEY是否正确"
        elif resp_status == 403:
            error_msg = "AI服务拒绝访问，请检查APIKey权限"
        elif resp_status == 404:
            error_msg = f"AI服务接口不存在(404)，请求地址：{full_url}"
        elif resp_status == 429:
            error_msg = "AI服务请求频率超限，请稍后重试"
        elif resp_status >= 500:
            error_msg = f"AI服务内部错误(HTTP {resp_status})，请稍后重试"

        return Response(
            {"error": error_msg, "reply": ""},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    reply = parse_ai_reply(body)
    if not reply:
        logger.warning("AI API returned 200 but empty reply from %s, body: %s", full_url, body[:300])
        if _debug_fallback_enabled():
            return Response({"reply": DEBUG_FALLBACK_REPLY, "error": "AI服务返回空内容"})
        return Response(
            {"error": "AI服务返回内容为空，请检查模型名称是否正确", "reply": ""},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response({"reply": reply})


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class AiHealthView(APIView):
    permission_classes = []

    def get(self, request):
        api_key = settings.XIAOMI_MIMO_API_KEY
        raw_url = settings.XIAOMI_MIMO_API_URL
        configured = bool(api_key and api_key != "your-api-key-here")
        return Response({
            "configured": configured,
            "model": settings.XIAOMI_MIMO_MODEL,
            "provider": "xiaomi-mimo",
            "url_host": _api_url_host(raw_url),
            "normalized_url": normalize_mimo_anthropic_url(raw_url) if configured else "",
            "debug_fallback": _debug_fallback_enabled(),
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

        system_prompt = SYSTEM_PROMPTS[feature]
        builder = CONTEXT_BUILDERS[feature]
        user_message = builder(context)

        result = call_ai_api(system_prompt, user_message)
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
