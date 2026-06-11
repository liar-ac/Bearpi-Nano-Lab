#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

#include "ohos_init.h"
#include "cmsis_os2.h"
#include "lwip/sockets.h"

#include "wifiiot_adc.h"
#include "wifiiot_errno.h"

#include "bearpi_lab_config.h"
#include "wifi_connect.h"
#include "E53_IA1.h"

#define TASK_STACK_SIZE (1024 * 12)
#define TASK_PRIO 25
#define HTTP_RX_BUF_SIZE 1536
#define HTTP_TX_BUF_SIZE 1024
#define JSON_BUF_SIZE 768
#define ACTUATOR_AUTO (-1)
#define ACTUATOR_OFF 0
#define ACTUATOR_ON 1
#define ISO_TIME_BUF_SIZE 40
#define MAX_SYNC_WAIT_MS 30000
#define SHA256_BLOCK_SIZE 64
#define SHA256_DIGEST_SIZE 32
#define DEVICE_TOKEN_HEX_SIZE 65
#define DEVICE_TOKEN_MESSAGE_PREFIX "bearpi-device:"

#ifndef BEARPI_VOLTAGE_ADC_ENABLE
#define BEARPI_VOLTAGE_ADC_ENABLE 0
#endif
#ifndef BEARPI_CURRENT_ADC_ENABLE
#define BEARPI_CURRENT_ADC_ENABLE 0
#endif
#ifndef BEARPI_VOLTAGE_ADC_CHANNEL
#define BEARPI_VOLTAGE_ADC_CHANNEL WIFI_IOT_ADC_CHANNEL_5
#endif
#ifndef BEARPI_CURRENT_ADC_CHANNEL
#define BEARPI_CURRENT_ADC_CHANNEL WIFI_IOT_ADC_CHANNEL_6
#endif
#ifndef BEARPI_ESTIMATED_SUPPLY_VOLTAGE
#define BEARPI_ESTIMATED_SUPPLY_VOLTAGE 5.0f
#endif
#ifndef BEARPI_ADC_REF_VOLTAGE
#define BEARPI_ADC_REF_VOLTAGE 1.8f
#endif
#ifndef BEARPI_ADC_SAMPLE_SCALE
#define BEARPI_ADC_SAMPLE_SCALE 4.0f
#endif
#ifndef BEARPI_ADC_MAX_RAW
#define BEARPI_ADC_MAX_RAW 4096.0f
#endif
#ifndef BEARPI_POWER_ADC_SAMPLES
#define BEARPI_POWER_ADC_SAMPLES 8
#endif
#ifndef BEARPI_VOLTAGE_DIVIDER_RATIO
#define BEARPI_VOLTAGE_DIVIDER_RATIO 1.0f
#endif
#ifndef BEARPI_CURRENT_SENSE_SHUNT_OHMS
#define BEARPI_CURRENT_SENSE_SHUNT_OHMS 0.1f
#endif
#ifndef BEARPI_CURRENT_SENSE_GAIN
#define BEARPI_CURRENT_SENSE_GAIN 1.0f
#endif
#ifndef BEARPI_CURRENT_SENSE_ZERO_VOLTAGE
#define BEARPI_CURRENT_SENSE_ZERO_VOLTAGE 0.0f
#endif
#ifndef BEARPI_SERVER_HOST_FALLBACK
#define BEARPI_SERVER_HOST_FALLBACK ""
#endif

E53_IA1_Data_TypeDef E53_IA1_Data;

static int g_motorOverride = ACTUATOR_AUTO;
static int g_lightOverride = ACTUATOR_AUTO;
static char g_deviceToken[DEVICE_TOKEN_HEX_SIZE];
static int g_deviceTokenReady = 0;
static const char *g_activeServerHost = BEARPI_SERVER_HOST;

typedef struct {
    uint8_t data[SHA256_BLOCK_SIZE];
    uint32_t dataLen;
    uint64_t bitLen;
    uint32_t state[8];
} Sha256Context;

static const uint32_t SHA256_K[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
    0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
    0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
    0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
    0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
    0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
    0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
    0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
    0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
    0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
    0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
    0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
    0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
    0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U
};

typedef struct {
    float temp;
    float hum;
    float light;
    float voltage;
    float current;
    float power;
    float powerMcu;
    float powerWifi;
    float powerSensor;
    float powerMotor;
    float powerLight;
    int voltageSampled;
    int currentSampled;
    int powerSampled;
    int motorOn;
    int fillLightOn;
} SensorSnapshot;

static uint32_t RotRight(uint32_t value, uint32_t bits)
{
    if (bits == 0) return value;
    return (value >> bits) | (value << (32U - bits));
}

static uint32_t Sha256Ch(uint32_t x, uint32_t y, uint32_t z)
{
    return (x & y) ^ (~x & z);
}

static uint32_t Sha256Maj(uint32_t x, uint32_t y, uint32_t z)
{
    return (x & y) ^ (x & z) ^ (y & z);
}

static uint32_t Sha256Ep0(uint32_t x)
{
    return RotRight(x, 2U) ^ RotRight(x, 13U) ^ RotRight(x, 22U);
}

static uint32_t Sha256Ep1(uint32_t x)
{
    return RotRight(x, 6U) ^ RotRight(x, 11U) ^ RotRight(x, 25U);
}

static uint32_t Sha256Sig0(uint32_t x)
{
    return RotRight(x, 7U) ^ RotRight(x, 18U) ^ (x >> 3U);
}

static uint32_t Sha256Sig1(uint32_t x)
{
    return RotRight(x, 17U) ^ RotRight(x, 19U) ^ (x >> 10U);
}

static void Sha256Transform(Sha256Context *ctx, const uint8_t data[])
{
    uint32_t m[64];
    uint32_t a;
    uint32_t b;
    uint32_t c;
    uint32_t d;
    uint32_t e;
    uint32_t f;
    uint32_t g;
    uint32_t h;

    for (int i = 0, j = 0; i < 16; ++i, j += 4) {
        m[i] = ((uint32_t)data[j] << 24U)
            | ((uint32_t)data[j + 1] << 16U)
            | ((uint32_t)data[j + 2] << 8U)
            | ((uint32_t)data[j + 3]);
    }
    for (int i = 16; i < 64; ++i) {
        m[i] = Sha256Sig1(m[i - 2]) + m[i - 7] + Sha256Sig0(m[i - 15]) + m[i - 16];
    }

    a = ctx->state[0];
    b = ctx->state[1];
    c = ctx->state[2];
    d = ctx->state[3];
    e = ctx->state[4];
    f = ctx->state[5];
    g = ctx->state[6];
    h = ctx->state[7];

    for (int i = 0; i < 64; ++i) {
        uint32_t t1 = h + Sha256Ep1(e) + Sha256Ch(e, f, g) + SHA256_K[i] + m[i];
        uint32_t t2 = Sha256Ep0(a) + Sha256Maj(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

static void Sha256Init(Sha256Context *ctx)
{
    ctx->dataLen = 0;
    ctx->bitLen = 0;
    ctx->state[0] = 0x6a09e667U;
    ctx->state[1] = 0xbb67ae85U;
    ctx->state[2] = 0x3c6ef372U;
    ctx->state[3] = 0xa54ff53aU;
    ctx->state[4] = 0x510e527fU;
    ctx->state[5] = 0x9b05688cU;
    ctx->state[6] = 0x1f83d9abU;
    ctx->state[7] = 0x5be0cd19U;
}

static void Sha256Update(Sha256Context *ctx, const uint8_t data[], size_t len)
{
    for (size_t i = 0; i < len; ++i) {
        ctx->data[ctx->dataLen] = data[i];
        ctx->dataLen++;
        if (ctx->dataLen == SHA256_BLOCK_SIZE) {
            Sha256Transform(ctx, ctx->data);
            ctx->bitLen += 512U;
            ctx->dataLen = 0;
        }
    }
}

static void Sha256Final(Sha256Context *ctx, uint8_t hash[])
{
    uint32_t i = ctx->dataLen;

    if (ctx->dataLen < 56U) {
        ctx->data[i++] = 0x80U;
        while (i < 56U) {
            ctx->data[i++] = 0x00U;
        }
    } else {
        ctx->data[i++] = 0x80U;
        while (i < 64U) {
            ctx->data[i++] = 0x00U;
        }
        Sha256Transform(ctx, ctx->data);
        memset(ctx->data, 0, 56U);
    }

    ctx->bitLen += (uint64_t)ctx->dataLen * 8U;
    ctx->data[63] = (uint8_t)(ctx->bitLen);
    ctx->data[62] = (uint8_t)(ctx->bitLen >> 8U);
    ctx->data[61] = (uint8_t)(ctx->bitLen >> 16U);
    ctx->data[60] = (uint8_t)(ctx->bitLen >> 24U);
    ctx->data[59] = (uint8_t)(ctx->bitLen >> 32U);
    ctx->data[58] = (uint8_t)(ctx->bitLen >> 40U);
    ctx->data[57] = (uint8_t)(ctx->bitLen >> 48U);
    ctx->data[56] = (uint8_t)(ctx->bitLen >> 56U);
    Sha256Transform(ctx, ctx->data);

    for (i = 0; i < 4U; ++i) {
        hash[i] = (uint8_t)((ctx->state[0] >> (24U - i * 8U)) & 0x000000ffU);
        hash[i + 4U] = (uint8_t)((ctx->state[1] >> (24U - i * 8U)) & 0x000000ffU);
        hash[i + 8U] = (uint8_t)((ctx->state[2] >> (24U - i * 8U)) & 0x000000ffU);
        hash[i + 12U] = (uint8_t)((ctx->state[3] >> (24U - i * 8U)) & 0x000000ffU);
        hash[i + 16U] = (uint8_t)((ctx->state[4] >> (24U - i * 8U)) & 0x000000ffU);
        hash[i + 20U] = (uint8_t)((ctx->state[5] >> (24U - i * 8U)) & 0x000000ffU);
        hash[i + 24U] = (uint8_t)((ctx->state[6] >> (24U - i * 8U)) & 0x000000ffU);
        hash[i + 28U] = (uint8_t)((ctx->state[7] >> (24U - i * 8U)) & 0x000000ffU);
    }
}

static void HmacSha256(const uint8_t *key, size_t keyLen, const uint8_t *data, size_t dataLen, uint8_t digest[])
{
    uint8_t keyBlock[SHA256_BLOCK_SIZE];
    uint8_t innerPad[SHA256_BLOCK_SIZE];
    uint8_t outerPad[SHA256_BLOCK_SIZE];
    uint8_t innerHash[SHA256_DIGEST_SIZE];
    Sha256Context ctx;

    memset(keyBlock, 0, sizeof(keyBlock));
    if (keyLen > SHA256_BLOCK_SIZE) {
        Sha256Init(&ctx);
        Sha256Update(&ctx, key, keyLen);
        Sha256Final(&ctx, keyBlock);
    } else {
        memcpy(keyBlock, key, keyLen);
    }

    for (int i = 0; i < SHA256_BLOCK_SIZE; ++i) {
        innerPad[i] = keyBlock[i] ^ 0x36U;
        outerPad[i] = keyBlock[i] ^ 0x5cU;
    }

    Sha256Init(&ctx);
    Sha256Update(&ctx, innerPad, sizeof(innerPad));
    Sha256Update(&ctx, data, dataLen);
    Sha256Final(&ctx, innerHash);

    Sha256Init(&ctx);
    Sha256Update(&ctx, outerPad, sizeof(outerPad));
    Sha256Update(&ctx, innerHash, sizeof(innerHash));
    Sha256Final(&ctx, digest);
}

static void HexEncode(const uint8_t digest[], char *out, int outLen)
{
    static const char HEX[] = "0123456789abcdef";
    if (outLen < DEVICE_TOKEN_HEX_SIZE) {
        return;
    }
    for (int i = 0; i < SHA256_DIGEST_SIZE; ++i) {
        out[i * 2] = HEX[(digest[i] >> 4U) & 0x0fU];
        out[i * 2 + 1] = HEX[digest[i] & 0x0fU];
    }
    out[SHA256_DIGEST_SIZE * 2] = '\0';
}

static void UppercaseIdentifier(const char *input, char *output, int outputLen)
{
    int i = 0;
    if (outputLen <= 0) {
        return;
    }
    for (; input[i] != '\0' && i < outputLen - 1; ++i) {
        char ch = input[i];
        output[i] = (ch >= 'a' && ch <= 'z') ? (char)(ch - 'a' + 'A') : ch;
    }
    output[i] = '\0';
}

static const char *GetDeviceToken(void)
{
    if (g_deviceTokenReady) {
        return g_deviceToken;
    }

    if (strlen(BEARPI_DEVICE_TOKEN) > 0) {
        snprintf(g_deviceToken, sizeof(g_deviceToken), "%s", BEARPI_DEVICE_TOKEN);
        g_deviceTokenReady = 1;
        return g_deviceToken;
    }

    char identifier[96];
    char message[128];
    uint8_t digest[SHA256_DIGEST_SIZE];
    UppercaseIdentifier(BEARPI_DEVICE_SN, identifier, sizeof(identifier));
    int messageLen = snprintf(message, sizeof(message), "%s%s", DEVICE_TOKEN_MESSAGE_PREFIX, identifier);
    if (strlen(BEARPI_DEVICE_TOKEN_SECRET) == 0 || messageLen <= 0 || messageLen >= (int)sizeof(message)) {
        printf("[bearpi-lab] missing device token secret or token message too long\r\n");
        g_deviceToken[0] = '\0';
        g_deviceTokenReady = 1;
        return g_deviceToken;
    }

    HmacSha256(
        (const uint8_t *)BEARPI_DEVICE_TOKEN_SECRET,
        strlen(BEARPI_DEVICE_TOKEN_SECRET),
        (const uint8_t *)message,
        (size_t)messageLen,
        digest
    );
    HexEncode(digest, g_deviceToken, sizeof(g_deviceToken));
    g_deviceTokenReady = 1;
    return g_deviceToken;
}

static void CloseSocket(int sock)
{
    closesocket(sock);
}

static int ConnectTcpToHost(const char *host)
{
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        printf("[bearpi-lab] socket create failed\r\n");
        return -1;
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(BEARPI_SERVER_PORT);
    addr.sin_addr.s_addr = inet_addr(host);

    if (addr.sin_addr.s_addr == INADDR_NONE) {
        printf("[bearpi-lab] inet_addr failed for host %s\r\n", host);
        CloseSocket(sock);
        return -1;
    }

    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        printf("[bearpi-lab] connect %s:%d failed\r\n", host, BEARPI_SERVER_PORT);
        CloseSocket(sock);
        return -1;
    }

    return sock;
}

static int ConnectTcp(void)
{
    int sock = ConnectTcpToHost(BEARPI_SERVER_HOST);
    if (sock >= 0) {
        g_activeServerHost = BEARPI_SERVER_HOST;
        return sock;
    }

    if (strlen(BEARPI_SERVER_HOST_FALLBACK) > 0 &&
        strcmp(BEARPI_SERVER_HOST_FALLBACK, BEARPI_SERVER_HOST) != 0) {
        printf("[bearpi-lab] trying fallback server %s:%d\r\n", BEARPI_SERVER_HOST_FALLBACK, BEARPI_SERVER_PORT);
        sock = ConnectTcpToHost(BEARPI_SERVER_HOST_FALLBACK);
        if (sock >= 0) {
            g_activeServerHost = BEARPI_SERVER_HOST_FALLBACK;
            return sock;
        }
    }

    return -1;
}

static int SendAll(int sock, const char *data, int len)
{
    int total = 0;
    while (total < len) {
        int sent = send(sock, data + total, len - total, 0);
        if (sent <= 0) {
            return -1;
        }
        total += sent;
    }
    return total;
}

static int HttpPostJson(const char *path, const char *json, char *response, int responseLen)
{
    char request[HTTP_TX_BUF_SIZE];
    const char *deviceToken = GetDeviceToken();
    int bodyLen = strlen(json);

    if (deviceToken[0] == '\0') {
        printf("[bearpi-lab] empty device token\r\n");
        return -1;
    }

    int sock = ConnectTcp();
    if (sock < 0) {
        return -1;
    }

    int requestLen = snprintf(
        request,
        sizeof(request),
        "POST %s HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Connection: close\r\n"
        "Content-Type: application/json\r\n"
        "X-Device-Token: %s\r\n"
        "Content-Length: %d\r\n"
        "\r\n"
        "%s",
        path,
        g_activeServerHost,
        BEARPI_SERVER_PORT,
        deviceToken,
        bodyLen,
        json
    );

    if (requestLen <= 0 || requestLen >= (int)sizeof(request)) {
        printf("[bearpi-lab] http request too long\r\n");
        CloseSocket(sock);
        return -1;
    }

    int sent = SendAll(sock, request, requestLen);
    if (sent != requestLen) {
        printf("[bearpi-lab] send failed: %d/%d\r\n", sent, requestLen);
        CloseSocket(sock);
        return -1;
    }

    int total = 0;
    while (total < responseLen - 1) {
        int n = recv(sock, response + total, responseLen - 1 - total, 0);
        if (n <= 0) {
            break;
        }
        total += n;
    }
    response[total] = '\0';
    CloseSocket(sock);

    char *lineEnd = strstr(response, "\r\n");
    int statusOk = 0;
    if (lineEnd != NULL) {
        char saved = *lineEnd;
        *lineEnd = '\0';
        if (strstr(response, " 200 ") != NULL || strstr(response, " 201 ") != NULL) {
            statusOk = 1;
        }
        *lineEnd = saved;
    } else {
        if (strstr(response, " 200 ") != NULL || strstr(response, " 201 ") != NULL) {
            statusOk = 1;
        }
    }
    if (!statusOk) {
        printf("[bearpi-lab] http response not ok:\r\n%s\r\n", response);
        return -1;
    }

    return 0;
}

static int ResolveOverride(int autoValue, int overrideValue)
{
    return overrideValue == ACTUATOR_AUTO ? autoValue : overrideValue;
}

static void ApplyActuators(int motorOn, int fillLightOn)
{
    Motor_StatusSet(motorOn ? ON : OFF);
    Light_StatusSet(fillLightOn ? ON : OFF);
}

static float SetEstimatedModulePower(SensorSnapshot *s)
{
    s->powerMcu = 250.0f;
    s->powerWifi = 120.0f;
    s->powerSensor = 35.0f;
    s->powerMotor = s->motorOn ? 600.0f : 0.0f;
    s->powerLight = s->fillLightOn ? 150.0f : 0.0f;
    return s->powerMcu + s->powerWifi + s->powerSensor + s->powerMotor + s->powerLight;
}

static void ScaleModulePowerToTotal(SensorSnapshot *s, float totalPower)
{
    float estimatedTotal = s->powerMcu + s->powerWifi + s->powerSensor + s->powerMotor + s->powerLight;
    if (estimatedTotal <= 0.01f || totalPower <= 0.01f) {
        return;
    }

    float scale = totalPower / estimatedTotal;
    s->powerMcu *= scale;
    s->powerWifi *= scale;
    s->powerSensor *= scale;
    s->powerMotor *= scale;
    s->powerLight *= scale;
}

#if BEARPI_VOLTAGE_ADC_ENABLE || BEARPI_CURRENT_ADC_ENABLE
static int ReadAdcInputVoltage(WifiIotAdcChannelIndex channel, float *voltage)
{
    unsigned int ret;
    unsigned short data;
    float rawSum = 0.0f;
    int okCount = 0;

    for (int i = 0; i < BEARPI_POWER_ADC_SAMPLES; i++) {
        ret = AdcRead(channel, &data, WIFI_IOT_ADC_EQU_MODEL_8, WIFI_IOT_ADC_CUR_BAIS_DEFAULT, 0xff);
        if (ret == WIFI_IOT_SUCCESS) {
            rawSum += (float)data;
            okCount++;
        }
        usleep(1000);
    }

    if (okCount == 0) {
        printf("[bearpi-lab] adc channel %d read failed\r\n", channel);
        return 0;
    }

    *voltage = (rawSum / okCount) * BEARPI_ADC_REF_VOLTAGE * BEARPI_ADC_SAMPLE_SCALE / BEARPI_ADC_MAX_RAW;
    return 1;
}
#endif

static int TryReadSupplyVoltage(float *voltage)
{
#if BEARPI_VOLTAGE_ADC_ENABLE
    float inputVoltage = 0.0f;
    if (!ReadAdcInputVoltage(BEARPI_VOLTAGE_ADC_CHANNEL, &inputVoltage)) {
        return 0;
    }
    *voltage = inputVoltage * BEARPI_VOLTAGE_DIVIDER_RATIO;
    return *voltage > 0.01f;
#else
    (void)voltage;
    return 0;
#endif
}

static int TryReadBoardCurrent(float *current)
{
#if BEARPI_CURRENT_ADC_ENABLE
    float inputVoltage = 0.0f;
    float currentA = 0.0f;
    if (!ReadAdcInputVoltage(BEARPI_CURRENT_ADC_CHANNEL, &inputVoltage)) {
        return 0;
    }
    if (BEARPI_CURRENT_SENSE_SHUNT_OHMS <= 0.0f || BEARPI_CURRENT_SENSE_GAIN <= 0.0f) {
        return 0;
    }
    currentA = (inputVoltage - BEARPI_CURRENT_SENSE_ZERO_VOLTAGE)
        / (BEARPI_CURRENT_SENSE_SHUNT_OHMS * BEARPI_CURRENT_SENSE_GAIN);
    if (currentA < 0.0f) {
        currentA = 0.0f;
    }
    *current = currentA * 1000.0f;
    return 1;
#else
    (void)current;
    return 0;
#endif
}

static SensorSnapshot ReadSensorSnapshot(void)
{
    SensorSnapshot s;
    memset(&s, 0, sizeof(s));

    E53_IA1_Read_Data();
    s.temp = E53_IA1_Data.Temperature;
    s.hum = E53_IA1_Data.Humidity;
    s.light = E53_IA1_Data.Lux;

    int motorAuto = (s.temp > BEARPI_TEMP_HIGH_THRESHOLD || s.hum > BEARPI_HUM_HIGH_THRESHOLD) ? ACTUATOR_ON : ACTUATOR_OFF;
    int fillLightAuto = (s.light < BEARPI_LIGHT_LOW_THRESHOLD) ? ACTUATOR_ON : ACTUATOR_OFF;
    s.motorOn = ResolveOverride(motorAuto, g_motorOverride);
    s.fillLightOn = ResolveOverride(fillLightAuto, g_lightOverride);

    float estimatedPower = SetEstimatedModulePower(&s);
    s.voltage = BEARPI_ESTIMATED_SUPPLY_VOLTAGE;
    s.power = estimatedPower;
    s.current = s.power / s.voltage;
    s.voltageSampled = TryReadSupplyVoltage(&s.voltage);
    if (s.voltageSampled && s.voltage > 0.01f) {
        s.current = estimatedPower / s.voltage;
    }
    s.currentSampled = TryReadBoardCurrent(&s.current);
    if (s.currentSampled) {
        s.power = s.voltage * s.current;
        s.powerSampled = 1;
        ScaleModulePowerToTotal(&s, s.power);
    } else if (s.voltage > 0.01f) {
        s.power = estimatedPower;
        s.current = s.power / s.voltage;
    }

    ApplyActuators(s.motorOn, s.fillLightOn);
    return s;
}

static int ReportTelemetry(void)
{
    char json[JSON_BUF_SIZE];
    char response[HTTP_RX_BUF_SIZE];
    SensorSnapshot s = ReadSensorSnapshot();

    int jsonLen = snprintf(
        json,
        sizeof(json),
        "{\"sn\":\"%s\",\"metrics\":{\"temp\":%.2f,\"hum\":%.2f,\"light\":%.2f,\"motor\":%d,\"voltage\":%.2f,\"current\":%.2f,\"power\":%.2f,\"voltage_sampled\":%d,\"current_sampled\":%d,\"power_sampled\":%d,\"power_mcu\":%.2f,\"power_wifi\":%.2f,\"power_sensor\":%.2f,\"power_motor\":%.2f,\"power_light\":%.2f}}",
        BEARPI_DEVICE_SN,
        s.temp,
        s.hum,
        s.light,
        s.motorOn,
        s.voltage,
        s.current,
        s.power,
        s.voltageSampled,
        s.currentSampled,
        s.powerSampled,
        s.powerMcu,
        s.powerWifi,
        s.powerSensor,
        s.powerMotor,
        s.powerLight
    );

    if (jsonLen <= 0 || jsonLen >= (int)sizeof(json)) {
        printf("[bearpi-lab] telemetry json too long\r\n");
        return -1;
    }

    int ret = HttpPostJson("/api/v1/ingest/telemetry", json, response, sizeof(response));
    printf("[bearpi-lab] ingest %s temp=%.2f hum=%.2f light=%.2f motor=%s fill_light=%s voltage=%.2fV current=%.2fmA power=%.2fmW source=%s module=%.2f/%.2f/%.2f/%.2f/%.2f\r\n",
        ret == 0 ? "ok" : "failed",
        s.temp,
        s.hum,
        s.light,
        s.motorOn ? "ON" : "OFF",
        s.fillLightOn ? "ON" : "OFF",
        s.voltage,
        s.current,
        s.power,
        s.powerSampled ? "ADC" : "estimate",
        s.powerMcu,
        s.powerWifi,
        s.powerSensor,
        s.powerMotor,
        s.powerLight);
    return ret;
}

static int ExtractFirstCommandId(const char *response)
{
    const char *id = strstr(response, "\"id\":");
    if (id == NULL) {
        return 0;
    }
    return atoi(id + 5);
}

static const char *FindJsonStringValue(const char *json, const char *key)
{
    const char *keyPos = strstr(json, key);
    if (keyPos == NULL) {
        return NULL;
    }

    const char *colon = strchr(keyPos, ':');
    if (colon == NULL) {
        return NULL;
    }

    const char *quote = strchr(colon, '"');
    if (quote == NULL) {
        return NULL;
    }
    return quote + 1;
}

static int ExtractJsonString(const char *json, const char *key, char *value, int valueLen)
{
    const char *start = FindJsonStringValue(json, key);
    if (start == NULL) {
        return 0;
    }

    const char *end = strchr(start, '"');
    if (end == NULL) {
        return 0;
    }

    int len = end - start;
    if (len <= 0 || len >= valueLen) {
        return 0;
    }

    memcpy(value, start, len);
    value[len] = '\0';
    return 1;
}

static long long DaysFromCivil(int year, int month, int day)
{
    year -= month <= 2;
    int era = (year >= 0 ? year : year - 399) / 400;
    unsigned yoe = (unsigned)(year - era * 400);
    unsigned monthPart = (unsigned)(month + (month > 2 ? -3 : 9));
    unsigned doy = (153 * monthPart + 2) / 5 + (unsigned)day - 1;
    unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return (long long)era * 146097 + (long long)doe - 719468;
}

static int ParseIsoMillis(const char *text, long long *millis)
{
    int year = 0;
    int month = 0;
    int day = 0;
    int hour = 0;
    int minute = 0;
    int second = 0;
    int consumed = 0;
    int fraction = 0;
    int fractionDigits = 0;

    if (sscanf(text, "%d-%d-%dT%d:%d:%d%n", &year, &month, &day, &hour, &minute, &second, &consumed) != 6) {
        return 0;
    }

    const char *cursor = text + consumed;
    if (*cursor == '.') {
        cursor++;
        while (*cursor >= '0' && *cursor <= '9') {
            if (fractionDigits < 3) {
                fraction = fraction * 10 + (*cursor - '0');
                fractionDigits++;
            }
            cursor++;
        }
    }
    while (fractionDigits < 3) {
        fraction *= 10;
        fractionDigits++;
    }

    long long days = DaysFromCivil(year, month, day);
    *millis = (((days * 24 + hour) * 60 + minute) * 60 + second) * 1000 + fraction;
    return 1;
}

static int ComputeSyncWaitMs(const char *response)
{
    char executeAt[ISO_TIME_BUF_SIZE];
    char serverTime[ISO_TIME_BUF_SIZE];
    long long executeMillis = 0;
    long long serverMillis = 0;
    long long waitMs = 0;

    if (!ExtractJsonString(response, "execute_at", executeAt, sizeof(executeAt))) {
        return 0;
    }
    if (!ExtractJsonString(response, "serverTime", serverTime, sizeof(serverTime))) {
        return 0;
    }
    if (!ParseIsoMillis(executeAt, &executeMillis) || !ParseIsoMillis(serverTime, &serverMillis)) {
        printf("[bearpi-lab] sync time parse failed execute_at=%s serverTime=%s\r\n", executeAt, serverTime);
        return 0;
    }

    waitMs = executeMillis - serverMillis;
    if (waitMs <= 0) {
        return 0;
    }
    if (waitMs > MAX_SYNC_WAIT_MS) {
        printf("[bearpi-lab] sync wait too long %lldms, cap to %dms\r\n", waitMs, MAX_SYNC_WAIT_MS);
        return MAX_SYNC_WAIT_MS;
    }
    return (int)waitMs;
}

static void WaitForSyncExecuteAt(const char *response)
{
    int waitMs = ComputeSyncWaitMs(response);
    if (waitMs <= 0) {
        return;
    }

    printf("[bearpi-lab] sync wait %dms before actuator update\r\n", waitMs);
    usleep(waitMs * 1000);
}

static const char *FindJsonValueEnd(const char *start)
{
    const char *comma = strchr(start, ',');
    const char *brace = strchr(start, '}');
    if (comma == NULL) {
        return brace;
    }
    if (brace == NULL) {
        return comma;
    }
    return comma < brace ? comma : brace;
}

static int HasParamValue(const char *json, const char *key, const char *value)
{
    const char *keyPos = strstr(json, key);
    if (keyPos == NULL) {
        return 0;
    }

    const char *colon = strchr(keyPos, ':');
    if (colon == NULL) {
        return 0;
    }

    const char *end = FindJsonValueEnd(colon);
    const char *valuePos = strstr(colon, value);
    return valuePos != NULL && (end == NULL || valuePos < end);
}

static int ApplyOverrideValue(const char *response, const char *key, int *target)
{
    if (HasParamValue(response, key, "auto")) {
        *target = ACTUATOR_AUTO;
        return 1;
    }
    if (HasParamValue(response, key, "on")) {
        *target = ACTUATOR_ON;
        return 1;
    }
    if (HasParamValue(response, key, "off")) {
        *target = ACTUATOR_OFF;
        return 1;
    }
    return 0;
}

static int ApplyActuatorCommand(const char *response)
{
    int changed = 0;
    changed |= ApplyOverrideValue(response, "motor_override", &g_motorOverride);
    changed |= ApplyOverrideValue(response, "light_override", &g_lightOverride);

    if (changed) {
        printf("[bearpi-lab] override motor=%d light=%d\r\n", g_motorOverride, g_lightOverride);
    }
    return changed;
}
static int AckCommand(int commandId, const char *status, const char *message)
{
    char json[JSON_BUF_SIZE];
    char response[HTTP_RX_BUF_SIZE];

    int jsonLen = snprintf(
        json,
        sizeof(json),
        "{\"sn\":\"%s\",\"command_id\":%d,\"status\":\"%s\",\"message\":\"%s\"}",
        BEARPI_DEVICE_SN,
        commandId,
        status,
        message
    );

    if (jsonLen <= 0 || jsonLen >= (int)sizeof(json)) {
        printf("[bearpi-lab] ack json too long\r\n");
        return -1;
    }

    int ret = HttpPostJson("/api/v1/device/commands/ack", json, response, sizeof(response));
    printf("[bearpi-lab] ack command_id=%d ret=%d\r\n", commandId, ret);
    return ret;
}

static int PullAndAckCommand(void)
{
    char json[JSON_BUF_SIZE];
    char response[HTTP_RX_BUF_SIZE];

    int jsonLen = snprintf(
        json,
        sizeof(json),
        "{\"sn\":\"%s\",\"limit\":%d}",
        BEARPI_DEVICE_SN,
        BEARPI_COMMAND_LIMIT
    );

    if (jsonLen <= 0 || jsonLen >= (int)sizeof(json)) {
        printf("[bearpi-lab] pull json too long\r\n");
        return -1;
    }

    int ret = HttpPostJson("/api/v1/device/commands/pull", json, response, sizeof(response));
    if (ret != 0) {
        printf("[bearpi-lab] pull failed\r\n");
        return ret;
    }

    int commandId = ExtractFirstCommandId(response);
    if (commandId <= 0) {
        printf("[bearpi-lab] no queued command\r\n");
        return 0;
    }

    printf("[bearpi-lab] pulled command_id=%d\r\n", commandId);
    if (ApplyActuatorCommand(response)) {
        WaitForSyncExecuteAt(response);
        ReadSensorSnapshot();
        return AckCommand(commandId, "acked", "IA1 actuator override updated");
    }
    return AckCommand(commandId, "acked", "BearPi command executed");
}

static void BearPiLabTask(void)
{
    int consecutiveFailures = 0;
    const int MAX_CONSECUTIVE_FAILURES = 5;

    printf("[bearpi-lab] starting\r\n");
    printf("[bearpi-lab] wifi ssid=%s\r\n", BEARPI_WIFI_SSID);
    printf("[bearpi-lab] server=%s:%d fallback=%s sn=%s\r\n",
        BEARPI_SERVER_HOST,
        BEARPI_SERVER_PORT,
        strlen(BEARPI_SERVER_HOST_FALLBACK) > 0 ? BEARPI_SERVER_HOST_FALLBACK : "none",
        BEARPI_DEVICE_SN);

    WifiConnect(BEARPI_WIFI_SSID, BEARPI_WIFI_PASSWORD);
    E53_IA1_Init();

    while (1) {
        int telemetryOk = (ReportTelemetry() == 0);
        int commandOk = (PullAndAckCommand() == 0);

        if (telemetryOk && commandOk) {
            consecutiveFailures = 0;
        } else {
            consecutiveFailures++;
            printf("[bearpi-lab] consecutive failures: %d/%d\r\n", consecutiveFailures, MAX_CONSECUTIVE_FAILURES);
        }

        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
            printf("[bearpi-lab] too many failures, attempting WiFi reconnect...\r\n");
            WifiConnect(BEARPI_WIFI_SSID, BEARPI_WIFI_PASSWORD);
            consecutiveFailures = 0;
        }

        /* Simple backoff: sleep longer on repeated failures */
        int backoffMs = BEARPI_REPORT_INTERVAL_MS * (1 + consecutiveFailures);
        usleep(backoffMs * 1000);
    }
}

static void BearPiLabEntry(void)
{
    osThreadAttr_t attr;

    attr.name = "BearPiLabTask";
    attr.attr_bits = 0U;
    attr.cb_mem = NULL;
    attr.cb_size = 0U;
    attr.stack_mem = NULL;
    attr.stack_size = TASK_STACK_SIZE;
    attr.priority = TASK_PRIO;

    if (osThreadNew((osThreadFunc_t)BearPiLabTask, NULL, &attr) == NULL) {
        printf("[bearpi-lab] failed to create task\r\n");
    }
}

APP_FEATURE_INIT(BearPiLabEntry);
