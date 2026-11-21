/* SPDX-License-Identifier: GPL-2.0-only
 * Galaxy A3 2017 (a3y17lte) S-Boot loader for the XNU payload. Derived from the A5XELTE loader.
 * arm64 Image with the load offset found in the A320FL BOOT backup. x0=FDT,
 * MMU off. Accept the arm64 firmware entry states EL1 or EL2. Payload at 0x4000.
 * On errors it flushes the log and halts (hold power + volume down for 10 s to reboot).
 */
.section .text.head, "ax"
.global _start
_start:
    b entry
    .long 0
    .quad 0x80000           /* offset from a 2 MiB aligned RAM base */
    .quad _image_size
    .quad 0                 /* same little-endian placement flags as original A320FL */
    .quad 0, 0, 0
    .byte 0x41, 0x52, 0x4d, 0x64
    .long 0

entry:
    msr daifset, #15
    mov x19, x0
    mrs x20, CurrentEL
    cmp x20, #8
    b.ne check_el1
    /* Firmware may hand an OS the CPU at EL2. Enter AArch64 EL1h with
     * interrupts masked and the physical timer available to the kernel. */
    mrs x21, SCTLR_EL2
    tbnz x21, #0, halt
    mov x0, #(1 << 31)
    msr hcr_el2, x0
    mrs x0, cnthctl_el2
    orr x0, x0, #3
    msr cnthctl_el2, x0
    msr cntvoff_el2, xzr
    mrs x0, midr_el1
    msr vpidr_el2, x0
    mrs x0, mpidr_el1
    msr vmpidr_el2, x0
    mov x0, #0x0800
    movk x0, #0x30d0, lsl #16
    msr sctlr_el1, x0
    mov x0, #0x33ff
    msr cptr_el2, x0
    msr hstr_el2, xzr
    msr vttbr_el2, xzr
    mov x0, #0x3c5
    msr spsr_el2, x0
    adr x0, in_el1
    msr elr_el2, x0
    isb
    eret
check_el1:
    cmp x20, #4
    b.ne halt
in_el1:
    msr SPSel, #1
    mrs x21, SCTLR_EL1
    tbnz x21, #0, halt
    adr x14, a5_boot_stack_top
    mov sp, x14
    mov x0, x19
    bl a3_board_ok
    cbz w0, halt
    ldr x13, =0x679fe000
    mov x14, x13
    add x15, x13, #4096
zero_log:
    stp xzr, xzr, [x14], #16
    cmp x14, x15
    b.lo zero_log
    ldr x14, =0x333030554e583341 /* "A3XNU003" */
    str x14, [x13]
    str x20, [x13, #8]
    str x21, [x13, #16]
    str x19, [x13, #24]
    adr x14, _start
    str x14, [x13, #32]
    mov x14, #1
    str x14, [x13, #80]
    /* Make the entry evidence visible before accessing the display. */
    dc cvac, x13
    add x14, x13, #80
    dc cvac, x14
    dsb sy
    mov x0, x13
    adr x1, _start
    add x1, x1, #0x4000    /* a3y17lte-pack-boot.py places wrapper here */
    bl a3_prepare_xnu
    ldr x13, =0x679fe000
    cbz x0, fail
    mov x16, x0
    ldr x0, [x13, #136]       /* boot_args physical address */
    /* C cleaned copied ranges and the log. XNU's entry needs MMU off. */
    mrs x14, SCTLR_EL1
    bic x14, x14, #1
    bic x14, x14, #4
    bic x14, x14, #0x1000
    msr SCTLR_EL1, x14
    isb
    br x16
fail:
    mov x0, #2               /* A3_SCREEN_ERROR */
    mov x1, x13
    bl a3_display
    ldr x13, =0x679fe000
    mov x14, x13
    add x15, x13, #4096
flush_log:
    dc cvac, x14
    add x14, x14, #32
    cmp x14, x15
    b.lo flush_log
    dsb sy
halt:
    wfe
    b halt
    .ltorg

.section .data, "aw"
.balign 16
a5_boot_stack:
    .space 4096
a5_boot_stack_top:
