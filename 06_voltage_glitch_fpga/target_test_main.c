#include <stdio.h>
#include "pico/stdlib.h"

#define EXPECTED_VALUE 0x7FA8D653u

volatile uint32_t test_value = 0;
volatile uint32_t test_stage = 0;

__attribute__((noinline))
void test_sequence(void)
{
    test_stage = 1;
    test_value = 0x12345678u;

    asm volatile("nop\n" "nop\n" "nop\n" "nop\n");

    test_stage = 2;
    test_value ^= 0xA5A5A5A5u;

    asm volatile("nop\n" "nop\n" "nop\n" "nop\n");

    test_stage = 3;
    test_value += 0x11111111u;

    asm volatile("nop\n" "nop\n" "nop\n" "nop\n");

    test_stage = 4;
    test_value ^= 0x5A5A5A5Au;

    asm volatile("nop\n" "nop\n" "nop\n" "nop\n");

    test_stage = 5;
    test_value -= 0x01020304u;

    asm volatile("nop\n" "nop\n" "nop\n" "nop\n");

    test_stage = 6;
    test_value += 0x0F0E0D0Cu;

    asm volatile("nop\n" "nop\n" "nop\n" "nop\n");

    test_stage = 7;
    test_value ^= 0xDEADBEEFu;

    test_stage = 8;
}

int main()
{
    stdio_init_all();

    /* Give Windows time to enumerate USB CDC. */
    sleep_ms(2000);

    printf("\r\n");
    printf("====================================\r\n");
    printf(" RP2040-Zero USB TEST v1\r\n");
    printf("====================================\r\n");
    printf("[BOOT] RP2040 started\r\n");
    printf("[BOOT] Expected value: 0x%08lX\r\n",
           (unsigned long)EXPECTED_VALUE);
    printf("\r\n");

    uint32_t test_number = 0;

    while (true)
    {
        test_number++;

        test_value = 0;
        test_stage = 0;

        printf("[BEGIN] test=%lu\r\n", (unsigned long)test_number);

        test_sequence();

        if ((test_stage != 8) || (test_value != EXPECTED_VALUE))
        {
            printf("\r\n");
            printf("!!!!!!!! ANOMALY !!!!!!!!\r\n");

            printf(
                "test  = %lu\r\n"
                "stage = %lu\r\n"
                "value = 0x%08lX\r\n"
                "expected = 0x%08lX\r\n",
                (unsigned long)test_number,
                (unsigned long)test_stage,
                (unsigned long)test_value,
                (unsigned long)EXPECTED_VALUE
            );

            printf("!!!!!!!!!!!!!!!!!!!!!!!!!\r\n");
            printf("\r\n");

            while (true)
            {
                printf(
                    "[ANOMALY LATCHED] stage=%lu value=0x%08lX\r\n",
                    (unsigned long)test_stage,
                    (unsigned long)test_value
                );

                sleep_ms(1000);
            }
        }

        printf(
            "[OK] test=%lu stage=%lu value=0x%08lX\r\n",
            (unsigned long)test_number,
            (unsigned long)test_stage,
            (unsigned long)test_value
        );

        sleep_ms(250);
    }
}
