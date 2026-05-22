#include <stdio.h>
#include "ohos_init.h"
#include "wifiiot_gpio.h"
#include "wifiiot_gpio_ex.h"

void LedExample(void)
{
    GpioInit();

    IoSetFunc(WIFI_IOT_IO_NAME_GPIO_2, WIFI_IOT_IO_FUNC_GPIO_2_GPIO);
    GpioSetDir(WIFI_IOT_GPIO_IDX_2, WIFI_IOT_GPIO_DIR_OUT);

    GpioSetOutputVal(WIFI_IOT_GPIO_IDX_2, 1);
    printf("[LED] GPIO_2 output high, LED on.\r\n");
}

APP_FEATURE_INIT(LedExample);
