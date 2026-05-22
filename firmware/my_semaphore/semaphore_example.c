#include <stdio.h>

#include "cmsis_os2.h"
#include "ohos_init.h"

static osSemaphoreId_t g_semaphoreId = NULL;

static void Semaphore1Thread(void *argument)
{
    (void)argument;

    while (1) {
        osSemaphoreRelease(g_semaphoreId);
        osSemaphoreRelease(g_semaphoreId);
        printf("Thread_Semaphore1 Release  Semap \r\n");
        osDelay(100);
    }
}

static void Semaphore2Thread(void *argument)
{
    (void)argument;

    while (1) {
        osSemaphoreAcquire(g_semaphoreId, osWaitForever);
        printf("Thread_Semaphore2 get Semap \r\n");
        osDelay(1);
    }
}

static void Semaphore3Thread(void *argument)
{
    (void)argument;

    while (1) {
        osSemaphoreAcquire(g_semaphoreId, osWaitForever);
        printf("Thread_Semaphore3 get Semap \r\n");
        osDelay(1);
    }
}

static void SemaphoreExample(void)
{
    osThreadAttr_t attr = {
        .attr_bits = 0U,
        .cb_mem = NULL,
        .cb_size = 0U,
        .stack_mem = NULL,
        .stack_size = 1024 * 4,
        .priority = 24,
    };

    g_semaphoreId = osSemaphoreNew(4, 0, NULL);
    if (g_semaphoreId == NULL) {
        printf("Failed to create Semaphore!\r\n");
        return;
    }

    attr.name = "Thread_Semaphore1";
    if (osThreadNew(Semaphore1Thread, NULL, &attr) == NULL) {
        printf("Failed to create Thread_Semaphore1!\r\n");
    }

    attr.name = "Thread_Semaphore2";
    if (osThreadNew(Semaphore2Thread, NULL, &attr) == NULL) {
        printf("Failed to create Thread_Semaphore2!\r\n");
    }

    attr.name = "Thread_Semaphore3";
    if (osThreadNew(Semaphore3Thread, NULL, &attr) == NULL) {
        printf("Failed to create Thread_Semaphore3!\r\n");
    }
}

APP_FEATURE_INIT(SemaphoreExample);