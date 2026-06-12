#ifndef BEARPI_LAB_CONFIG_H
#define BEARPI_LAB_CONFIG_H

/*
 * Fill these values before flashing the board.
 * Keep BEARPI_DEVICE_TOKEN_SECRET in sync with backend DEVICE_TOKEN_SECRET.
 */
#define BEARPI_WIFI_SSID      "liar"
#define BEARPI_WIFI_PASSWORD  "1234567890"

#define BEARPI_SERVER_HOST    "10.211.178.163"
#define BEARPI_SERVER_HOST_FALLBACK "192.168.137.1"
#define BEARPI_SERVER_PORT    8000
#define BEARPI_DEVICE_SN      "BEARPI-NANO-A001"
#define BEARPI_DEVICE_TOKEN_SECRET "bearpi-device-token-secret-2026"

/*
 * Optional: paste a precomputed per-board token here if you do not want the
 * board to derive it at runtime. Leave empty for HMAC-SHA256(SN,secret) mode.
 */
#define BEARPI_DEVICE_TOKEN   ""

#define BEARPI_REPORT_INTERVAL_MS  2000
#define BEARPI_COMMAND_LIMIT       1

#define BEARPI_TEMP_HIGH_THRESHOLD   32.0f
#define BEARPI_HUM_HIGH_THRESHOLD    75.0f
#define BEARPI_LIGHT_LOW_THRESHOLD   20.0f

/*
 * Power sampling is disabled by default because BearPi-HM Nano does not
 * expose real board current in software. Enable these only after wiring a
 * voltage divider or current-sense circuit to ADC pins and calibrating them.
 */
#define BEARPI_VOLTAGE_ADC_ENABLE  0
#define BEARPI_CURRENT_ADC_ENABLE  0

#define BEARPI_VOLTAGE_ADC_CHANNEL WIFI_IOT_ADC_CHANNEL_5
#define BEARPI_CURRENT_ADC_CHANNEL WIFI_IOT_ADC_CHANNEL_6

#define BEARPI_ESTIMATED_SUPPLY_VOLTAGE 5.0f
#define BEARPI_ADC_REF_VOLTAGE          1.8f
#define BEARPI_ADC_SAMPLE_SCALE         4.0f
#define BEARPI_ADC_MAX_RAW              4096.0f
#define BEARPI_POWER_ADC_SAMPLES        8

/*
 * supply_voltage = adc_input_voltage * BEARPI_VOLTAGE_DIVIDER_RATIO
 * current_mA = (adc_input_voltage - zero_voltage) / (shunt_ohms * gain) * 1000
 */
#define BEARPI_VOLTAGE_DIVIDER_RATIO       1.0f
#define BEARPI_CURRENT_SENSE_SHUNT_OHMS    0.1f
#define BEARPI_CURRENT_SENSE_GAIN          1.0f
#define BEARPI_CURRENT_SENSE_ZERO_VOLTAGE  0.0f

#endif
