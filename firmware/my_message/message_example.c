#include <stdio.h>
#include <stdint.h>

#include "cmsis_os2.h"
#include "ohos_init.h"

#define MSGQUEUE_OBJECTS 16U

typedef struct {
    const char *buf;
    uint8_t idx;
} MessageQueueObj;

static osMessageQueueId_t g_msgQueueId = NULL;

static void MsgQueueSenderThread(void *argument)
{
    (void)argument;
    MessageQueueObj msg = {
        .buf = "Hello BearPi-HM_Nano!",
        .idx = 0U,
    };

    while (1) {
        osMessageQueuePut(g_msgQueueId, &msg, 0U, 0U);
        osThreadYield();
        osDelay(100U);
    }
}

static void MsgQueueReceiverThread(void *argument)
{
    (void)argument;
    MessageQueueObj msg;
    osStatus_t status;

    while (1) {
        status = osMessageQueueGet(g_msgQueueId, &msg, NULL, osWaitForever);
        if (status == osOK) {
            printf("Message Queue Get msg:%s\r\n", msg.buf);
        }
    }
}

static void MessageExample(void)
{
    osThreadAttr_t attr = {
        .attr_bits = 0U,
        .cb_mem = NULL,
        .cb_size = 0U,
        .stack_mem = NULL,
        .stack_size = 1024 * 10,
        .priority = 25,
    };

    g_msgQueueId = osMessageQueueNew(MSGQUEUE_OBJECTS, sizeof(MessageQueueObj), NULL);
    if (g_msgQueueId == NULL) {
        printf("Failed to create Message Queue!\r\n");
        return;
    }

    attr.name = "Thread_MsgQueue1";
    if (osThreadNew(MsgQueueSenderThread, NULL, &attr) == NULL) {
        printf("Failed to create Thread_MsgQueue1!\r\n");
    }

    attr.name = "Thread_MsgQueue2";
    if (osThreadNew(MsgQueueReceiverThread, NULL, &attr) == NULL) {
        printf("Failed to create Thread_MsgQueue2!\r\n");
    }
}

APP_FEATURE_INIT(MessageExample);