#!/bin/python3
import inspect
import sys
import time

import HDevice
import HPlatform
import HHhdlist
import HStategrid
import HSyslog


# null_writer = NullWriter()
# sys.stdout = null_writer


def main():
    HStategrid.datadb_init()
    HDevice.do_link_mqtt()
    HDevice.do_mqtt_send_data()
    HDevice.do_mqtt_period()

    try:
        HStategrid.disable_network_interface("eth0")
        HStategrid.disable_network_interface("eth1")
        HStategrid.disable_network_interface("eth2")
        HHhdlist.set_apn()
        HPlatform.linkkit_init()
    except Exception as e:
        print(f"\033[91mHPlatform.linkkit_init error: {e} .{inspect.currentframe().f_lineno}\033[0m")
        HSyslog.log_info(f"HPlatform.linkkit_init error: {e} .{inspect.currentframe().f_lineno}")
    try:
        while True:
            pass
    except Exception as e:
        print(f"\033[91mHPlatform.mainloop error: {e} .{inspect.currentframe().f_lineno}\033[0m")
        HSyslog.log_info(f"HPlatform.mainloop error: {e} .{inspect.currentframe().f_lineno}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
    except KeyboardInterrupt:
        sys.exit()
