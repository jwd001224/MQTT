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
        if not HStategrid.DEBUG_MODE:
            HStategrid.disable_network_interface("eth0")
            HStategrid.disable_network_interface("eth1")
            HStategrid.disable_network_interface("eth2")
        # HHhdlist.set_apn()
        while True:
            if HStategrid.get_DeviceInfo("deviceCode") is None or HStategrid.get_DeviceInfo("deviceCode") == "":
                deviceCode = HHhdlist.read_json_config("deviceCode")
                # deviceName = HHhdlist.read_json_config("deviceName")
                if deviceCode is None or deviceCode == "":
                    time.sleep(10)
                else:
                    HStategrid.save_DeviceInfo("deviceCode", 1, deviceCode, 0)
                    # HStategrid.save_DeviceInfo("deviceName", 1, deviceName, 0)
                    break
            else:
                if HStategrid.get_DeviceInfo("productKey") is None or HStategrid.get_DeviceInfo("productKey") == "0" or HStategrid.get_DeviceInfo("productKey") == "":
                    HStategrid.save_DeviceInfo("productKey", 1, HHhdlist.read_json_config("productKey", "/root/DeviceCode.json"), 0)
                    HStategrid.save_DeviceInfo("deviceName", 1, HHhdlist.read_json_config("deviceName", "/root/DeviceCode.json"), 0)
                    HStategrid.save_DeviceInfo("deviceSecret", 1, HHhdlist.read_json_config("deviceSecret", "/root/DeviceCode.json"), 0)
                else:
                    HHhdlist.save_json_config({"productKey": HStategrid.get_DeviceInfo("productKey")})
                    HHhdlist.save_json_config({"deviceName": HStategrid.get_DeviceInfo("deviceName")})
                    HHhdlist.save_json_config({"deviceSecret": HStategrid.get_DeviceInfo("deviceSecret")})
                break
        HPlatform.linkkit_init()
    except Exception as e:
        HSyslog.log_info(f"HPlatform.linkkit_init error: {e} .{inspect.currentframe().f_lineno}")
    try:
        while True:
            pass
    except Exception as e:
        HSyslog.log_info(f"HPlatform.mainloop error: {e} .{inspect.currentframe().f_lineno}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        HSyslog.log_info(e)
    except KeyboardInterrupt:
        sys.exit()
