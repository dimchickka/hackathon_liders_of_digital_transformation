#include <stdint.h>

extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss;
int main(void);
void Reset_Handler(void);
void Default_Handler(void);

void NMI_Handler(void)       __attribute__((weak, alias("Default_Handler")));
void HardFault_Handler(void) __attribute__((weak, alias("Default_Handler")));

/* All peripheral interrupts stay disabled. A complete Cortex-M3 core vector
 * prefix is provided so an unexpected fault reaches Default_Handler. */
__attribute__((section(".isr_vector"), used))
const void *const vector_table[16] = {
    &_estack, Reset_Handler, NMI_Handler, HardFault_Handler,
    Default_Handler, Default_Handler, Default_Handler, 0,
    0, 0, 0, Default_Handler,
    Default_Handler, 0, Default_Handler, Default_Handler
};

void Reset_Handler(void) {
    uint32_t *src = &_sidata;
    for (uint32_t *dst = &_sdata; dst < &_edata; ) *dst++ = *src++;
    for (uint32_t *dst = &_sbss; dst < &_ebss; ) *dst++ = 0;
    (void)main();
    for (;;) {}
}

void Default_Handler(void) {
    for (;;) {}
}
