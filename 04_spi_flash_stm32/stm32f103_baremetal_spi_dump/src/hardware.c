#include "hardware.h"

/* Reset clock is HSI 8 MHz. APB2 = 8 MHz, SPI1 SCK = 8 MHz / 16 = 500 kHz.
 * USART1 BRR=69 gives about 115942 baud (0.64% error before HSI tolerance).
 * The host checks CRC32 to detect serial corruption. */
void hardware_init(void) {
    RCC_CR |= 1u;                          /* HSI on */
    while ((RCC_CR & (1u << 1)) == 0u) {} /* HSIRDY */
    RCC_CFGR = 0u;                        /* SYSCLK=HSI, prescalers /1 */
    while ((RCC_CFGR & (3u << 2)) != 0u) {}

    RCC_APB2ENR |= (1u << 0) | (1u << 2) | (1u << 12) | (1u << 14);
    AFIO_MAPR &= ~((1u << 0) | (1u << 2)); /* SPI1/USART1 no remap */

    GPIOA_BSRR = 1u << 4;                 /* /CS idle HIGH first */
    GPIOA_CRL = (GPIOA_CRL & ~((15u << 16) | (15u << 20) |
                                (15u << 24) | (15u << 28))) |
                (2u << 16) |             /* PA4 output push-pull, 2 MHz */
                (11u << 20) |            /* PA5 SPI1 SCK, AF push-pull */
                (4u << 24) |             /* PA6 SPI1 MISO, floating input */
                (11u << 28);             /* PA7 SPI1 MOSI, AF push-pull */
    GPIOA_CRH = (GPIOA_CRH & ~((15u << 4) | (15u << 8))) |
                (11u << 4) |             /* PA9 USART1 TX, AF push-pull */
                (4u << 8);               /* PA10 USART1 RX, floating input */

    SPI1_CR1 = (1u << 2) | (3u << 3) | (1u << 8) | (1u << 9);
    /* MSTR; BR=011 (/16); SSI=SSM=1; CPOL=CPHA=0, 8-bit, MSB first. */
    SPI1_CR2 = 0u;
    SPI1_CR1 |= 1u << 6;                  /* SPE */

    USART1_CR1 = 0u;
    USART1_CR2 = 0u;                      /* one stop bit */
    USART1_CR3 = 0u;                      /* no flow control */
    USART1_BRR = 69u;                    /* 115200 nominal, PCLK2=8 MHz */
    USART1_CR1 = (1u << 13) | (1u << 3) | (1u << 2); /* UE, TE, RE */
}

void uart_put(uint8_t value) {
    while ((USART1_SR & (1u << 7)) == 0u) {} /* TXE */
    USART1_DR = value;
}

uint8_t uart_get(void) {
    for (;;) {
        uint32_t status = USART1_SR;
        if (status & (1u << 5)) {           /* RXNE */
            uint8_t value = (uint8_t)USART1_DR;
            if ((status & ((1u << 3) | (1u << 2) | (1u << 1) | 1u)) == 0u)
                return value;              /* no ORE, NE, FE, PE */
        }
    }
}

void uart_flush(void) {
    while ((USART1_SR & (1u << 6)) == 0u) {} /* TC */
}
