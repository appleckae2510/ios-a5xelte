/* Exercise the diagnostic probe with inaccessible CP control registers.
 * The touch path is compiled with the existing helper ABI and left disabled. */
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uintptr_t vm_offset_t;
typedef unsigned long vm_size_t;
typedef int wait_result_t;
typedef void *thread_t;
#define A3Y17LTE 1
#define KERN_SUCCESS 0
static uint32_t a5touch_read(vm_offset_t a, uint32_t b) { (void)a; (void)b; return 0; }
static void a5touch_write(vm_offset_t a, uint32_t b, uint32_t c) { (void)a; (void)b; (void)c; }
static bool a5touch_wait_irq(vm_offset_t a) { (void)a; return false; }
static void a5touch_clear_irq(vm_offset_t a) { (void)a; }
static void delay(unsigned a) { (void)a; }
static void j7t_sleep_ms(unsigned a) { (void)a; }
static unsigned mapped_pages;
static vm_offset_t ml_io_map(vm_offset_t address, vm_size_t length)
{
    static const uintptr_t bases[] = {0x139b0000, 0x139f0000, 0x10460000, 0x10484000};
    static uint32_t pages[4][0x1000 / sizeof(uint32_t)];
    assert(length == 0x1000);
    for (unsigned i = 0; i < sizeof(bases) / sizeof(bases[0]); ++i) {
        if (address == bases[i]) {
            mapped_pages |= 1u << i;
            return (vm_offset_t)pages[i];
        }
    }
    assert(0 && "unexpected MMIO mapping");
    return 0;
}
static void sweet_hid_touch(int a,int b,int c,int d) { (void)a;(void)b;(void)c;(void)d; }
static void thread_terminate_self(void) { }
static void thread_deallocate(thread_t a) { (void)a; }
static bool PE_parse_boot_argn(const char *name, void *value, unsigned size)
{
    if (strcmp(name, "a3hwprobe") != 0) return false;
    assert(size == sizeof(unsigned));
    *(unsigned *)value = 1;
    return true;
}
static int kernel_thread_start_priority(void (*a)(void *,wait_result_t),void *b,int c,thread_t *d)
{ (void)a;(void)b;(void)c; *d=NULL; return 0; }
#include "../xnu/a3y17lte/a3_touch.inc"
#include "../xnu/a3y17lte/a3_hardware.inc"
int main(void)
{
    a3y17lte_hardware_probe();
    assert(mapped_pages == 0xf);
    a3y17lte_touch_start();
    return 0;
}
