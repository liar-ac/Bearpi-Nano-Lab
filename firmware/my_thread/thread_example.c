#include <stdio.h>
#include <unistd.h>

#include "cmsis_os2.h"
#include "ohos_init.h"

static void Thread1(void *argument)
{
    (void)argument;
    int count = 0;

    while (1) {
        printf("This is BearPi-HM_Nano Thread1----%d\r\n", count++);
        usleep(1000000);
    }
}

static void Thread2(void *argument)
{
    (void)argument;
    int count = 0;

    while (1) {
        printf("This is BearPi-HM_Nano Thread2----%d\r\n", count++);
        usleep(500000);
    }
}

static void ThreadExample(void)
{
    osThreadAttr_t attr = {
        .name = "thread1",
        .attr_bits = 0U,
        .cb_mem = NULL,
        .cb_size = 0U,
        .stack_mem = NULL,
        .stack_size = 1024 * 4,
        .priority = 25,
    };

    if (osThreadNew(Thread1, NULL, &attr) == NULL) {
        printf("Failed to create thread1!\r\n");
    }

    attr.name = "thread2";
    if (osThreadNew(Thread2, NULL, &attr) == NULL) {
        printf("Failed to create thread2!\r\n");
    }
}

APP_FEATURE_INIT(ThreadExample);