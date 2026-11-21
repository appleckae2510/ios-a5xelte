/* SPDX-License-Identifier: GPL-2.0-only */
/* SM-A320FL early console. See Samsung's decon_7870/{regs-decon.h,
 * decon_reg_7870.c} and pwrcal/S5E7870 for the register map and polarity. */
#include <stdint.h>
#include "display_console.h"
#include "font.h"

#define FB_BASE        0x67000000UL
#define FB_W           720U
#define FB_H           1280U
#define FB_PIXELS      (FB_W * FB_H)
#define FB_BYTES       (FB_PIXELS * 4UL)
#define DECON          0x14830000UL
#define DISP_PD_STATUS 0x10484024UL
#define MIF_BUS_GATE   0x10460870UL
#define DISP_CMU       0x148d0000UL
#define VIDCON0        0x0000U
#define VIDOUTCON0     0x0004U
#define WINCON0        0x0050U
#define WHOLE_X0       0x0130U
#define WHOLE_Y0       0x0134U
#define OFFSET_X0      0x0170U
#define OFFSET_Y0      0x0174U
#define WIN_MAP0       0x0340U
#define TRIGCON        0x06b0U
#define UPDATE         0x0710U
#define ADD0           0x0880U
#define HW_ENABLE      (1U << 3)
#define HW_UNMASK      (1U << 4)
#define SW_ENABLE      (1U << 0)
#define SW_COMMAND     (1U << 1)
#define SCALE          3U
#define CELL           (6U * SCALE)
#define TITLE_Y        594U
#define STATUS_Y       648U
#define WHITE          0xffffffffU
#define BLACK          0xff000000U

static uint32_t rd(uintptr_t addr) { return *(volatile uint32_t *)addr; }
static void wr(uintptr_t addr, uint32_t value)
{
    *(volatile uint32_t *)addr = value;
    __asm__ volatile("dsb sy" ::: "memory");
}

/* Only request a frame on a live command-mode window using one of this
 * board's two diagnosed frame-sized slots. Never change its buffer mapping.
 * The loader keeps booting when firmware leaves DECON or its clocks off. */
static uintptr_t command_window(volatile uint64_t *log, uint32_t *trigger)
{
    log[64] = 1;
    if ((rd(DISP_PD_STATUS) & 15U) != 15U || !(rd(MIF_BUS_GATE) & 1U))
        return 0;
    if ((rd(DISP_CMU + 0x810) & 5U) != 5U || (rd(DISP_CMU + 0x814) & 3U) != 3U ||
        !(rd(DISP_CMU + 0x820) & 1U)) return 0;
    log[64] = 2;
    if ((rd(DECON + VIDCON0) & 3U) != 3U ||
        (rd(DECON + VIDOUTCON0) & 0x01800000U) != 0x01800000U) return 0;
    uint32_t win = rd(DECON + WINCON0), format = (win >> 2) & 0x1fU;
    if (!(win & 1U) || format > 7U || (rd(DECON + WIN_MAP0) & (1U << 24))) return 0;
    log[64] = 3;
    uint32_t raw = rd(DECON + ADD0), y = rd(DECON + OFFSET_Y0);
    if (rd(DECON + WHOLE_X0) != FB_W || rd(DECON + OFFSET_X0) != 0 ||
        (y != 0 && y != FB_H) || rd(DECON + WHOLE_Y0) < y + FB_H) return 0;
    uintptr_t active = (uintptr_t)raw + (uintptr_t)y * FB_W * 4;
    if ((raw != FB_BASE && raw != FB_BASE + FB_BYTES) ||
        (active != FB_BASE && active != FB_BASE + FB_BYTES)) return 0;
    uint32_t trig = rd(DECON + TRIGCON);
    *trigger = trig & HW_ENABLE ? HW_UNMASK : trig & SW_ENABLE ? SW_COMMAND : 0;
    if (!*trigger) return 0;
    log[64] = 4; log[65] = active; log[66] = trig;
    return active;
}

static void line(volatile uint32_t *fb, unsigned y, const char *text, unsigned field)
{
    unsigned len = 0;
    while (text[len]) ++len;
    unsigned x = (FB_W - field * CELL) / 2;
    unsigned pad = (field - len) / 2;
    for (unsigned col = 0; col < field; ++col) {
        char ch = (col >= pad && col < pad + len) ? text[col - pad] : ' ';
        unsigned index = 0;
        while (index + 1 < FONT_COUNT && font_chars[index] != ch) ++index;
        for (unsigned row = 0; row < 7U * SCALE; ++row) {
            volatile uint32_t *dest = fb + (y + row) * FB_W + x + col * CELL;
            unsigned bits = font_rows[index][row / SCALE];
            for (unsigned p = 0; p < CELL; ++p)
                dest[p] = p < 5U * SCALE && (bits & (16U >> (p / SCALE))) ? WHITE : BLACK;
        }
    }
}

static void draw(uintptr_t address, enum a3_screen screen)
{
    volatile uint32_t *fb = (volatile uint32_t *)address;
    if (screen == A3_SCREEN_LOADING) {
        volatile uint64_t *wide = (volatile uint64_t *)address;
        for (unsigned i = 0; i < FB_PIXELS / 2; ++i) wide[i] = 0xff000000ff000000ULL;
        line(fb, TITLE_Y, "A3 2017 XNU LOADER", 20);
    }
    const char *status = screen == A3_SCREEN_LOADING ? "LOADING XNU" :
                         screen == A3_SCREEN_STARTING ? "STARTING XNU" : "PAYLOAD ERROR";
    line(fb, STATUS_Y, status, 16);
    if (screen == A3_SCREEN_LOADING) a3_clean_range(address, address + FB_BYTES);
    else a3_clean_range(address + STATUS_Y * FB_W * 4,
                        address + (STATUS_Y + 7U * SCALE) * FB_W * 4);
}

void a3_display(enum a3_screen screen, volatile uint64_t *log)
{
    /* Always put the message in the verified firmware buffer first. Video-mode
     * scanout can consume it without any register writes. */
    draw(FB_BASE, screen);
    uint32_t trigger = 0;
    uintptr_t active = command_window(log, &trigger);
    if (!active) return;
    if (active != FB_BASE) draw(active, screen);
    wr(DECON + UPDATE, rd(DECON + UPDATE) | 1U);
    wr(DECON + TRIGCON, rd(DECON + TRIGCON) | trigger);
    log[67] += 1;
}
