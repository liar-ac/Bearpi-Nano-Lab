"""
传感器历史接口的范围/校验测试。
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.cloud.models import CloudDeviceStatus
from apps.devices.models import Device, Sensor
from apps.telemetry.views import EXECUTOR_SENSOR_CODES, MAX_HISTORY_RANGE, parse_required_datetime, record_threshold_alarm
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
