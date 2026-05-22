#include <stdio.h>
#include <unistd.h>

#include "cmsis_os2.h"
#include "ohos_init.h"
#include "wifiiot_gpio.h"
#include "wifiiot_gpio_ex.h"
#include "wifiiot_pwm.h"

#define PWM_TASK_STACK_SIZE 512
#define PWM_TASK_PRIO 25
#define PWM_FREQ 40000
#define PWM_DUTY_STEP 100
#define PWM_DELAY_US 10

static void PwmTask(void *argument)
{
    (void)argument;
    unsigned int duty;

    GpioInit();
    IoSetFunc(WIFI_IOT_IO_NAME_GPIO_2, WIFI_IOT_IO_FUNC_GPIO_2_PWM2_OUT);
    GpioSetDir(WIFI_IOT_GPIO_IDX_2, WIFI_IOT_GPIO_DIR_OUT);
    PwmInit(WIFI_IOT_PWM_PORT_PWM2);

    while (1) {
        for (duty = 0; duty < PWM_FREQ; duty += PWM_DUTY_STEP) {
            PwmStart(WIFI_IOT_PWM_PORT_PWM2, duty, PWM_FREQ);
            usleep(PWM_DELAY_US);
        }
    }
}

static void PwmExampleEntry(void)
{
    osThreadAttr_t attr = {
        .name = "PwmTask",
        .attr_bits = 0U,
        .cb_mem = NULL,
        .cb_size = 0U,
        .stack_mem = NULL,
        .stack_size = PWM_TASK_STACK_SIZE,
        .priority = PWM_TASK_PRIO,
    };

    if (osThreadNew(PwmTask, NULL, &attr) == NULL) {
        printf("Failed to create PwmTask!\r\n");
    }
}

APP_FEATURE_INIT(PwmExampleEntry);