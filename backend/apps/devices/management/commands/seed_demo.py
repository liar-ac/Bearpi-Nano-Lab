from datetime import timedelta
import math
import os
import secrets

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.alarms.models import Alarm
from apps.accounts.models import UserRoleProfile
from apps.devices.models import Device, Sensor
from apps.telemetry.models import RawPoint


class Command(BaseCommand):
    help = "Seed BearPi Nano lab demo users. Demo devices are opt-in."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-demo-devices",
            action="store_true",
            help="Also create the old four demo boards. Do not use this for real device auto-discovery mode.",
        )
        parser.add_argument(
            "--allow-prod",
            action="store_true",
            help="允许在 DEBUG=false 时执行（默认拒绝以防止泄漏弱密码）。",
        )
        parser.add_argument(
            "--admin-password",
            default=os.getenv("SEED_ADMIN_PASSWORD", ""),
            help="覆盖默认 admin 密码；不指定则使用 SEED_ADMIN_PASSWORD 或随机生成。",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_prod"]:
            raise CommandError(
                "拒绝执行：DEBUG=false 时禁止 seed_demo 创建弱密码账号；"
                "如确需执行，请显式加 --allow-prod 并通过 --admin-password 指定强密码。"
            )

        admin_password = options["admin_password"] or "admin123"
        if not settings.DEBUG and admin_password == "admin123":
            admin_password = secrets.token_urlsafe(12)
            self.stdout.write(self.style.WARNING(
                f"生产模式下检测到默认密码 admin123，已自动改为随机：{admin_password}"
            ))

        self.create_users(admin_password)
        if options["with_demo_devices"]:
            self.create_devices()
            self.stdout.write(self.style.SUCCESS("Demo users and boards seeded."))
            return
        self.stdout.write(self.style.SUCCESS("Demo users seeded. Device list is now driven by real board ingest."))

    def create_users(self, admin_password):
        users = [
            ("admin", admin_password, True, True, "实验室管理员", UserRoleProfile.Role.ADMIN),
            ("exp", "admin123", False, False, "实验员", UserRoleProfile.Role.EXPERIMENTER),
            ("lab", "admin123", False, False, "实验员", UserRoleProfile.Role.EXPERIMENTER),
            ("viewer", "admin123", False, False, "只读观察员", UserRoleProfile.Role.VIEWER),
        ]
        for username, password, is_staff, is_superuser, first_name, role in users:
            user, _ = User.objects.get_or_create(username=username)
            user.first_name = first_name
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.is_active = True
            user.set_password(password)
            user.save()
            UserRoleProfile.objects.update_or_create(user=user, defaults={"role": role})

    def create_devices(self):
        now = timezone.now()
        owner = "嵌入式+前端+后端+APP联合组"
        specs = [
            (1, "BEARPI-NANO-A001", "成员A", "online", "", 1, "v1.3.2", 1),
            (2, "BEARPI-NANO-A002", "成员B", "warning", "光照传感器近10分钟波动过大", 3, "v1.3.2", 1),
            (3, "BEARPI-NANO-A003", "成员C", "maintenance", "", 12, "v1.3.2", 1),
            (4, "BEARPI-NANO-A004", "成员D", "offline", "超过30分钟未上报", 42, "v1.3.2", 1),
        ]
        for slot, sn, member, status, abnormal, minutes_ago, firmware, sample_rate in specs:
            device, _ = Device.objects.update_or_create(
                sn=sn,
                defaults={
                    "slot_no": slot,
                    "lab_id": "lab-embedded-01",
                    "model": "BearPi-HM Nano",
                    "firmware_version": firmware,
                    "location": f"实验台{slot}/后端HTTP接入组",
                    "owner": owner,
                    "member": member,
                    "status": status,
                    "last_seen": now - timedelta(minutes=minutes_ago),
                    "ip_address": f"192.168.31.4{slot}",
                    "cloud_twin_id": "",
                    "sample_rate": sample_rate,
                    "abnormal_reason": abnormal,
                },
            )
            self.create_sensors_and_points(device, slot, now)

        self.create_alarms(now)

    def create_sensors_and_points(self, device, index, now):
        Sensor.objects.filter(device=device, code="acc").delete()
        templates = [
            ("temp", "温度", "℃", "板载温度传感器", 18, 32, 24.6 + index * 0.7),
            ("hum", "湿度", "%", "环境湿度", 25, 75, 48 + index * 4),
            ("light", "光照", "lx", "光照强度，低于阈值时开启补光灯", 20, 1200, 420 + index * 86),
            ("motor", "电机驱动", "", "IA1 通风电机状态，0=关闭，1=开启", 0, 1, 0),
            ("voltage", "工作电压", "V", "开发板工作电压", 4.75, 5.25, 5.0 + index * 0.01),
            ("current", "工作电流", "mA", "开发板工作电流", 0, 500, 80 + index * 12),
            ("power", "功耗", "mW", "开发板瞬时功耗", 0, 2500, 400 + index * 60),
            ("voltage_sampled", "电压采样来源", "", "0=估算，1=ADC采样", 0, 1, index % 2),
            ("current_sampled", "电流采样来源", "", "0=估算，1=ADC采样", 0, 1, index % 2),
            ("power_sampled", "功耗采样来源", "", "0=估算，1=ADC采样", 0, 1, index % 2),
            ("power_mcu", "主控功耗", "mW", "主控芯片功耗", 0, 800, 250),
            ("power_wifi", "WiFi功耗", "mW", "WiFi通信模块功耗", 0, 1000, 120 + index * 5),
            ("power_sensor", "传感器功耗", "mW", "E53_IA1传感器板功耗", 0, 500, 35),
            ("power_motor", "电机功耗", "mW", "通风电机功耗", 0, 1500, 0),
            ("power_light", "补光灯功耗", "mW", "补光灯功耗", 0, 500, 0),
        ]
        for code, name, unit, description, min_value, max_value, base in templates:
            sensor, _ = Sensor.objects.update_or_create(
                device=device,
                code=code,
                defaults={
                    "name": name,
                    "unit": unit,
                    "description": description,
                    "min_value": min_value,
                    "max_value": max_value,
                    "latest_ts": now - timedelta(minutes=index),
                    "latest_value": round(base, 2),
                },
            )
            RawPoint.objects.filter(sensor=sensor).delete()
            points = []
            for point_index in range(96):
                ts = now - timedelta(minutes=(95 - point_index) * 5)
                if code == "motor":
                    value = 1 if point_index % 24 in (0, 1, 2) else 0
                elif code in ("voltage_sampled", "current_sampled", "power_sampled"):
                    value = float(base)
                elif code in ("power_mcu", "power_wifi", "power_sensor"):
                    value = round(base + math.sin(point_index / 5) * 15, 2)
                elif code in ("power_motor", "power_light"):
                    value = round(base + math.sin(point_index / 8) * 10, 2)
                elif code == "power":
                    motor_on = 1 if point_index % 24 in (0, 1, 2) else 0
                    value = round(base + motor_on * 600 + math.sin(point_index / 4) * 20, 2)
                elif code == "current":
                    motor_on = 1 if point_index % 24 in (0, 1, 2) else 0
                    value = round(base + motor_on * 120 + math.sin(point_index / 4) * 5, 2)
                elif code == "voltage":
                    value = round(base + math.sin(point_index / 6) * 0.05, 3)
                else:
                    value = round(base + math.sin(point_index / 4) * (max_value - min_value) * 0.04, 3)
                points.append(RawPoint(device=device, sensor=sensor, ts=ts, value=value))
            RawPoint.objects.bulk_create(points)

    def create_alarms(self, now):
        demo_sns = [spec[1] for spec in [
            (1, "BEARPI-NANO-A001"), (2, "BEARPI-NANO-A002"),
            (3, "BEARPI-NANO-A003"), (4, "BEARPI-NANO-A004"),
        ]]
        Alarm.objects.filter(device__sn__in=demo_sns).delete()
        device_2 = Device.objects.get(sn="BEARPI-NANO-A002")
        device_4 = Device.objects.get(sn="BEARPI-NANO-A004")
        light = Sensor.objects.get(device=device_2, code="light")
        Alarm.objects.create(
            device=device_2,
            sensor=light,
            ts=now - timedelta(minutes=4),
            level="warning",
            status="new",
            message="光照传感器波动超过预警阈值",
        )
        Alarm.objects.create(
            device=device_4,
            ts=now - timedelta(minutes=42),
            level="critical",
            status="new",
            message="设备离线，最近一次上报超过 30 分钟",
        )
