#include <assert.h>
#include <string.h>
#include "../xnu/a3y17lte/a3_bt_protocol.h"

int main(void)
{
    uint8_t reply[] = {4, 0x0e, 12, 1, 1, 0x10, 0, 8, 0x34, 0x12, 8, 0x1d, 0, 0x78, 0x56};
    struct a3_bt_version version;
    assert(a3_bt_decode_version(reply, sizeof(reply), &version) == 1);
    assert(version.status == 0 && version.hci == 8 && version.lmp == 8);
    assert(version.revision == 0x1234 && version.manufacturer == 0x1d && version.subversion == 0x5678);
    for (unsigned length = 0; length < sizeof(reply); ++length)
        assert(a3_bt_decode_version(reply, length, &version) == -1);
    reply[5] = 0x0c;
    assert(a3_bt_decode_version(reply, sizeof(reply), &version) == 0);
    reply[5] = 0x10;
    reply[6] = 1;
    reply[2] = 4;
    assert(a3_bt_decode_version(reply, 7, &version) == 1 && version.status == 1);
    reply[6] = 0;
    assert(a3_bt_decode_version(reply, 7, &version) == -1);
    uint8_t event[] = {4, 0xff, 1, 0};
    assert(a3_bt_decode_version(event, sizeof(event), &version) == 0);
    return 0;
}
