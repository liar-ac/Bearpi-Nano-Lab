from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.telemetry.models import RawPoint


class Command(BaseCommand):
    help = (
        "按时间清理 RawPoint 历史采样点，避免单张表无限增长。"
        "默认保留最近 90 天，可用 --days/--batch-size 调整。"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="保留天数，早于该窗口的采样点将被删除（默认 90 天）。",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="每批删除的行数，控制单事务大小，默认 5000。",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只统计将被删除的行数，不真正执行删除。",
        )
        parser.add_argument(
            "--sensor",
            type=int,
            default=None,
            help="只清理特定 sensor_id（可选）。",
        )

    def handle(self, *args, **options):
        days = max(1, int(options["days"]))
        batch_size = max(100, int(options["batch_size"]))
        dry_run = bool(options["dry_run"])
        sensor_id = options.get("sensor")

        cutoff = timezone.now() - timedelta(days=days)
        queryset = RawPoint.objects.filter(ts__lt=cutoff)
        if sensor_id:
            queryset = queryset.filter(sensor_id=sensor_id)

        total_candidates = queryset.count()
        self.stdout.write(
            self.style.NOTICE(
                f"cutoff={cutoff.isoformat()} candidates={total_candidates} batch_size={batch_size} dry_run={dry_run}"
            )
        )
        if dry_run or total_candidates == 0:
            return

        deleted_total = 0
        while True:
            with transaction.atomic():
                ids = list(queryset.values_list("id", flat=True)[:batch_size])
                if not ids:
                    break
                deleted, _ = RawPoint.objects.filter(id__in=ids).delete()
            deleted_total += deleted
            self.stdout.write(self.style.NOTICE(f"deleted {deleted_total}/{total_candidates}"))
            if deleted < batch_size:
                break

        self.stdout.write(self.style.SUCCESS(f"done, removed {deleted_total} rows older than {days}d"))
