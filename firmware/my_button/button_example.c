#include <stdio.h>

#include "ohos_init.h"
#include "wifiiot_gpio.h"
#include "wifiiot_gpio_ex.h"

static void F1Pressed(char *arg)
{
    (void)arg;
    GpioSetOutputVal(WIFI_IOT_GPIO_IDX_2, 1);
}

static void F2Pressed(char *arg)
{
    (void)arg;
    GpioSetOutputVal(WIFI_IOT_GPIO_IDX_2, 0);
}

static void ButtonExampleEntry(void)
{
    GpioInit();

    IoSetFunc(WIFI_IOT_IO_NAME_GPIO_2, WIFI_IOT_IO_FUNC_GPIO_2_GPIO);
    GpioSetDir(WIFI_IOT_GPIO_IDX_2, WIFI_IOT_GPIO_DIR_OUT);
    GpioSetOutputVal(WIFI_IOT_GPIO_IDX_2, 0);

    IoSetFunc(WIFI_IOT_IO_NAME_GPIO_11, WIFI_IOT_IO_FUNC_GPIO_11_GPIO);
    GpioSetDir(WIFI_IOT_GPIO_IDX_11, WIFI_IOT_GPIO_DIR_IN);
    IoSetPull(WIFI_IOT_IO_NAME_GPIO_11, WIFI_IOT_IO_PULL_UP);
    GpioRegisterIsrFunc(WIFI_IOT_GPIO_IDX_11, WIFI_IOT_INT_TYPE_EDGE,
        WIFI_IOT_GPIO_EDGE_FALL_LEVEL_LOW, F1Pressed, NULL);

    IoSetFunc(WIFI_IOT_IO_NAME_GPIO_12, WIFI_IOT_IO_FUNC_GPIO_12_GPIO);
    GpioSetDir(WIFI_IOT_GPIO_IDX_12, WIFI_IOT_GPIO_DIR_IN);
    IoSetPull(WIFI_IOT_IO_NAME_GPIO_12, WIFI_IOT_IO_PULL_UP);
    GpioRegisterIsrFunc(WIFI_IOT_GPIO_IDX_12, WIFI_IOT_INT_TYPE_EDGE,
        WIFI_IOT_GPIO_EDGE_FALL_LEVEL_LOW, F2Pressed, NULL);

    printf("Button example started. Press F1 to turn LED on, F2 to turn LED off.\r\n");
}

APP_FEATURE_INIT(ButtonExampleEntry);