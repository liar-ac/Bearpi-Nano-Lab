"""
传感器历史接口的范围/校验测试。
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cloud.models import CloudDeviceStatus
from apps.devices.models import Device, Sensor
from apps.telemetry.models import RawPoint
from apps.telemetry.views import (
    EXECUTOR_SENSOR_CODES,
    MAX_HISTORY_RANGE,
    SensorHistoryView,
    TelemetryIngestView,
    parse_required_datetime,
    record_threshold_alarm,
)
from apps.alarms.models import Alarm


def _make_device(slot_no=1, sn=None):
    device = Device.objects.create(
        slot_no=slot_no,
        sn=sn or f"BEARPI-NANO-A{slot_no:03d}",
        lab_id="lab-test",
        model="BearPi-HM Nano",
        firmware_version="v-test",
        location="test",
        owner="test",
        member="tester",
        status=Device.Status.ONLINE,
        last_seen=timezone.now(),
    )
    CloudDeviceStatus.objects.create(
        device=device, platform="Test", product_id="t", cloud_device_id=device.sn, node_id=device.sn
    )
    return device


class HistoryRangeCapTests(TestCase):
    """覆盖 Bug #18：历史区间最大跨度 31 天"""

    def test_max_history_range_constant(self):
        self.assertEqual(MAX_HISTORY_RANGE, timedelta(days=31))

    def test_required_datetime_makes_naive_value_aware(self):
        parsed = parse_required_datetime("2026-05-17T10:00:00", "start")
        self.assertTrue(timezone.is_aware(parsed))


class HistoryInvalidCalendarDateTests(TestCase):
    """覆盖修复：格式合法但日期非法（如2月30日）的start/end返回400而非500"""

    def test_invalid_calendar_date_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            parse_required_datetime("2026-02-30T00:00:00", "start")

    def test_history_endpoint_invalid_calendar_date_returns_400(self):
        device = _make_device(9)
        sensor = Sensor.objects.create(
            device=device, code="temp", name="温度", unit="℃", min_value=18, max_value=32
        )
        user = User.objects.create_user(username="history-tester", password="x")
        request = APIRequestFactory().get(
            f"/api/v1/sensors/{sensor.id}/history",
            {"start": "2026-02-30T00:00:00", "end": "2026-03-01T00:00:00"},
        )
        force_authenticate(request, user=user)
        response = SensorHistoryView.as_view()(request, sensor_id=sensor.id)
        self.assertEqual(response.status_code, 400)


class ThresholdAlarmExecutorTests(TestCase):
    """覆盖 Bug #16：执行器代码不参与阈值告警"""

    def test_executor_codes_dont_trigger_alarm(self):
        device = _make_device()
        sensor = Sensor.objects.create(
            device=device, code="motor", name="电机", unit="", min_value=0, max_value=1
        )
        alarm = record_threshold_alarm(sensor, value=2.5, ts=timezone.now())
        self.assertIsNone(alarm)
        self.assertEqual(Alarm.objects.count(), 0)

    def test_regular_sensor_still_triggers(self):
        device = _make_device(2)
        sensor = Sensor.objects.create(
            device=device, code="temp", name="温度", unit="℃", min_value=18, max_value=32
        )
        alarm = record_threshold_alarm(sensor, value=40, ts=timezone.now())
        self.assertIsNotNone(alarm)
        self.assertEqual(alarm.level, Alarm.Level.WARNING)


class TelemetryIngestValidationTests(TestCase):
    """覆盖修复：非有限数值、非字典body、超长sensor_code在ingest入口被拒绝"""

    def _post(self, body):
        request = APIRequestFactory().post(
            "/api/v1/ingest/telemetry",
            body,
            format="json",
            HTTP_X_DEVICE_TOKEN=settings.DEVICE_INGEST_TOKEN,
        )
        return TelemetryIngestView.as_view()(request)

    def test_nan_value_rejected_and_nothing_persisted(self):
        response = self._post({"sn": "BEARPI-NANO-A001", "sensor_code": "temp", "value": "NaN"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(RawPoint.objects.count(), 0)
        self.assertEqual(Device.objects.count(), 0)

    def test_infinite_value_rejected_and_nothing_persisted(self):
        response = self._post({"sn": "BEARPI-NANO-A001", "sensor_code": "temp", "value": "Infinity"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(RawPoint.objects.count(), 0)

    def test_non_dict_body_returns_400(self):
        response = self._post([{"sensor_code": "temp", "value": 1.0}])
        self.assertEqual(response.status_code, 400)

    def test_sensor_code_longer_than_32_chars_rejected(self):
        long_code = "x" * 33
        response = self._post({"sn": "BEARPI-NANO-A001", "metrics": {long_code: 1.0}})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Sensor.objects.filter(code=long_code).exists())


class AcknowledgedAlarmAutoCloseTests(TestCase):
    """覆盖修复：数值恢复后ACKNOWLEDGED告警也随NEW告警一起自动关闭"""

    def test_acknowledged_alarm_closed_when_value_recovers(self):
        device = _make_device(3)
        sensor = Sensor.objects.create(
            device=device, code="temp", name="温度", unit="℃", min_value=18, max_value=32
        )
        alarm = Alarm.objects.create(
            device=device,
            sensor=sensor,
            ts=timezone.now(),
            level=Alarm.Level.WARNING,
            message="温度高于阈值",
            status=Alarm.Status.ACKNOWLEDGED,
        )
        result = record_threshold_alarm(sensor, value=25, ts=timezone.now())
        self.assertIsNone(result)
        alarm.refresh_from_db()
        self.assertEqual(alarm.status, Alarm.Status.CLOSED)
