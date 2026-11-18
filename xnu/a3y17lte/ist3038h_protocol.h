/* SPDX-License-Identifier: GPL-2.0-only */
/* IST3038H wire format, from Samsung imagis_30xxh sources. No firmware/NVM writes. */
#ifndef A3_IST3038H_PROTOCOL_H
#define A3_IST3038H_PROTOCOL_H
#include <stdint.h>

#define A3_IST_FINGERS 10
#define A3_IST_CHIP_ID_REG 0xc0001000u
#define A3_IST_INTR_REG 0xb00b0104u
#define A3_IST_COORD_BURST_REG 0xb80b0108u
#define A3_IST_CMD_REG 0xb00b011cu

struct a3_ist_frame {
    uint16_t mask;
    uint16_t x[A3_IST_FINGERS], y[A3_IST_FINGERS];
};

static inline uint32_t a3_ist_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}

/* 1 = complete frame, 0 = notification, -1 = corrupt/unsupported packet.
 * Validate the complete packet before exposing any contact to HID. */
static inline int a3_ist_decode(const uint32_t *words, unsigned count,
                                struct a3_ist_frame *out)
{
    if (!count) return -1;
    uint32_t status = words[0];
    if (status == 0x8ead8eadu || status == 0x8ca0d00eu ||
        status == 0xdbdb0000u || (status & 0xf0000fffu) == 0x80000cabu)
        return 0;
    if (!status || status == 0xffffffffu || !(status & 0x800u)) return -1;
    unsigned n = (status >> 12) & 15u, pop = 0;
    uint16_t mask = (uint16_t)(status & 0x3ffu);
    for (unsigned i = 0; i < A3_IST_FINGERS; ++i) pop += (mask >> i) & 1u;
    if (n > A3_IST_FINGERS || count != n + 1 || pop != n) return -1;
    unsigned checksum = 0;
    for (unsigned i = 0; i < count; ++i) {
        uint32_t w = i ? words[i] : status & 0xffffffu;
        for (unsigned b = 0; b < 4; ++b) checksum += (w >> (b * 8)) & 255u;
    }
    if ((checksum & 255u) != (status >> 24)) return -1;
    struct a3_ist_frame f = {0};
    f.mask = mask;
    for (unsigned slot = 0, index = 1; slot < A3_IST_FINGERS; ++slot) {
        if (!(mask & (1u << slot))) continue;
        uint32_t w = words[index++];
        unsigned x = (w >> 12) & 0xfffu, y = w & 0xfffu;
        if (x >= 720 || y >= 1280) return -1;
        f.x[slot] = (uint16_t)x;
        f.y[slot] = (uint16_t)y;
    }
    *out = f;
    return 1;
}
#endif
