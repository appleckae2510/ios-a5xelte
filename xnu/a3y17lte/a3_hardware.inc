/* SPDX-License-Identifier: MIT
 * A3Y17LTE hardware handoff and H4 transport bring-up, opt-in a3hwprobe=1.
 * Register facts come from the pinned Exynos7870 DTS and Samsung pwrcal.
 * HCI Read Local Version is sent only with enabled clocks, rails and UART.
 * No power sequencing, firmware upload, radio scanning or media writes.
 */
#if defined(A3Y17LTE)
#include "a3_bt_protocol.h"

static uint32_t
a3hw_read(vm_offset_t base, unsigned off)
{
    return *(volatile uint32_t *)(base + off);
}

static bool
a3bt_receive(vm_offset_t uart, uint8_t *value, unsigned *budget)
{
    while (*budget) {
        if (a3hw_read(uart, 0x10) & 1u) {
            if (a3hw_read(uart, 0x14) & 0xfu) return false;
            *value = *(volatile uint8_t *)(uart + 0x24);
            return true;
        }
        --*budget;
        delay(20);
    }
    return false;
}

static void
a3bt_version_probe(vm_offset_t uart)
{
    static const uint8_t command[] = {1, 1, 0x10, 0};
    unsigned budget = 50000; /* One-second aggregate waiting budget. */
    for (unsigned i = 0; i < sizeof(command); ++i) {
        while (budget && !(a3hw_read(uart, 0x10) & 2u)) {
            --budget;
            delay(20);
        }
        if (!budget) {
            printf("A3 BT: UART transmit timeout\n");
            return;
        }
        *(volatile uint8_t *)(uart + 0x20) = command[i];
    }
    uint8_t event[258];
    for (unsigned packets = 0; packets < 64; ++packets) {
        if (!a3bt_receive(uart, event, &budget)) break;
        if (event[0] != 4) continue;
        if (!a3bt_receive(uart, event + 1, &budget) ||
            !a3bt_receive(uart, event + 2, &budget)) break;
        unsigned length = (unsigned)event[2] + 3;
        for (unsigned i = 3; i < length; ++i) {
            if (!a3bt_receive(uart, event + i, &budget)) {
                printf("A3 BT: incomplete HCI event\n");
                return;
            }
        }
        struct a3_bt_version version;
        int result = a3_bt_decode_version(event, length, &version);
        if (result < 0) {
            printf("A3 BT: malformed HCI version event\n");
            return;
        }
        if (result == 1) {
            printf("A3 BT: HCI status=%u hci=%u rev=%x lmp=%u manufacturer=%x sub=%x\n",
                version.status, version.hci, version.revision, version.lmp,
                version.manufacturer, version.subversion);
            return;
        }
    }
    printf("A3 BT: HCI version response unavailable\n");
}

static void
a3y17lte_hardware_probe(void)
{
    unsigned enabled = 0, bt = 0;
    PE_parse_boot_argn("a3hwprobe", &enabled, sizeof(enabled));
    if (enabled != 1) return;
    printf("A3 HW: A3Y17LTE_HARDWARE_V2\n");
    vm_offset_t top = ml_io_map(0x139b0000u, 0x1000);
    vm_offset_t alive = ml_io_map(0x139f0000u, 0x1000);
    vm_offset_t mif = ml_io_map(0x10460000u, 0x1000);
    /* The A320FL aborts on direct CP_CTRL_NS reads. Only map the
     * power-domain status page needed by audio and camera. */
    vm_offset_t domains = ml_io_map(0x10484000u, 0x1000);
    if (!top || !alive || !mif || !domains) {
        printf("A3 HW: register mapping unavailable\n");
        return;
    }
    uint32_t uart_mux = a3hw_read(top, 0);
    uint32_t bt_con = a3hw_read(top, 0x160), bt_dat = a3hw_read(top, 0x164);
    uint32_t power_con = a3hw_read(top, 0x220), power_dat = a3hw_read(top, 0x224);
    uint32_t wake_con = a3hw_read(alive, 0x60), wake_dat = a3hw_read(alive, 0x64);
    printf("A3 BT: QCA6174 UART0 mux=%x EN=%u DCDC=%u WAKE=%u HOST=%u\n",
        uart_mux, bt_dat & 1u, power_dat & 1u, (wake_dat >> 2) & 1u, (wake_dat >> 6) & 1u);
    printf("A3 WLAN: QCOM SDIO EN=%u HOST=%u clock=%x\n",
        (a3hw_read(top, 0x144) >> 6) & 1u,
        (a3hw_read(alive, 0x84) >> 2) & 1u, a3hw_read(mif, 0x88c));
    printf("A3 AUDIO: COD3026X TFA9896 domain=%x\n", a3hw_read(domains, 0x24));
    printf("A3 CAMERA: IMX258 IMX219 domain=%x io=%u core=%u rear_reset=%u front_reset=%u\n",
        a3hw_read(domains, 0x44), (power_dat >> 2) & 1u,
        (a3hw_read(top, 0x244) >> 1) & 1u, (power_dat >> 3) & 1u, (power_dat >> 1) & 1u);
    printf("A3 MODEM: CP registers skipped\n");
    PE_parse_boot_argn("a3btprobe", &bt, sizeof(bt));
    if (bt != 1) return;
    if (!(a3hw_read(mif, 0x8a0) & 1u) || !(a3hw_read(mif, 0x8a4) & 1u)) {
        printf("A3 BT: UART source clock disabled\n");
        return;
    }
    vm_offset_t peri = ml_io_map(0x101f0000u, 0x1000);
    if (!peri) return;
    uint32_t pclk = a3hw_read(peri, 0x814), sclk = a3hw_read(peri, 0x830);
    printf("A3 BT: UART pclk=%x sclk=%x mux=%x div=%x\n",
        pclk, sclk, a3hw_read(mif, 0x2a4), a3hw_read(mif, 0x4a4));
    if (!(pclk & (1u << 11)) || !(sclk & 1u)) {
        printf("A3 BT: UART peripheral clock disabled\n");
        return;
    }
    if ((uart_mux & 0xffffu) != 0x2222u || (bt_con & 15u) != 1 || !(bt_dat & 1u) ||
        (power_con & 15u) != 1 || !(power_dat & 1u) ||
        ((wake_con >> 8) & 15u) != 1 || !(wake_dat & 4u)) {
        printf("A3 BT: UART pins or chip power need initialization\n");
        return;
    }
    vm_offset_t uart = ml_io_map(0x13810000u, 0x1000);
    if (!uart) return;
    uint32_t ulcon = a3hw_read(uart, 0), ucon = a3hw_read(uart, 4);
    printf("A3 BT: UART ulcon=%x ucon=%x baud_div=%x frac=%x\n",
        ulcon, ucon, a3hw_read(uart, 0x28), a3hw_read(uart, 0x2c));
    if ((ulcon & 0x3fu) != 3 || (ucon & 15u) != 5) {
        printf("A3 BT: UART handoff mode unsuitable\n");
        return;
    }
    a3bt_version_probe(uart);
}
#endif
