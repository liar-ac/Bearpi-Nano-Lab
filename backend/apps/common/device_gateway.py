import hashlib
import hmac
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import ValidationError

from apps.cloud.models import CloudDeviceStatus
from apps.devices.models import Device
from apps.devices.models import Sensor

logger = logging.getLogger(__name__)


KNOWN_BOARD_PROFILES = {
    "A001": {
        "sn": "BEARPI-NANO-A001",
        "slot_no": 1,
        "firmware_version": "v1.3.2",
        "member": "成员A",
        "sample_rate": 1,
    },
    "A002": {
        "sn": "BEARPI-NANO-A002",
        "slot_no": 2,
        "firmware_version": "v1.3.2",
        "member": "成员B",
        "sample_rate": 1,
    },
    "A003": {
        "sn": "BEARPI-NANO-A003",
        "slot_no": 3,
        "firmware_version": "v1.3.2",
        "member": "成员C",
        "sample_rate": 1,
    },
    "A004": {
        "sn": "BEARPI-NANO-A004",
        "slot_no": 4,
        "firmware_version": "v1.3.2",
        "member": "成员D",
        "sample_rate": 1,
    },
}
KNOWN_BOARD_OWNER = "嵌入式+前端+后端+APP联合组"


IA1_SENSOR_TEMPLATES = {
    "temp": {
        "name": "温度",
        "unit": "℃",
        "description": "IA1 环境温度",
        "min_value": 18,
        "max_value": 32,
    },
    "hum": {
        "name": "湿度",
        "unit": "%",
        "description": "IA1 环境湿度",
        "min_value": 25,
        "max_value": 75,
    },
    "light": {
        "name": "光照强度",
        "unit": "lx",
        "description": "IA1 环境光照强度",
        "min_value": 20,
        "max_value": 1200,
    },
    "motor": {
        "name": "通风电机",
        "unit": "",
        "description": "IA1 通风电机状态，0=关闭，1=开启",
        "min_value": 0,
        "max_value": 1,
    },
    "fill_light": {
        "name": "补光灯",
        "unit": "",
        "description": "IA1 补光灯状态，0=关闭，1=开启",
        "min_value": 0,
        "max_value": 1,
    },
    "voltage": {
        "name": "工作电压",
        "unit": "V",
        "description": "开发板工作电压",
        "min_value": 4.75,
        "max_value": 5.25,
    },
    "current": {
        "name": "工作电流",
        "unit": "mA",
        "description": "开发板工作电流，优先使用ADC采样值，未配置采样时使用估算值",
        "min_value": 0,
        "max_value": 500,
    },
    "power": {
        "name": "功耗",
        "unit": "mW",
        "description": "开发板瞬时功耗，优先由实测电压/电流计算，未配置采样时使用估算值",
        "min_value": 0,
        "max_value": 2500,
    },
    "voltage_sampled": {
        "name": "电压采样来源",
        "unit": "",
        "description": "0=估算，1=ADC采样",
        "min_value": 0,
        "max_value": 1,
    },
    "current_sampled": {
        "name": "电流采样来源",
        "unit": "",
        "description": "0=估算，1=ADC采样",
        "min_value": 0,
        "max_value": 1,
    },
    "power_sampled": {
        "name": "功耗采样来源",
        "unit": "",
        "description": "0=估算，1=由ADC电流采样参与计算",
        "min_value": 0,
        "max_value": 1,
    },
    "power_mcu": {
        "name": "主控功耗",
        "unit": "mW",
        "description": "主控芯片功耗，整板实测时按估算比例分摊",
        "min_value": 0,
        "max_value": 800,
    },
    "power_wifi": {
        "name": "WiFi功耗",
        "unit": "mW",
        "description": "WiFi通信模块功耗，整板实测时按估算比例分摊",
        "min_value": 0,
        "max_value": 1000,
    },
    "power_sensor": {
        "name": "传感器功耗",
        "unit": "mW",
        "description": "E53_IA1传感器板功耗，整板实测时按估算比例分摊",
        "min_value": 0,
        "max_value": 500,
    },
    "power_motor": {
        "name": "电机功耗",
        "unit": "mW",
        "description": "通风电机功耗，整板实测时按估算比例分摊",
        "min_value": 0,
        "max_value": 1500,
    },
    "power_light": {
        "name": "补光灯功耗",
        "unit": "mW",
        "description": "补光灯功耗，整板实测时按估算比例分摊",
        "min_value": 0,
        "max_value": 500,
    },
}


def device_token_for_identifier(identifier):
    secret = getattr(settings, "DEVICE_TOKEN_SECRET", "")
    if not secret or not identifier:
        return ""
    normalized = str(identifier).strip().upper()
    if not normalized:
        return ""
    return hmac.HMAC(
        secret.encode("utf-8"),
        f"bearpi-device:{normalized}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _token_candidates_from_data(data):
    candidates = []
    if data:
        candidates.extend(candidate_device_sns(data))
        for key in ("sn", "node_id", "cloud_device_id", "device_id"):
            value = data.get(key)
            if value:
                candidates.append(str(value))

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        key = str(candidate).strip().upper()
        if not key or key in seen:
            continue
        seen.add(key)
        unique_candidates.append(candidate)
    return unique_candidates


def valid_device_token(request, data=None, device=None):
    candidate = request.headers.get("X-Device-Token", "")
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("device "):
        candidate = auth.split(" ", 1)[1].strip()
    if not candidate:
        return False

    identifiers = []
    if device is not None:
        identifiers.extend([device.sn, device.cloud_twin_id])
        cloud = getattr(device, "cloud", None)
        if cloud is not None:
            identifiers.extend([cloud.node_id, cloud.cloud_device_id])
    identifiers.extend(_token_candidates_from_data(data or {}))

    for identifier in identifiers:
        expected = device_token_for_identifier(identifier)
        if expected and constant_time_compare(candidate, expected):
            return True

    legacy_expected = getattr(settings, "DEVICE_INGEST_TOKEN", "")
    return bool(
        legacy_expected
        and legacy_expected != "bearpi-dev-token"
        and constant_time_compare(candidate, legacy_expected)
    )


def board_code_from_identifier(value):
    if value is None:
        return None
    identifier = str(value).strip().upper()
    if not identifier:
        return None
    for code in KNOWN_BOARD_PROFILES:
        if code in identifier:
            return code
    # 只对看起来像板卡SN的标识符使用尾部数字匹配（包含BEARPI或NANO关键字）
    upper = identifier.upper()
    if "BEARPI" in upper or "NANO" in upper:
        trailing_number = "".join(character for character in identifier[-4:] if character.isdigit())
        if trailing_number in {"001", "1"}:
            return "A001"
        if trailing_number in {"002", "2"}:
            return "A002"
        if trailing_number in {"003", "3"}:
            return "A003"
        if trailing_number in {"004", "4"}:
            return "A004"
    return None


def board_profile_from_data(data):
    for key in ("sn", "node_id", "cloud_device_id", "device_id"):
        code = board_code_from_identifier(data.get(key))
        if code:
            return KNOWN_BOARD_PROFILES[code]
    return None


def candidate_device_sns(data):
    raw_sn = data.get("sn") or data.get("node_id")
    candidates = []
    if raw_sn:
        candidates.append(str(raw_sn))
    profile = board_profile_from_data(data)
    if profile:
        candidates.append(profile["sn"])

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        key = candidate.upper()
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(candidate)
    return unique_candidates


def resolve_device(data):
    cloud_device_id = data.get("cloud_device_id") or data.get("device_id")

    for sn in candidate_device_sns(data):
        device = Device.objects.filter(sn=sn).first()
        if device:
            return device
        device = Device.objects.filter(cloud__node_id=sn).first()
        if device:
            return device

    if cloud_device_id:
        device = Device.objects.filter(cloud_twin_id=cloud_device_id).first()
        if device:
            return device
        device = Device.objects.filter(cloud__cloud_device_id=cloud_device_id).first()
        if device:
            return device

    raise ValidationError({"device": "device not found by sn, node_id, cloud_device_id, or device_id"})


def resolve_or_register_device(data, sensor_codes=None):
    try:
        device = resolve_device(data)
        sync_known_board_profile(device, data)
        ensure_device_sensors(device, sensor_codes or [])
        return device
    except ValidationError:
        profile = board_profile_from_data(data)
        sn = data.get("sn") or data.get("node_id") or ((profile or {}).get("sn"))
        if not sn:
            raise

    sn_value = profile["sn"] if profile else str(sn)
    for _ in range(5):
        try:
            with transaction.atomic():
                existing = Device.objects.select_for_update().filter(sn=sn_value).first()
                if existing:
                    device = existing
                    break
                slot_no = profile.get("slot_no") if profile else None
                if slot_no:
                    move_conflicting_device_from_slot(slot_no)
                else:
                    slot_no = next_slot_no_locked()
                device = Device.objects.create(
                    slot_no=slot_no,
                    sn=sn_value,
                    lab_id="lab-embedded-01",
                    model="BearPi-HM Nano",
                    firmware_version=str(
                        data.get("firmware_version")
                        or data.get("firmware")
                        or (profile or {}).get("firmware_version")
                        or "unknown"
                    ),
                    location=f"实验台{slot_no}/后端HTTP接入组" if profile else f"自动接入槽位{slot_no}",
                    owner=KNOWN_BOARD_OWNER if profile else "小熊派Nano实验室",
                    member=str(
                        (profile or {}).get("member")
                        or data.get("member")
                        or data.get("owner")
                        or "未分配"
                    ),
                    status=Device.Status.ONLINE,
                    last_seen=timezone.now(),
                    ip_address=data.get("ip_address"),
                    cloud_twin_id=str(data.get("cloud_device_id") or data.get("device_id") or ""),
                    sample_rate=int(data.get("sample_rate") or (profile or {}).get("sample_rate") or 1),
                )
                CloudDeviceStatus.objects.create(
                    device=device,
                    platform="Self-hosted IoT Gateway",
                    product_id="self-hosted-bearpi-lab",
                    cloud_device_id=device.cloud_twin_id or device.sn,
                    node_id=device.sn,
                    mqtt_status=CloudDeviceStatus.MqttStatus.UNKNOWN,
                    rule_engine=CloudDeviceStatus.RuleEngine.ENABLED,
                    sync_status=CloudDeviceStatus.SyncStatus.UNBOUND,
                )
                break
        except IntegrityError:
            # 并发竞争同一个 slot_no 时重试
            continue
    else:
        raise ValidationError({"device": "concurrent registration failed, please retry"})

    sync_known_board_profile(device, data)
    ensure_device_sensors(device, sensor_codes or [])
    return device


def sync_known_board_profile(device, data=None):
    data = data or {}
    profile = board_profile_from_data(data)
    if profile is None:
        code = board_code_from_identifier(device.sn)
        profile = KNOWN_BOARD_PROFILES.get(code)
    if profile is None:
        return device

    preferred_slot_no = profile.get("slot_no")
    if preferred_slot_no:
        with transaction.atomic():
            locked_device = Device.objects.select_for_update().get(pk=device.pk)
            move_conflicting_device_from_slot(preferred_slot_no, current_device=locked_device)
            if locked_device.slot_no != preferred_slot_no:
                locked_device.slot_no = preferred_slot_no
                locked_device.location = default_known_board_location(preferred_slot_no)
                locked_device.save(update_fields=["slot_no", "location"])
            device.refresh_from_db()

    updates = {
        "sn": profile["sn"],
        "lab_id": "lab-embedded-01",
        "model": "BearPi-HM Nano",
        "firmware_version": str(data.get("firmware_version") or data.get("firmware") or profile["firmware_version"]),
        "location": default_known_board_location(device.slot_no),
        "owner": KNOWN_BOARD_OWNER,
        "member": profile["member"],
        "sample_rate": int(data.get("sample_rate") or profile["sample_rate"]),
    }
    cloud_twin_id = data.get("cloud_device_id") or data.get("device_id")
    if cloud_twin_id:
        updates["cloud_twin_id"] = str(cloud_twin_id)
    if data.get("ip_address"):
        updates["ip_address"] = data.get("ip_address")

    changed_fields = []
    for field, value in updates.items():
        if getattr(device, field) == value:
            continue
        setattr(device, field, value)
        changed_fields.append(field)
    if changed_fields:
        try:
            device.save(update_fields=changed_fields)
        except IntegrityError:
            logger.warning("sync_known_board_profile: IntegrityError saving %s, skipping SN update", device.sn)
            changed_fields = [f for f in changed_fields if f != 'sn']
            if changed_fields:
                device.save(update_fields=changed_fields)

    cloud, _ = CloudDeviceStatus.objects.get_or_create(
        device=device,
        defaults={
            "platform": "Self-hosted IoT Gateway",
            "product_id": "self-hosted-bearpi-lab",
            "cloud_device_id": device.cloud_twin_id or device.sn,
            "node_id": device.sn,
            "mqtt_status": CloudDeviceStatus.MqttStatus.UNKNOWN,
            "rule_engine": CloudDeviceStatus.RuleEngine.ENABLED,
            "sync_status": CloudDeviceStatus.SyncStatus.UNBOUND,
        },
    )
    cloud_updates = {
        "node_id": device.sn,
        "cloud_device_id": device.cloud_twin_id or device.sn,
    }
    cloud_changed_fields = []
    for field, value in cloud_updates.items():
        if getattr(cloud, field) == value:
            continue
        setattr(cloud, field, value)
        cloud_changed_fields.append(field)
    if cloud_changed_fields:
        cloud.save(update_fields=cloud_changed_fields)

    return device


def ensure_device_sensors(device, sensor_codes):
    codes = {str(code) for code in sensor_codes if code}
    codes.update({
        "temp",
        "hum",
        "light",
        "motor",
        "fill_light",
        "voltage",
        "current",
        "power",
        "voltage_sampled",
        "current_sampled",
        "power_sampled",
        "power_mcu",
        "power_wifi",
        "power_sensor",
        "power_motor",
        "power_light",
    })
    for code in sorted(codes):
        if code in IA1_SENSOR_TEMPLATES:
            # 使用 get_or_create 而非 update_or_create，避免每次遥测ingest重置用户设置的阈值
            Sensor.objects.get_or_create(device=device, code=code, defaults=IA1_SENSOR_TEMPLATES[code])
            continue

        Sensor.objects.get_or_create(
            device=device,
            code=code,
            defaults={
                "name": code,
                "unit": "",
                "description": f"自动发现指标 {code}",
                "min_value": None,
                "max_value": None,
            },
        )


def default_known_board_location(slot_no):
    return f"实验台{slot_no}/后端HTTP接入组"


def move_conflicting_device_from_slot(slot_no, current_device=None):
    conflict = Device.objects.select_for_update().filter(slot_no=slot_no).first()
    if conflict is None:
        return
    if current_device is not None and conflict.pk == current_device.pk:
        return

    next_slot = next_unreserved_slot_no_locked()
    conflict.slot_no = next_slot
    conflict.location = default_known_board_location(next_slot)
    conflict.save(update_fields=["slot_no", "location"])


def reserved_known_slot_nos():
    return {
        int(profile["slot_no"])
        for profile in KNOWN_BOARD_PROFILES.values()
        if profile.get("slot_no")
    }


def next_unreserved_slot_no_locked():
    used = set(
        Device.objects.select_for_update().values_list("slot_no", flat=True)
    )
    reserved = reserved_known_slot_nos()
    for slot_no in range(1, 121):
        if slot_no not in used and slot_no not in reserved:
            return slot_no
    max_slot = Device.objects.aggregate(value=Max("slot_no"))["value"] or 0
    return max_slot + 1


def next_slot_no_locked():
    """事务内拿 slot_no，配合 select_for_update 在 transaction.atomic 调用"""
    used = set(
        Device.objects.select_for_update().values_list("slot_no", flat=True)
    )
    for slot_no in range(1, 121):
        if slot_no not in used:
            return slot_no
    max_slot = Device.objects.aggregate(value=Max("slot_no"))["value"] or 0
    return max_slot + 1
