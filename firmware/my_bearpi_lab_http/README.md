# BearPi Nano HTTP Client

This is the BearPi-side HTTP version for local Wi-Fi integration.

It does four things in a loop:

1. Report sensor values to Django.
2. Pull queued commands from Django.
3. Wait until `params.execute_at` for synchronized motor/light commands.
4. ACK command execution result back to Django.

## Backend Address

Your current computer Wi-Fi IP is:

```text
10.212.180.213
```

The board should call:

```text
http://10.212.180.213:8000/api/v1/ingest/telemetry
http://10.212.180.213:8000/api/v1/device/commands/pull
http://10.212.180.213:8000/api/v1/device/commands/ack
```

## Configure

Edit:

```text
include/bearpi_lab_config.h
```

Set:

```c
#define BEARPI_WIFI_SSID      "YOUR_WIFI_SSID"
#define BEARPI_WIFI_PASSWORD  "your-wifi-password"
#define BEARPI_SERVER_HOST    "10.212.180.213"
#define BEARPI_SERVER_HOST_FALLBACK "192.168.137.1"
#define BEARPI_DEVICE_SN      "BEARPI-NANO-A001"
#define BEARPI_DEVICE_TOKEN_SECRET "replace-me-device-token-secret"
```

Use a unique board SN for each physical board. The backend assigns slots by first successful connection, so the first connected SN enters slot 1, the second enters slot 2, and so on up to 120 boards. These are examples only:

```text
BEARPI-NANO-A001
BEARPI-NANO-A002
BEARPI-NANO-A003
BEARPI-NANO-A004
BEARPI-NANO-A005
...
BEARPI-NANO-A120
```

## Copy Into BearPi Project

Recommended first integration:

1. Open your BearPi / OpenHarmony / Hi3861 project.
2. Create a new app module named `bearpi_lab_http`.
3. Copy `include/bearpi_lab_config.h` and `src/bearpi_lab_http_client.c` into that module.
4. Wire the module into your SDK build file. A starter `BUILD.gn` is included, but SDK paths may need adjustment.
5. Replace the Wi-Fi adapter function in the C file if your SDK uses a different Wi-Fi API.
6. Replace `ReadSensorSnapshot()` with real sensor readings.

## Current Sensor Behavior

This IA1 version reports real values from E53_IA1:

```text
temp / hum / light
```

E53_IA1 does not have an accelerometer, so it does not report `acc`.

It also reports power metrics:

```text
voltage / current / power
voltage_sampled / current_sampled / power_sampled
power_mcu / power_wifi / power_sensor / power_motor / power_light
```

Default behavior is still estimated because BearPi-HM Nano cannot know board current from software alone. The estimate is now dynamic: it uses the board SN, IA1 temperature/humidity/light readings, and motor/light state so multiple boards do not collapse to the same fixed power number when they have unique SNs and different environments.

```text
voltage = 5.0V
power = calibrated(MCU + WiFi + sensor + motor + light)
current = power / voltage
```

For estimated mode:

```c
#define BEARPI_POWER_ESTIMATE_CALIBRATION 0.0f
#define BEARPI_POWER_ESTIMATE_SN_TRIM_ENABLE 1
```

`BEARPI_POWER_ESTIMATE_CALIBRATION=0.0f` means auto-trim by SN. If you measure a board with a USB power meter or current-sense module, set a per-board calibration factor such as `0.96f` or `1.08f`. Keep `BEARPI_DEVICE_SN` unique for each physical board; flashing the same SN to multiple boards makes the backend treat them as the same board and also gives the estimator the same SN trim.

For real-time measurement, wire sampling hardware to ADC and edit `include/bearpi_lab_config.h`:

```c
#define BEARPI_VOLTAGE_ADC_ENABLE  1
#define BEARPI_CURRENT_ADC_ENABLE  1
#define BEARPI_VOLTAGE_ADC_CHANNEL WIFI_IOT_ADC_CHANNEL_5
#define BEARPI_CURRENT_ADC_CHANNEL WIFI_IOT_ADC_CHANNEL_6
#define BEARPI_VOLTAGE_DIVIDER_RATIO       1.0f
#define BEARPI_CURRENT_SENSE_SHUNT_OHMS    0.1f
#define BEARPI_CURRENT_SENSE_GAIN          1.0f
#define BEARPI_CURRENT_SENSE_ZERO_VOLTAGE  0.0f
```

The ADC formula is:

```text
adc_input_voltage = raw * 1.8 * 4 / 4096
supply_voltage = adc_input_voltage * BEARPI_VOLTAGE_DIVIDER_RATIO
current_mA = (adc_input_voltage - zero_voltage) / (shunt_ohms * gain) * 1000
power_mW = supply_voltage * current_mA
```

`voltage_sampled/current_sampled/power_sampled` are reported as `0` for estimated and `1` for ADC-sampled. Module power values are exact only if each module has its own current-sense circuit. With only one board-level current channel, this firmware scales the module estimates so their sum matches the measured board power.

## Backend Startup

Run Django like this:

```powershell
cd "C:\Users\32918\Desktop\IoT embedding\iot big\backend"
$env:DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost,10.212.180.213,192.168.137.1"
$env:DEVICE_TOKEN_SECRET="replace-me-device-token-secret"
python manage.py runserver 0.0.0.0:8000
```

Then open:

```text
http://10.212.180.213:8000/health
```

## Expected Frontend Result

Open:

```text
http://10.212.180.213:8000/
```

Go to:

```text
BEARPI-NANO-A001 -> temp -> realtime
```

When the board loop runs, the line chart should keep updating.
