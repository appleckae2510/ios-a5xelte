/* Compile harness only: validates the new C path against the existing helper ABI.
 * It does not emulate I2C, power rails or XNU's scheduler. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
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
static vm_offset_t ml_io_map(vm_offset_t a, vm_size_t b) { (void)b; return a; }
static void sweet_hid_touch(int a,int b,int c,int d) { (void)a;(void)b;(void)c;(void)d; }
static void thread_terminate_self(void) { }
static void thread_deallocate(thread_t a) { (void)a; }
static bool PE_parse_boot_argn(const char *a,void *b,unsigned c) { (void)a;(void)b;(void)c; return false; }
static int kernel_thread_start_priority(void (*a)(void *,wait_result_t),void *b,int c,thread_t *d)
{ (void)a;(void)b;(void)c; *d=NULL; return 0; }
#include "../xnu/a3y17lte/a3_touch.inc"
#include "../xnu/a3y17lte/a3_hardware.inc"
int main(void) { a3y17lte_hardware_probe(); a3y17lte_touch_start(); return 0; }
