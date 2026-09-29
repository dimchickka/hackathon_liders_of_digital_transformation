#include "hardware.h"

#define FLASH_BYTES 0x200000u
#define BLOCK_BYTES 256u

static uint8_t block[BLOCK_BYTES];

static void put_u32_le(uint32_t value) {
    for (unsigned i = 0; i < 4u; ++i)
        uart_put((uint8_t)(value >> (8u * i)));
}

static uint32_t crc32_byte(uint32_t crc, uint8_t value) {
    crc ^= value;
    for (unsigned i = 0; i < 8u; ++i)
        crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    return crc;
}

static void send_marker(const char marker[4]) {
    for (unsigned i = 0; i < 4u; ++i) uart_put((uint8_t)marker[i]);
}

static void dump_once(void) {
    uint8_t id[3] = {0u, 0u, 0u};
    if (!flash_jedec(id) || id[0] != 0xEFu || id[1] != 0x40u || id[2] != 0x15u) {
        send_marker("ERR1");
        for (unsigned i = 0; i < 3u; ++i) uart_put(id[i]);
        uart_flush();
        return;
    }

    send_marker("RPF1");
    for (unsigned i = 0; i < 3u; ++i) uart_put(id[i]);
    put_u32_le(FLASH_BYTES);

    uint32_t crc = 0xFFFFFFFFu;
    for (uint32_t address = 0; address < FLASH_BYTES; address += BLOCK_BYTES) {
        if (!flash_read(address, block, BLOCK_BYTES)) {
            /* Incomplete data stream: host will time out and reject it. */
            uart_flush();
            return;
        }
        for (unsigned i = 0; i < BLOCK_BYTES; ++i) {
            crc = crc32_byte(crc, block[i]);
            uart_put(block[i]);
        }
    }
    put_u32_le(crc ^ 0xFFFFFFFFu);
    uart_flush();
}

int main(void) {
    hardware_init();
    /* The host sends 'D' after opening the UART. No startup text is emitted. */
    for (;;) {
        if (uart_get() == (uint8_t)'D') dump_once();
    }
}
