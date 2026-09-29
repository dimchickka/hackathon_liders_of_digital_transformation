#include "hardware.h"

#define CS_HIGH() (GPIOA_BSRR = (1u << 4))
#define CS_LOW()  (GPIOA_BSRR = (1u << 20))
#define SPI_TIMEOUT 1000000u

static bool spi_exchange(uint8_t output, uint8_t *input) {
    uint32_t remaining = SPI_TIMEOUT;
    while ((SPI1_SR & (1u << 1)) == 0u) { /* TXE */
        if (--remaining == 0u) return false;
    }
    SPI1_DR8 = output;
    remaining = SPI_TIMEOUT;
    while ((SPI1_SR & 1u) == 0u) {        /* RXNE */
        if (--remaining == 0u) return false;
    }
    *input = SPI1_DR8;
    return true;
}

static bool spi_finish(void) {
    uint32_t remaining = SPI_TIMEOUT;
    while (SPI1_SR & (1u << 7)) {        /* BSY */
        if (--remaining == 0u) return false;
    }
    return true;
}

bool flash_jedec(uint8_t id[3]) {
    uint8_t ignored;
    bool ok = true;
    CS_LOW();
    ok = spi_exchange(0x9Fu, &ignored);
    for (unsigned i = 0; ok && i < 3u; ++i)
        ok = spi_exchange(0xFFu, &id[i]);
    if (ok) ok = spi_finish();
    CS_HIGH();
    return ok;
}

bool flash_read(uint32_t address, uint8_t *data, uint16_t length) {
    uint8_t ignored;
    bool ok = true;
    CS_LOW();
    ok = spi_exchange(0x03u, &ignored);
    if (ok) ok = spi_exchange((uint8_t)(address >> 16), &ignored);
    if (ok) ok = spi_exchange((uint8_t)(address >> 8), &ignored);
    if (ok) ok = spi_exchange((uint8_t)address, &ignored);
    for (uint16_t i = 0; ok && i < length; ++i)
        ok = spi_exchange(0xFFu, &data[i]);
    if (ok) ok = spi_finish();
    CS_HIGH();
    return ok;
}
