from django.core.management.base import BaseCommand
from django.db import transaction

from apps.devices.models import Device


class Command(BaseCommand):
    help = "Reassign device slots sequentially by register time without deleting devices."

    def handle(self, *args, **options):
        with transaction.atomic():
            devices = list(Device.objects.select_for_update().order_by("register_time", "id"))
            if not devices:
                self.stdout.write(self.style.SUCCESS("No devices to compact."))
                return

            temp_base = max(Device.objects.values_list("slot_no", flat=True), default=0) + 1000
            for index, device in enumerate(devices, start=1):
                device.slot_no = temp_base + index
                device.save(update_fields=["slot_no"])

            for index, device in enumerate(devices, start=1):
                device.slot_no = index
                if device.location.startswith("实验台") or device.location.startswith("自动接入槽位"):
                    device.location = f"实验台{index}/后端HTTP接入组"
                    device.save(update_fields=["slot_no", "location"])
                else:
                    device.save(update_fields=["slot_no"])

        self.stdout.write(self.style.SUCCESS(f"Compacted {len(devices)} devices into slots 1..{len(devices)}."))
