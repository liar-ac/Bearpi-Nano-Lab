#include <stdio.h>
#include <stdint.h>
#include <unistd.h>

#include "cmsis_os2.h"
#include "ohos_init.h"

static uint32_t g_timer1Arg;
static uint32_t g_timer2Arg;

static void Timer1Callback(void *arg)
{
    (void)arg;
    printf("This is BearPi Harmony Timer1_Callback!\r\n");
}

static void Timer2Callback(void *arg)
{
    (void)arg;
    printf("This is BearPi Harmony Timer2_Callback!\r\n");
}

static void TimerExample(void)
{
    osTimerId_t timer1Id;
    osTimerId_t timer2Id;
    osStatus_t status;

    g_timer1Arg = 1U;
    timer1Id = osTimerNew(Timer1Callback, osTimerPeriodic, &g_timer1Arg, NULL);
    if (timer1Id == NULL) {
        printf("Failed to create Timer1!\r\n");
        return;
    }

    /* Hi3861: 1 tick is 10 ms, so 100 ticks is 1 second. */
    status = osTimerStart(timer1Id, 100U);
    if (status != osOK) {
        printf("Failed to start Timer1!\r\n");
    }

    g_timer2Arg = 1U;
    timer2Id = osTimerNew(Timer2Callback, osTimerPeriodic, &g_timer2Arg, NULL);
    if (timer2Id == NULL) {
        printf("Failed to create Timer2!\r\n");
        return;
    }

    /* Hi3861: 300 ticks is 3 seconds. */
    status = osTimerStart(timer2Id, 300U);
    if (status != osOK) {
        printf("Failed to start Timer2!\r\n");
    }
}

APP_FEATURE_INIT(TimerExample);