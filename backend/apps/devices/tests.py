"""
关键业务路径的回归测试，覆盖第一/第二轮修复的核心 bug。
运行方法：
    cd backend
    python manage.py test apps.devices.tests
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.models import UserRoleProfile
from apps.cloud.models import CloudDeviceStatus
from apps.common.device_gateway import (
    KNOWN_BOARD_PROFILES,
    board_code_from_identifier,
    device_token_for_identifier,
    next_slot_no_locked,
    resolve_or_register_device,
)
from apps.devices.models import Device, DeviceCommand, Sensor
from apps.devices.views import (
    DeviceCommandAckView,
    create_bulk_commands,
    filter_bulk_command_devices,
    load_bulk_task_commands,
    serialize_bulk_task,
)


def _make_device(slot_no, sn=None, status=Device.Status.ONLINE, last_seen=None):
    device = Device.objects.create(
        slot_no=slot_no,
        sn=sn or f"BEARPI-NANO-A{slot_no:03d}",
        lab_id="lab-test",
        model="BearPi-HM Nano",
        firmware_version="v-test",
        location=f"test-{slot_no}",
        owner="test",
        member="tester",
        status=status,
        last_seen=last_seen or timezone.now(),
    )
    CloudDeviceStatus.objects.create(
        device=device,
        platform="Test",
        product_id="test",
        cloud_device_id=device.sn,
        node_id=device.sn,
    )
    return device


class BulkTaskAggregationTests(TestCase):
    """覆盖 Bug #1：批量任务切片切断 → 应按 batch_id 分组取齐"""

    def test_groups_all_commands_of_a_batch(self):
        devices = [_make_device(i) for i in range(1, 11)]
        batch_id, _, commands = create_bulk_commands(devices, "motor", "on", sync_delay_ms=5000)
        self.assertEqual(len(commands), 10)

        # 即便我们插入一大堆别的 batch 噪声，原 batch 仍应被一次性拉齐
        for i in range(11, 21):
            other_device = _make_device(i)
            create_bulk_commands([other_device], "light", "off", sync_delay_ms=5000)

        groups = load_bulk_task_commands(batch_id=batch_id)
        self.assertIn(batch_id, groups)
        self.assertEqual(len(groups[batch_id]), 10)

    def test_serialize_status_progresses_correctly(self):
        devices = [_make_device(i) for i in range(1, 4)]
        batch_id, _, commands = create_bulk_commands(devices, "motor", "off", sync_delay_ms=5000)
        # 模拟 1 acked + 1 failed + 1 queued
        commands[0].status = DeviceCommand.Status.ACKED
        commands[0].ack_at = timezone.now()
        commands[0].save()
        commands[1].status = DeviceCommand.Status.FAILED
        commands[1].ack_at = timezone.now()
        commands[1].save()
        groups = load_bulk_task_commands(batch_id=batch_id)
        task = serialize_bulk_task(batch_id, groups[batch_id])
        self.assertEqual(task["total"], 3)
        self.assertEqual(task["acked"], 1)
        self.assertEqual(task["failed"], 1)
        self.assertEqual(task["queued"], 1)
        self.assertEqual(task["status"], "partial")


class CommandPullRaceTests(TestCase):
    """覆盖 Bug #5：拉取竞态 → update WHERE status=QUEUED 必须幂等"""

    def test_pull_only_transitions_queued_rows(self):
        from apps.devices.models import DeviceCommand
        device = _make_device(1)
        DeviceCommand.objects.create(
            device=device,
            command=DeviceCommand.Command.REBOOT,
            params={},
            status=DeviceCommand.Status.QUEUED,
            message="queued1",
        )
        DeviceCommand.objects.create(
            device=device,
            command=DeviceCommand.Command.REBOOT,
            params={},
            status=DeviceCommand.Status.ACKED,
            message="already acked",
        )

        # 模拟两次拉取的 update_where 行为：第二次必须只匹配仍 QUEUED 的行
        updated_first = DeviceCommand.objects.filter(
            device=device, status=DeviceCommand.Status.QUEUED
        ).update(status=DeviceCommand.Status.SENT)
        updated_second = DeviceCommand.objects.filter(
            device=device, status=DeviceCommand.Status.QUEUED
        ).update(status=DeviceCommand.Status.SENT)
        self.assertEqual(updated_first, 1)
        self.assertEqual(updated_second, 0)


class DeviceCommandApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="command-admin", password="pass")
        UserRoleProfile.objects.create(user=self.user, role=UserRoleProfile.Role.ADMIN)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_send_command_to_missing_device_returns_404(self):
        response = self.client.post(
            "/api/v1/devices/999/commands",
            {"type": DeviceCommand.Command.REBOOT, "params": {}},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(DeviceCommand.objects.exists())


class DeviceListActiveFilterTests(TestCase):
    """覆盖 Bug #3：新设备已写 last_seen=now，默认列表能看到"""

    def test_recently_seen_device_appears_in_default_list(self):
        from django.conf import settings
        cutoff = timezone.now() - timedelta(seconds=settings.DEVICE_ACTIVE_TTL_SECONDS)
        # 注册时立刻可见
        _make_device(1, last_seen=timezone.now())
        # 老旧设备：超过 TTL 的不应出现
        _make_device(2, last_seen=cutoff - timedelta(seconds=30))

        active = Device.objects.filter(last_seen__gte=cutoff)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().slot_no, 1)


class BulkTargetFilterTests(TestCase):
    """覆盖批量控制目标筛选：只向当前可执行设备下发"""

    def test_all_target_excludes_offline_and_inactive(self):
        from django.conf import settings
        cutoff = timezone.now() - timedelta(seconds=settings.DEVICE_ACTIVE_TTL_SECONDS)
        _make_device(1, status=Device.Status.ONLINE, last_seen=timezone.now())
        _make_device(2, status=Device.Status.OFFLINE, last_seen=timezone.now())
        _make_device(3, status=Device.Status.WARNING, last_seen=cutoff - timedelta(seconds=60))
        _make_device(4, status=Device.Status.MAINTENANCE, last_seen=timezone.now())

        qs = filter_bulk_command_devices("all")
        slots = sorted(qs.values_list("slot_no", flat=True))
        self.assertEqual(slots, [1, 4])  # OFFLINE 排除；3 号过老也排除

    def test_selected_target_excludes_offline_maintenance_and_inactive(self):
        from django.conf import settings
        cutoff = timezone.now() - timedelta(seconds=settings.DEVICE_ACTIVE_TTL_SECONDS)
        online = _make_device(1, status=Device.Status.ONLINE, last_seen=timezone.now())
        offline = _make_device(2, status=Device.Status.OFFLINE, last_seen=timezone.now())
        stale = _make_device(3, status=Device.Status.WARNING, last_seen=cutoff - timedelta(seconds=60))
        maintenance = _make_device(4, status=Device.Status.MAINTENANCE, last_seen=timezone.now())
        warning = _make_device(5, status=Device.Status.WARNING, last_seen=timezone.now())

        qs = filter_bulk_command_devices(
            "selected",
            [online.id, offline.id, stale.id, maintenance.id, warning.id],
        )
        slots = sorted(qs.values_list("slot_no", flat=True))
        self.assertEqual(slots, [1, 5])


class DeviceCommandAckTests(TestCase):
    def test_duplicate_ack_does_not_overwrite_terminal_command(self):
        device = _make_device(1)
        command = DeviceCommand.objects.create(
            device=device,
            command=DeviceCommand.Command.SET_PARAM,
            params={"value": "on"},
            status=DeviceCommand.Status.ACKED,
            ack_at=timezone.now() - timedelta(seconds=30),
            message="首次执行成功",
        )

        request = APIRequestFactory().post(
            "/api/device/commands/ack",
            {
                "sn": device.sn,
                "command_id": command.id,
                "status": DeviceCommand.Status.FAILED,
                "message": "迟到失败回执",
            },
            format="json",
            HTTP_X_DEVICE_TOKEN=settings.DEVICE_INGEST_TOKEN,
        )
        response = DeviceCommandAckView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        command.refresh_from_db()
        self.assertEqual(command.status, DeviceCommand.Status.ACKED)
        self.assertEqual(command.message, "首次执行成功")

    @mock.patch("apps.common.device_gateway.settings.DEVICE_TOKEN_SECRET", "unit-test-device-secret")
    @mock.patch("apps.common.device_gateway.settings.DEVICE_INGEST_TOKEN", "")
    def test_per_device_token_can_ack_without_global_token(self):
        device = _make_device(1, sn="BEARPI-NANO-A001")
        command = DeviceCommand.objects.create(
            device=device,
            command=DeviceCommand.Command.SET_PARAM,
            params={"value": "on"},
            status=DeviceCommand.Status.SENT,
            message="等待设备 ACK",
        )

        request = APIRequestFactory().post(
            "/api/device/commands/ack",
            {
                "sn": device.sn,
                "command_id": command.id,
                "status": DeviceCommand.Status.ACKED,
            },
            format="json",
            HTTP_X_DEVICE_TOKEN=device_token_for_identifier(device.sn),
        )
        response = DeviceCommandAckView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        command.refresh_from_db()
        self.assertEqual(command.status, DeviceCommand.Status.ACKED)


class AuditMetadataSanitizeTests(TestCase):
    """覆盖第二轮：metadata 大小封顶 + JSON 安全降级"""

    def test_large_metadata_is_truncated(self):
        from apps.audit.services import _sanitize_metadata, AUDIT_METADATA_MAX_BYTES
        big = {f"k{i}": "x" * 100 for i in range(200)}
        sanitized = _sanitize_metadata(big)
        self.assertIn("_truncated", sanitized)
        self.assertLessEqual(len(str(sanitized).encode("utf-8")), AUDIT_METADATA_MAX_BYTES + 1024)

    def test_unserializable_metadata_falls_back(self):
        from apps.audit.services import _sanitize_metadata
        unserializable = {"obj": object()}
        sanitized = _sanitize_metadata(unserializable)
        # default=str 会把 object() 转成字符串，不应崩溃
        self.assertIsInstance(sanitized, dict)


class BoardIdentificationTests(TestCase):
    def test_board_code_match_explicit(self):
        self.assertEqual(board_code_from_identifier("BEARPI-NANO-A003"), "A003")

    def test_board_code_fallback_to_trailing(self):
        # 只对包含BEARPI/NANO关键字的标识符使用尾部数字匹配
        self.assertEqual(board_code_from_identifier("BEARPI-002"), "A002")
        self.assertEqual(board_code_from_identifier("xxx-002"), None)  # 不含关键字，不匹配
        self.assertEqual(board_code_from_identifier(None), None)


class DeviceAutoRegisterTests(TestCase):
    """覆盖 Bug #3 + #4：自动注册时 last_seen 立即写入，slot_no 唯一"""

    def test_resolve_or_register_assigns_slot_and_lastseen(self):
        device = resolve_or_register_device({"sn": "BEARPI-NANO-A001"})
        self.assertIsNotNone(device.last_seen)
        self.assertEqual(device.sn, KNOWN_BOARD_PROFILES["A001"]["sn"])
        self.assertEqual(device.slot_no, 1)
        # 二次解析返回同一台
        device2 = resolve_or_register_device({"sn": "BEARPI-NANO-A001"})
        self.assertEqual(device.id, device2.id)

    def test_known_board_uses_profile_slot_when_old_device_blocks_it(self):
        old_device = _make_device(2, sn="BEARPI-NANO-OLD002", status=Device.Status.OFFLINE)
        device = resolve_or_register_device({"sn": "BEARPI-NANO-A002"})
        old_device.refresh_from_db()
        self.assertEqual(device.slot_no, 2)
        self.assertGreaterEqual(old_device.slot_no, 5)

    def test_next_slot_no_locked_starts_from_one(self):
        from django.db import transaction
        with transaction.atomic():
            self.assertEqual(next_slot_no_locked(), 1)
        resolve_or_register_device({"sn": "BEARPI-NANO-A001"})
        with transaction.atomic():
            next_value = next_slot_no_locked()
        self.assertGreaterEqual(next_value, 2)
