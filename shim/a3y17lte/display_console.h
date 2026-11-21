/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef A3Y17LTE_DISPLAY_CONSOLE_H
#define A3Y17LTE_DISPLAY_CONSOLE_H

#include <stdint.h>

enum a3_screen { A3_SCREEN_LOADING, A3_SCREEN_STARTING, A3_SCREEN_ERROR };
void a3_display(enum a3_screen screen, volatile uint64_t *log);
void a3_clean_range(uintptr_t start, uintptr_t end);

#endif
