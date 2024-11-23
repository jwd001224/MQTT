#!/bin/python3
import inspect
import sys
import time

import HDevice
import HPlatform
import HHhdlist
import HStategrid
import HSyslog
import PROTOCOL


# null_writer = NullWriter()
# sys.stdout = null_writer


def main():
    HStategrid.datadb_init()
    client = HDevice.HMqttClient(broker_address="127.0.0.1", broker_port=1883)
    client.connect()
    HDevice.do_mqtt_period()

    try:
        if not HStategrid.DEBUG_MODE:
            HStategrid.disable_network_interface("eth0")
            HStategrid.disable_network_interface("eth1")
            # HStategrid.disable_network_interface("eth2")
        # HHhdlist.set_apn()
        HHhdlist.save_json_config({"SDKVersion": HStategrid.SDKVersion})
        HHhdlist.save_json_config({"Platform_type": HStategrid.Platform_type})
        while True:
            deviceCode = HHhdlist.read_json_config("deviceCode")
            if deviceCode is None or deviceCode == "":
                time.sleep(10)
            else:
                HStategrid.save_DeviceInfo("deviceCode", 1, deviceCode, 0)
                HSyslog.log_info(deviceCode)
                if len(deviceCode) > 20:
                    HStategrid.Sign_type = HStategrid.SIGN_TYPE.deviceRegCode.value
                else:
                    HStategrid.Sign_type = HStategrid.SIGN_TYPE.deviceCode.value
                    HStategrid.Vendor_Code = deviceCode[0:4]
                break
            # if HStategrid.get_DeviceInfo("deviceCode") is None or HStategrid.get_DeviceInfo("deviceCode") == "":
            #     deviceCode = HHhdlist.read_json_config("deviceCode")
            #     if deviceCode is None or deviceCode == "":
            #         time.sleep(10)
            #     else:
            #         HStategrid.save_DeviceInfo("deviceCode", 1, deviceCode, 0)
            #         if len(deviceCode) > 20:
            #             HStategrid.Sign_type = HStategrid.SIGN_TYPE.deviceRegCode.value
            #         else:
            #             HStategrid.Sign_type = HStategrid.SIGN_TYPE.deviceCode.value
            #             HStategrid.Vendor_Code = deviceCode[0:4]
            #         break
            # else:
            #     if HStategrid.get_DeviceInfo("productKey") is None or HStategrid.get_DeviceInfo("productKey") == "0" or HStategrid.get_DeviceInfo("productKey") == "":
            #         HStategrid.save_DeviceInfo("productKey", 1, HHhdlist.read_json_config("productKey", "/root/DeviceCode.json"), 0)
            #         HStategrid.save_DeviceInfo("deviceName", 1, HHhdlist.read_json_config("deviceName", "/root/DeviceCode.json"), 0)
            #         HStategrid.save_DeviceInfo("deviceSecret", 1, HHhdlist.read_json_config("deviceSecret", "/root/DeviceCode.json"), 0)
            #         deviceCode = HStategrid.get_DeviceInfo("deviceCode")
            #         HStategrid.Vendor_Code = deviceCode[0:4]
            #     else:
            #         HHhdlist.save_json_config({"productKey": HStategrid.get_DeviceInfo("productKey")})
            #         HHhdlist.save_json_config({"deviceName": HStategrid.get_DeviceInfo("deviceName")})
            #         HHhdlist.save_json_config({"deviceSecret": HStategrid.get_DeviceInfo("deviceSecret")})
            #         deviceCode = HStategrid.get_DeviceInfo("deviceCode")
            #         if len(deviceCode) > 20:
            #             HStategrid.Sign_type = HStategrid.SIGN_TYPE.deviceRegCode.value
            #         else:
            #             HStategrid.Sign_type = HStategrid.SIGN_TYPE.deviceCode.value
            #             HStategrid.Vendor_Code = deviceCode[0:4]
            #     break
        HPlatform.linkkit_init()
        HHhdlist.time_sync_time = int(time.time())
    except Exception as e:
        HSyslog.log_info(f"HPlatform.linkkit_init error: {e}")
    try:
        while True:
            if HStategrid.get_link_init_status() == 1:
                if int(time.time()) - HHhdlist.time_sync_time >= 86400 and HPlatform.send_event_queue.empty():
                    PROTOCOL.iot_linkkit_time_sync()
                    HHhdlist.time_sync_time = int(time.time())
                    HStategrid.backup_sqlite_db()
                else:
                    time.sleep(3600)
            else:
                time.sleep(3600)
    except Exception as e:
        HSyslog.log_info(f"HPlatform.mainloop error: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        HSyslog.log_info(e)
    except KeyboardInterrupt:
        sys.exit()
