/* SPDX-License-Identifier: GPL-2.0-only
 * Experimental A3 IST3038H path included in a5xelte_touch.c by the A3-only patch.
 * Reuses bounded S3C I2C register helpers. Assumes clock, GPC2 mux and tsp_avdd
 * are already on; does not guess PMIC settings, reset or reflash the controller.
 * a3touch=1 opts in. The initial entry profile leaves this disabled.
 */
#if defined(A3Y17LTE)
#include "ist3038h_protocol.h"
static vm_offset_t a3t_bus, a3t_alive;
static uint16_t a3t_mask, a3t_x[A3_IST_FINGERS], a3t_y[A3_IST_FINGERS];

static bool a3t_step(void)
{
    a5touch_clear_irq(a3t_bus);
    return a5touch_wait_irq(a3t_bus);
}

static void a3t_stop(void)
{
    a5touch_write(a3t_bus, 4, a5touch_read(a3t_bus, 4) & ~0x20u);
    a5touch_clear_irq(a3t_bus);
    for (unsigned i = 0; i < 1000; ++i) {
        if (!(a5touch_read(a3t_bus, 4) & 0x20u)) break;
        delay(1);
    }
}

/* Combined write + repeated START + read, matching Linux i2c_transfer(2 msgs).
 * IST addresses and words are big endian, unlike Synaptics byte registers. */
static bool a3t_transfer(const uint8_t *tx, unsigned ntx, uint8_t *rx, unsigned nrx)
{
    if (!ntx || ntx > 8 || nrx > 40) return false;
    if (a5touch_read(a3t_bus, 4) & 0x20u) return false;
    bool ok = false;
    a5touch_write(a3t_bus, 0, 0xe3u);
    a5touch_write(a3t_bus, 0x10, 7u);
    a5touch_write(a3t_bus, 4, 0xd0u);
    a5touch_write(a3t_bus, 0xc, 0xa0u);
    a5touch_write(a3t_bus, 4, 0xf0u);
    if (!a5touch_wait_irq(a3t_bus) || (a5touch_read(a3t_bus, 4) & 1u)) goto out;
    for (unsigned i = 0; i < ntx; ++i) {
        a5touch_write(a3t_bus, 0xc, tx[i]);
        if (!a3t_step() || (a5touch_read(a3t_bus, 4) & 1u)) goto out;
    }
    if (nrx) {
        a5touch_write(a3t_bus, 0xc, 0xa1u);
        a5touch_write(a3t_bus, 4, 0xb0u);
        if (!a3t_step() || (a5touch_read(a3t_bus, 4) & 1u)) goto out;
        for (unsigned i = 0; i < nrx; ++i) {
            if (i + 1 == nrx) a5touch_write(a3t_bus, 0, 0x63u);
            if (!a3t_step()) goto out;
            rx[i] = (uint8_t)a5touch_read(a3t_bus, 0xc);
        }
    }
    ok = true;
out:
    a3t_stop();
    return ok;
}

static void a3t_put32(uint8_t *b, uint32_t w)
{
    for (unsigned i = 0; i < 4; ++i) b[i] = (uint8_t)(w >> (24 - 8 * i));
}

static bool a3t_read(uint32_t reg, uint32_t *words, unsigned count)
{
    uint8_t tx[4], rx[40];
    if (!count || count > 10) return false;
    a3t_put32(tx, reg);
    if (!a3t_transfer(tx, 4, rx, 4 * count)) return false;
    for (unsigned i = 0; i < count; ++i) words[i] = a3_ist_be32(rx + 4 * i);
    return true;
}

static void a3t_release(void)
{
    for (unsigned i = 0; i < A3_IST_FINGERS; ++i)
        if (a3t_mask & (1u << i)) sweet_hid_touch((int)i, 0, a3t_x[i], a3t_y[i]);
    a3t_mask = 0;
}

static void a3t_thread(void *arg, wait_result_t result)
{
    (void)arg; (void)result;
    uint32_t chip = 0;
    uint8_t tx[8];
    unsigned failures = 0, invalid = 0;
    j7t_sleep_ms(3000);
    a3t_bus = ml_io_map(0x13890000u, 0x1000);
    a3t_alive = ml_io_map(0x139f0000u, 0x1000);
    vm_offset_t pins = ml_io_map(0x139c0000u, 0x1000);
    if (!a3t_bus || !a3t_alive || !pins) goto done;
    if ((a5touch_read(pins, 0) & 0xffu) != 0x22u) {
        printf("A3 TOUCH: GPC2 not in I2C mode; live mux/clock/rail evidence needed\n");
        goto done;
    }
    if (!a3t_read(A3_IST_CHIP_ID_REG, &chip, 1) || (chip & 0xffffu) != 0x038du) {
        printf("A3 TOUCH: IST3038H not responding (chip=%#x); tsp_avdd/clock handoff unresolved\n", chip);
        goto done;
    }
    printf("A3 TOUCH: IST3038H chip=%#x; experimental scan start\n", chip);
    a3t_put32(tx, A3_IST_CMD_REG);
    a3t_put32(tx + 4, 0x00010001u); /* eHCOM_FW_START / enable, volatile command */
    if (!a3t_transfer(tx, 8, NULL, 0)) goto done;
    j7t_sleep_ms(40);
    for (;;) {
        if (a5touch_read(a3t_alive, 0x44) & (1u << 6)) {
            j7t_sleep_ms(8);
            continue;
        }
        uint32_t words[11] = {0};
        struct a3_ist_frame frame;
        if (!a3t_read(A3_IST_INTR_REG, words, 1)) {
            if (++failures >= 8) break;
            j7t_sleep_ms(20);
            continue;
        }
        unsigned n = (words[0] >> 12) & 15u;
        if (a3_ist_decode(words, 1, &frame) == 0) {
            if (words[0] == 0x8ead8eadu) a3t_release();
            j7t_sleep_ms(8);
            continue;
        }
        if (n > 10 || !(words[0] & 0x800u)) {
            if (++invalid >= 100) break;
            j7t_sleep_ms(8); continue;
        }
        if (n && !a3t_read(A3_IST_COORD_BURST_REG, words + 1, n)) {
            if (++failures >= 8) break;
            j7t_sleep_ms(20);
            continue;
        }
        failures = 0;
        int rc = a3_ist_decode(words, n + 1, &frame);
        if (rc == 1) {
            for (unsigned i = 0; i < A3_IST_FINGERS; ++i) {
                bool down = (frame.mask & (1u << i)) != 0;
                if (down) {
                    a3t_x[i] = frame.x[i]; a3t_y[i] = frame.y[i];
                    sweet_hid_touch((int)i, 1, a3t_x[i], a3t_y[i]);
                } else if (a3t_mask & (1u << i)) {
                    sweet_hid_touch((int)i, 0, a3t_x[i], a3t_y[i]);
                }
            }
            a3t_mask = frame.mask;
            invalid = 0;
        } else if (rc < 0) {
            if (++invalid <= 8) printf("A3 TOUCH: rejected frame status=%#x count=%u\n", words[0], n);
            if (invalid >= 100) break;
        }
        j7t_sleep_ms(4);
    }
done:
    a3t_release();
    thread_terminate_self();
}

static void a3y17lte_touch_start(void)
{
    int enabled = 0;
    thread_t thread;
    (void)PE_parse_boot_argn("a3touch", &enabled, sizeof(enabled));
    printf("A3Y17LTE_PORT_V1_720X1280_IST3038H touch=%d\n", enabled);
    if (enabled && kernel_thread_start_priority(a3t_thread, NULL, 28, &thread) == KERN_SUCCESS)
        thread_deallocate(thread);
}
#endif
