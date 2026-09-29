#ifndef HARDWARE_H
#define HARDWARE_H

#include <stdint.h>
#include <stdbool.h>

#define REG32(address) (*(volatile uint32_t *)(address))
#define REG8(address)  (*(volatile uint8_t *)(address))

#define RCC_CR       REG32(0x40021000u)
#define RCC_CFGR     REG32(0x40021004u)
#define RCC_APB2ENR  REG32(0x40021018u)
#define AFIO_MAPR    REG32(0x40010004u)
#define GPIOA_CRL    REG32(0x40010800u)
#define GPIOA_CRH    REG32(0x40010804u)
#define GPIOA_BSRR   REG32(0x40010810u)

#define SPI1_CR1     REG32(0x40013000u)
#define SPI1_CR2     REG32(0x40013004u)
#define SPI1_SR      REG32(0x40013008u)
#define SPI1_DR8     REG8(0x4001300Cu)

#define USART1_SR    REG32(0x40013800u)
#define USART1_DR    REG32(0x40013804u)
#define USART1_BRR   REG32(0x40013808u)
#define USART1_CR1   REG32(0x4001380Cu)
#define USART1_CR2   REG32(0x40013810u)
#define USART1_CR3   REG32(0x40013814u)

void hardware_init(void);
void uart_put(uint8_t value);
uint8_t uart_get(void);
void uart_flush(void);
bool flash_jedec(uint8_t id[3]);
bool flash_read(uint32_t address, uint8_t *data, uint16_t length);

#endif
