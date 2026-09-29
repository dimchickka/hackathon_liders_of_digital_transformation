/* STM32F103C8T6 + STM32Cube HAL integration fragment.
 * SPI1: PA5 SCK, PA6 MISO, PA7 MOSI; PA4 /CS (GPIO output).
 * USART1: PA9 TX, 115200 8N1. Configure peripherals in CubeMX first.
 * Output: 3-byte JEDEC ID followed by exactly 0x200000 flash bytes.
 * NOT TESTED ON THE TARGET BOARD.
 */
#include "main.h"
#include <stdint.h>

extern SPI_HandleTypeDef hspi1;
extern UART_HandleTypeDef huart1;

#define FLASH_SIZE 0x200000UL
#define CS_LOW()  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_RESET)
#define CS_HIGH() HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET)

static HAL_StatusTypeDef flash_jedec(uint8_t id[3]) {
    uint8_t cmd = 0x9F;
    CS_LOW();
    HAL_StatusTypeDef s = HAL_SPI_Transmit(&hspi1, &cmd, 1, 1000);
    if (s == HAL_OK) s = HAL_SPI_Receive(&hspi1, id, 3, 1000);
    CS_HIGH();
    return s;
}

static HAL_StatusTypeDef flash_read(uint32_t address, uint8_t *dst, uint16_t len) {
    uint8_t cmd[4] = {0x03, (uint8_t)(address >> 16),
                      (uint8_t)(address >> 8), (uint8_t)address};
    CS_LOW();
    HAL_StatusTypeDef s = HAL_SPI_Transmit(&hspi1, cmd, 4, 1000);
    if (s == HAL_OK) s = HAL_SPI_Receive(&hspi1, dst, len, 1000);
    CS_HIGH();
    return s;
}

void dump_flash_over_uart(void) {
    uint8_t id[3], block[256];
    CS_HIGH();
    if (flash_jedec(id) != HAL_OK) Error_Handler();
    if (HAL_UART_Transmit(&huart1, id, sizeof(id), 1000) != HAL_OK) Error_Handler();
    for (uint32_t addr = 0; addr < FLASH_SIZE; addr += sizeof(block)) {
        if (flash_read(addr, block, sizeof(block)) != HAL_OK) Error_Handler();
        if (HAL_UART_Transmit(&huart1, block, sizeof(block), 5000) != HAL_OK) Error_Handler();
    }
}
