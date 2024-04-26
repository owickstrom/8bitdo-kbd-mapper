#!/usr/bin/python
import sys
import time
import argparse
import usb.core
import usb.util

import keys
import utils

VENDOR_ID = 0x2dc8
PRODUCT_ID = 0x5200

ATTN = [0x52, 0x76, 0xff]
MAP = [0x52, 0xfa, 0x03, 0x0c, 0x00, 0xaa, 0x09, 0x71]
MAP_DONE = [0x52, 0x76, 0xa5]

OK = [0x54, 0xe4, 0x08] + [0] * 30
READY = [0x54, 0x8a, 0x07, 0x01] + [0] * 29  # nothing to report ?


class EightBDKdb:

    def __init__(self):
        self.ep_read, self.ep_write = get_8bd_endpoints()
        # print(self.ep_read)
        # print(self.ep_write)

    def read(self, size=64, timeout=1000):
        return self.ep_read.read(size, timeout).tobytes()

    def write(self, data, size=33):
        return self.ep_write.write(data + [0] * (33 - len(data)))

    def read_check(self, expected, size=64, timeout=1000):
        r = self.read(size, timeout)  # bytes
        if list(r) != expected:
            raise ValueError(
                f"Read unexpected value\rExpected: {bytes(expected).hex()}\n    Read: {r.hex()}"
            )

        return r

    def map_hid_usage(self, hwkey, usage):
        assert len(usage) <= 24

        self.write(ATTN)
        self.read()

        self.write(MAP + [hwkey] + usage)
        self.read_check(OK)

        self.write(MAP_DONE)
        self.read_check(OK)


def get_8bd_endpoints():
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

    if dev is None:
        raise ValueError(
            "Could not find 8BitDo Retro Mechanical Keyboard. Is its cable connected?"
        )

    # detach interface #2 if needed
    if dev.is_kernel_driver_active(2):
        print("detaching kernel driver", file=sys.stderr)
        dev.detach_kernel_driver(2)

    # [config][(interface, alternate)][endpoint]
    endpoint_in = dev[0][(2, 0)][0]
    endpoint_out = dev[0][(2, 0)][1]

    return endpoint_in, endpoint_out


def cmd_list_keys(args):
    print("Mappable keys")
    print("-------------")
    print()
    utils.print_usage_keys()
    print()
    # print("Can't find the key you're looking for? Use \"map-hid\".")
    # print()
    print("Hardware keys")
    print("-------------")
    print()
    utils.print_hw_keys()
    print()


# TODO: create Key and Usage classes and store byte value but also name/hex
# Those could be used to write things as "successfully mapped capslock to esc"
def cmd_map(hwkey, usage):
    kbd = EightBDKdb()
    try:
        kbd.map_hid_usage(hwkey, usage)
    except Exception as e:
        print(f"Failed mapping with error:\n{e}\nMaybe try again?")
        sys.exit(1)


def cmd_map_key(args):
    cmd_map(args.hardware_key, args.mapped_key)


def cmd_map_hid(args):
    cmd_map(args.hardware_key, args.hid_usage)


def arg_hw_key(key):
    if not key in keys.HWKEY:
        raise argparse.ArgumentTypeError(
            f"unknown value '{key}'.\nUse \"list-keys\" to list known values.")

    return keys.HWKEY[key]


def arg_mapped_key(key):
    if not key in keys.USAGE:
        raise argparse.ArgumentTypeError(
            f"unknown value '{key}'.\nUse \"list-keys\" to list known values.")

    return utils.int_to_bytes(keys.USAGE[key][0])


def arg_hid_usage(usage):
    try:
        usage = bytes.fromhex(usage)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"could not convert '{usage}' to bytes. Maybe a digit is missing?")

    # remaining buffer len, although usages should be shorter
    if len(usage) > 24:
        raise argparse.ArgumentTypeError(f"value '{usage}' is too long.")

    return list(usage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Key mapper for 8BitDo\'s Retro Mechanical Keyboard")
    subparsers = parser.add_subparsers()

    parser_list_keys = subparsers.add_parser(
        "list-keys", help="list the names of keys to be used in maps")
    parser_list_keys.set_defaults(func=cmd_list_keys)

    parser_map = subparsers.add_parser(
        "map",
        formatter_class=argparse.RawTextHelpFormatter,
        help="map hardware keys to other keys")
    parser_map.set_defaults(func=cmd_map_key)
    parser_map.add_argument(
        "hardware_key",
        type=arg_hw_key,
        help="the name of the hardware key whose mapping will be changed")
    parser_map.add_argument(
        "mapped_key",
        type=arg_mapped_key,
        help=
        "the name of the key to map to (eg. \"esc\");\nuse the \"list-keys\" subcommand for a key name reference"
    )

    parser_map_hid = subparsers.add_parser(
        "map-hid", help="map hardware keys to HID Usage codes")
    parser_map_hid.set_defaults(func=cmd_map_hid)
    parser_map_hid.add_argument(
        "hardware_key",
        type=arg_hw_key,
        help="the name of the hardware key whose mapping will be changed")
    parser_map_hid.add_argument(
        "hid_usage",
        type=arg_hid_usage,
        help="a HID Usage code hex string (eg. 070029 for \"esc\")")

    args = parser.parse_args()

    args.func(args)
