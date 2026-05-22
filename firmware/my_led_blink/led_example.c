#include <stdio.h>
#include <unistd.h>

#include "cmsis_os2.h"
#include "ohos_init.h"
#include "wifiiot_gpio.h"
#include "wifiiot_gpio_ex.h"

#define LED_TASK_STACK_SIZE 512
#define LED_TASK_PRIO 25

static void LedTask(void *argument)
{
    (void)argument;

    GpioInit();
    IoSetFunc(WIFI_IOT_IO_NAME_GPIO_2, WIFI_IOT_IO_FUNC_GPIO_2_GPIO);
    GpioSetDir(WIFI_IOT_GPIO_IDX_2, WIFI_IOT_GPIO_DIR_OUT);

    while (1) {
        GpioSetOutputVal(WIFI_IOT_GPIO_IDX_2, 1);
        usleep(1000000);
        GpioSetOutputVal(WIFI_IOT_GPIO_IDX_2, 0);
        usleep(1000000);
    }
}

static void LedExampleEntry(void)
{
    osThreadAttr_t attr = {
        .name = "LedTask",
        .attr_bits = 0U,
        .cb_mem = NULL,
        .cb_size = 0U,
        .stack_mem = NULL,
        .stack_size = LED_TASK_STACK_SIZE,
        .priority = LED_TASK_PRIO,
    };

    if (osThreadNew(LedTask, NULL, &attr) == NULL) {
        printf("Failed to create LedTask!\r\n");
    }
}

APP_FEATURE_INIT(LedExampleEntry);