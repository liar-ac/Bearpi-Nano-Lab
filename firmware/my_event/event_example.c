#include <stdio.h>
#include <stdint.h>

#include "cmsis_os2.h"
#include "ohos_init.h"

#define FLAGS_MSK1 0x00000001U

static osEventFlagsId_t g_eventId = NULL;

static void ThreadEventSender(void *argument)
{
    (void)argument;

    while (1) {
        osEventFlagsSet(g_eventId, FLAGS_MSK1);
        osThreadYield();
        osDelay(100);
    }
}

static void ThreadEventReceiver(void *argument)
{
    (void)argument;
    uint32_t flags;

    while (1) {
        flags = osEventFlagsWait(g_eventId, FLAGS_MSK1, osFlagsWaitAny, osWaitForever);
        printf("Receive Flags is %u\r\n", flags);
    }
}

static void EventExample(void)
{
    osThreadAttr_t attr = {
        .attr_bits = 0U,
        .cb_mem = NULL,
        .cb_size = 0U,
        .stack_mem = NULL,
        .stack_size = 1024 * 4,
        .priority = 25,
    };

    g_eventId = osEventFlagsNew(NULL);
    if (g_eventId == NULL) {
        printf("Failed to create EventFlags!\r\n");
        return;
    }

    attr.name = "Thread_EventSender";
    if (osThreadNew(ThreadEventSender, NULL, &attr) == NULL) {
        printf("Failed to create Thread_EventSender!\r\n");
    }

    attr.name = "Thread_EventReceiver";
    if (osThreadNew(ThreadEventReceiver, NULL, &attr) == NULL) {
        printf("Failed to create Thread_EventReceiver!\r\n");
    }
}

APP_FEATURE_INIT(EventExample);