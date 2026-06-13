from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.devices.models import DEVICE_COMMAND_AUTO_FAIL_MESSAGE, DeviceCommand


class Command(BaseCommand):
    help = "把长期停留在 SENT/QUEUED 状态的设备指令标记为 FAILED，避免任务永远 pending、离线板卡迟到执行过期指令。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=600,
            help="SENT 状态最长允许等待的秒数（默认 600s），按 sent_at 计时（历史数据缺 sent_at 时回退 created_at）。",
        )
        parser.add_argument(
            "--queued-timeout",
            type=int,
            default=3600,
            help="QUEUED 状态最长允许排队的秒数（默认 3600s），超时未被拉取的指令自动过期。",
        )
        parser.add_argument(
            "--message",
            default=DEVICE_COMMAND_AUTO_FAIL_MESSAGE,
            help="自动失败时写入 command.message 的文案。改动后迟到 ACK 将无法识别并覆盖自动失败状态。",
        )

    def handle(self, *args, **options):
        timeout = max(30, int(options["timeout"]))
        queued_timeout = max(30, int(options["queued_timeout"]))
        now = timezone.now()
        sent_cutoff = now - timedelta(seconds=timeout)
        stale_sent = DeviceCommand.objects.filter(status=DeviceCommand.Status.SENT).filter(
            Q(sent_at__lt=sent_cutoff) | Q(sent_at__isnull=True, created_at__lt=sent_cutoff)
        )
        sent_affected = stale_sent.update(
            status=DeviceCommand.Status.FAILED,
            message=options["message"],
            ack_at=now,
        )
        queued_cutoff = now - timedelta(seconds=queued_timeout)
        expired_queued = DeviceCommand.objects.filter(
            status=DeviceCommand.Status.QUEUED,
            created_at__lt=queued_cutoff,
        )
        queued_affected = expired_queued.update(
            status=DeviceCommand.Status.FAILED,
            message="指令排队超时未被设备拉取，已自动过期",
            ack_at=now,
        )
        self.stdout.write(self.style.SUCCESS(
            f"recovered {sent_affected} stale commands (>{timeout}s in SENT), "
            f"expired {queued_affected} queued commands (>{queued_timeout}s in QUEUED)"
        ))
