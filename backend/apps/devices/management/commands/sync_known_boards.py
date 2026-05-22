from django.core.management.base import BaseCommand

from apps.common.device_gateway import KNOWN_BOARD_PROFILES, sync_known_board_profile
from apps.devices.models import Device


class Command(BaseCommand):
    help = "Normalize known BearPi board metadata and fixed slot numbers."

    def handle(self, *args, **options):
        updated = 0
        missing = []

        for code, profile in KNOWN_BOARD_PROFILES.items():
            device = (
                Device.objects.filter(sn=profile["sn"]).first()
                or Device.objects.filter(sn__icontains=code).first()
                or Device.objects.filter(cloud__node_id__icontains=code).first()
                or Device.objects.filter(cloud_twin_id__icontains=code).first()
            )
            if device is None:
                missing.append(profile["sn"])
                continue

            before = {
                "sn": device.sn,
                "slot_no": device.slot_no,
                "firmware_version": device.firmware_version,
                "location": device.location,
                "owner": device.owner,
                "member": device.member,
                "sample_rate": device.sample_rate,
            }
            sync_known_board_profile(device, {"sn": profile["sn"]})
            device.refresh_from_db()
            after = {
                "sn": device.sn,
                "slot_no": device.slot_no,
                "firmware_version": device.firmware_version,
                "location": device.location,
                "owner": device.owner,
                "member": device.member,
                "sample_rate": device.sample_rate,
            }
            if before != after:
                updated += 1
                self.stdout.write(f"{profile['sn']}: slot {before['slot_no']} -> {after['slot_no']}")

        self.stdout.write(self.style.SUCCESS(f"Known boards synced: {updated} updated."))
        if missing:
            self.stdout.write(f"Not present yet: {', '.join(missing)}")
