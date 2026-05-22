from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.devices.models import DeviceCommand


class Command(BaseCommand):
    help = "把长期停留在 SENT 状态的设备指令标记为 FAILED，避免任务永远 pending。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=300,
            help="SENT 状态最长允许等待的秒数（默认 300s）。",
        )
        parser.add_argument(
            "--message",
            default="设备超时未回执，自动判定失败",
            help="自动失败时写入 command.message 的文案。",
        )

    def handle(self, *args, **options):
        timeout = max(30, int(options["timeout"]))
        cutoff = timezone.now() - timedelta(seconds=timeout)
        stale = DeviceCommand.objects.filter(
            status=DeviceCommand.Status.SENT,
            created_at__lt=cutoff,
        )
        affected = stale.update(
            status=DeviceCommand.Status.FAILED,
            message=options["message"],
            ack_at=timezone.now(),
        )
        self.stdout.write(self.style.SUCCESS(f"recovered {affected} stale commands (>{timeout}s in SENT)"))
