/* SPDX-License-Identifier: MIT */
/* Bluetooth H4 Command Complete for HCI Read Local Version Information. */
#ifndef A3_BT_PROTOCOL_H
#define A3_BT_PROTOCOL_H
#include <stdint.h>

struct a3_bt_version {
    uint8_t status, hci, lmp;
    uint16_t revision, manufacturer, subversion;
};

/* Return 0 for another event, -1 for malformed data, 1 for a matching reply. */
static inline int
a3_bt_decode_version(const uint8_t *p, unsigned size, struct a3_bt_version *out)
{
    if (size < 3 || p[0] != 4 || size != (unsigned)p[2] + 3) return -1;
    if (p[1] != 0x0e) return 0;
    if (size < 7) return -1;
    if (p[4] != 1 || p[5] != 0x10) return 0;
    struct a3_bt_version v = {0};
    v.status = p[6];
    if (!v.status) {
        if (size != 15) return -1;
        v.hci = p[7];
        v.revision = p[8] | (uint16_t)p[9] << 8;
        v.lmp = p[10];
        v.manufacturer = p[11] | (uint16_t)p[12] << 8;
        v.subversion = p[13] | (uint16_t)p[14] << 8;
    }
    *out = v;
    return 1;
}
#endif
