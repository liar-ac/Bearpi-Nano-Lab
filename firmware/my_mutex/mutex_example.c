#include <stdio.h>

#include "cmsis_os2.h"
#include "ohos_init.h"

static osMutexId_t g_mutexId = NULL;

static void HighPrioThread(void *argument)
{
    (void)argument;

    osDelay(100U);
    while (1) {
        osMutexAcquire(g_mutexId, osWaitForever);
        printf("HighPrioThread is runing.\r\n");
        osDelay(300U);
        osMutexRelease(g_mutexId);
    }
}

static void MidPrioThread(void *argument)
{
    (void)argument;

    osDelay(100U);
    while (1) {
        printf("MidPrioThread is runing.\r\n");
        osDelay(100U);
    }
}

static void LowPrioThread(void *argument)
{
    (void)argument;

    while (1) {
        osMutexAcquire(g_mutexId, osWaitForever);
        printf("LowPrioThread is runing.\r\n");
        osDelay(300U);
        osMutexRelease(g_mutexId);
    }
}

static void MutexExample(void)
{
    osThreadAttr_t attr = {
        .attr_bits = 0U,
        .cb_mem = NULL,
        .cb_size = 0U,
        .stack_mem = NULL,
        .stack_size = 1024 * 4,
    };

    g_mutexId = osMutexNew(NULL);
    if (g_mutexId == NULL) {
        printf("Failed to create Mutex!\r\n");
        return;
    }

    attr.name = "HighPrioThread";
    attr.priority = 26;
    if (osThreadNew(HighPrioThread, NULL, &attr) == NULL) {
        printf("Failed to create HighPrioThread!\r\n");
    }

    attr.name = "MidPrioThread";
    attr.priority = 25;
    if (osThreadNew(MidPrioThread, NULL, &attr) == NULL) {
        printf("Failed to create MidPrioThread!\r\n");
    }

    attr.name = "LowPrioThread";
    attr.priority = 24;
    if (osThreadNew(LowPrioThread, NULL, &attr) == NULL) {
        printf("Failed to create LowPrioThread!\r\n");
    }
}

APP_FEATURE_INIT(MutexExample);