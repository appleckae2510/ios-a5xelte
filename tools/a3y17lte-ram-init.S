/* Single-section ARM64 Darwin PID 1, packaged with tools/mkinit.py.
 * The bootstrap checks console, HFS and pipe I/O, then execs the second
 * program immediately. Neither stage opens a physical disk.
 */
.macro say label
    mov x0, x19
    adr x1, \label
    adr x2, \label\()_end
    sub x2, x2, x1
    mov x16, #4
    svc #0x80
.endmacro
.text
.globl _start
.p2align 2
_start:
    mov x9, sp
    and x9, x9, #~15
    mov sp, x9
    sub sp, sp, #96
    adr x0, console_path
    mov x1, #2
    orr x1, x1, #0x1000000      /* O_RDWR | O_CLOEXEC */
    mov x2, #0
    mov x16, #5
    svc #0x80
    b.cs idle
    mov x19, x0
    mov x16, #20                /* getpid */
    svc #0x80
    b.cs wrong_pid
    cmp x0, #1
    b.ne wrong_pid
#ifdef A3_RAM_USERLAND
    say ram_ready
    b idle
#else
    adr x0, marker_path
    mov x1, #0                  /* O_RDONLY */
    mov x2, #0
    mov x16, #5
    svc #0x80
    b.cs file_failed
    mov x20, x0
    mov x1, sp
    mov x2, #9                  /* eight expected bytes; reject trailing data */
    mov x16, #3
    svc #0x80
    b.cs file_failed
    cmp x0, #8
    b.ne file_failed
    adr x9, token
    ldr x10, [x9]
    ldr x11, [sp]
    cmp x10, x11
    b.ne file_failed
    mov x0, x20
    mov x16, #6
    svc #0x80
    mov x16, #42                /* pipe returns read fd in x0, write fd in x1 */
    svc #0x80
    b.cs ipc_failed
    mov x20, x0
    mov x21, x1
    mov x0, x21
    mov x1, sp
    mov x2, #8
    mov x16, #4
    svc #0x80
    b.cs ipc_failed
    cmp x0, #8
    b.ne ipc_failed
    mov x0, x20
    add x1, sp, #16
    mov x2, #8
    mov x16, #3
    svc #0x80
    b.cs ipc_failed
    cmp x0, #8
    b.ne ipc_failed
    ldr x10, [sp]
    ldr x11, [sp, #16]
    cmp x10, x11
    b.ne ipc_failed
    mov x0, x20
    mov x16, #6
    svc #0x80
    mov x0, x21
    mov x16, #6
    svc #0x80
    say passed
    adr x0, next_path
    stp x0, xzr, [sp, #32]      /* argv[0], NULL */
    str xzr, [sp, #48]         /* envp[0] */
    add x1, sp, #32
    add x2, sp, #48
    mov x16, #59                /* execve; successful exec preserves PID 1 */
    svc #0x80
    say exec_error
    b idle
file_failed:
    say file_error
    b idle
ipc_failed:
    say ipc_error
    b idle
#endif
wrong_pid:
    say pid_error
idle:
    mov x9, #60
    stp x9, xzr, [sp, #64]      /* stack timeval may be updated by select */
    mov x0, #0
    mov x1, #0
    mov x2, #0
    mov x3, #0
    add x4, sp, #64
    mov x16, #93
    svc #0x80
    b idle
.p2align 3
console_path: .asciz "/dev/console"
pid_error: .ascii "A3 TEST STOP: PID 1 unavailable\n"
pid_error_end:
#ifdef A3_RAM_USERLAND
ram_ready: .ascii "A3 RAM USERLAND: PID 1 OK\nApple userland needs the prepared iOS root.\n"
ram_ready_end:
#else
marker_path: .asciz "/etc/a3-boot-id"
next_path: .asciz "/sbin/a3-userland"
.p2align 3
token: .ascii "A3RAM08!"
passed: .ascii "A3 TEST OK: HFS + console + PID 1 + pipe\n"
passed_end:
exec_error: .ascii "A3 TEST STOP: exec /sbin/a3-userland failed\n"
exec_error_end:
file_error: .ascii "A3 TEST STOP: HFS file check failed\n"
file_error_end:
ipc_error: .ascii "A3 TEST STOP: pipe transfer failed\n"
ipc_error_end:
#endif
