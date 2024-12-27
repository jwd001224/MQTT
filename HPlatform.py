import asyncio
import glob
import json
import multiprocessing
import queue
import subprocess
import urllib.request
import urllib.error
import time
import datetime

import HSyslog
import HTools
import HStategrid
import HHhdlist

from PROTOCOL import *

dcPile_property = None
fault_property = None
dc_work_property = None
dc_nonWork_property = None
meter_property = None
BMS_property = None
dc_input_meter_property = None
property_start = 0
send_event_queue = queue.Queue()


class PeriodicFunctionCaller:
    def __init__(self, timeout, func):
        self.timer = None
        self.interval = timeout
        self.callback = func
        self.thread_status = False

    def my_function(self):
        try:
            self.callback()
        except Exception as e:
            HSyslog.log_info(f"{e}")

    def call_function_periodically(self):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(self.interval, self.call_function_periodically)
        self.timer.start()
        self.my_function()

    def start_periodic_calling(self):
        thread = threading.Thread(target=self.call_function_periodically)
        thread.start()
        self.thread_status = True

    def cleck_thread_status(self):
        return self.thread_status

    def set_interval(self, new_interval):
        self.interval = new_interval
        HSyslog.log_info(f"new_interval: {new_interval}")


def linkkit_init():
    HSyslog.log_info(HStategrid.Sign_type)
    while True:
        if HStategrid.get_DeviceInfo("deviceCode") is None or HStategrid.get_DeviceInfo("deviceCode") == "":
            time.sleep(10)
        else:
            break
    while True:
        if HStategrid.get_ping() == 0:
            time.sleep(5)
        else:
            break
    try:
        if HStategrid.Sign_type == HStategrid.SIGN_TYPE.deviceCode.value:
            init_data = {
                "device_uid": HStategrid.get_DeviceInfo("deviceCode"),
            }
        elif HStategrid.Sign_type == HStategrid.SIGN_TYPE.deviceRegCode.value:
            init_data = {
                "device_reg_code": HStategrid.get_DeviceInfo("deviceCode"),
            }
        init_data_json = json.dumps(init_data)
        iot_linkkit_init(init_data_json)
        result = HStategrid.get_VerInfoEvt(4)
        if result[0] is not None:
            HSyslog.log_info(f"set_version: {result[0]}")
            set_version(result[0])
        HStategrid.save_DeviceInfo("SDKVersion", 1, HStategrid.SDKVersion, 0)
        HStategrid.save_DeviceInfo("UIVersion", 1, HHhdlist.read_json_config("ui_version"), 0)
        HStategrid.Vendor_Code = HStategrid.get_DeviceInfo("deviceCode")[0:4]
        time.sleep(3)

        if HStategrid.Sign_type == HStategrid.SIGN_TYPE.deviceCode.value:
            iot_link_connect(0, 1)
        elif HStategrid.Sign_type == HStategrid.SIGN_TYPE.deviceRegCode.value:
            iot_link_connect(0, 0)
        plamform_server()
        do_plamform_send()
        HStategrid.gun_num = HStategrid.get_DeviceInfo("00110")
        if HStategrid.gun_num is not None and HHhdlist.device_charfer_p == {}:
            for i in range(0, HStategrid.gun_num):
                HHhdlist.device_charfer_p[i + 1] = {}
                HHhdlist.bms_sum[i + 1] = 1
                HStategrid.send_gunElecFreq[i + 1] = 0
    except Exception as e:
        HSyslog.log_info(f"linkkit_init error: {e}")


# -------------------- 发送事件 ------------------ #

def plamform_event(event_type: int, info_dict: dict):
    try:
        info_json = json.dumps(info_dict)
        send_event_queue.put([event_type, info_json])
        return 0
    except Exception as e:
        HSyslog.log_info(f"input_data---info_dict: {info_dict}. {e}")
        return -1


def do_plamform_send():
    mqttSendThread = threading.Thread(target=__plamform_send)
    mqttSendThread.start()
    HSyslog.log_info("do_plamform_event")


def __plamform_send():
    while True:
        iot_mainloop()
        if HStategrid.get_link_init_status() == 1:
            if not send_event_queue:
                time.sleep(0.1)
            else:
                try:
                    if send_event_queue.empty():
                        time.sleep(0.1)
                    else:
                        data = send_event_queue.get()
                        if data[0] <= 14:
                            iot_send_event(data[0], data[1])
                        elif data[0] >= 15:
                            iot_send_property(data[0], data[1])
                        else:
                            HSyslog.log_info("info_msg send error")
                except Exception as e:
                    HSyslog.log_info(f"{e}")
        else:
            if send_event_queue.empty():
                time.sleep(0.1)
            else:
                send_event_queue.get()
                time.sleep(0.1)


# -------------------- 发送属性 ------------------ #

def plamform_property(property_type: int, property_dict: dict):
    try:
        property_json = json.dumps(property_dict)
        send_event_queue.put([property_type, property_json])
    except Exception as e:
        HSyslog.log_info(f"plamform_property---info_dict: {property_dict}. {e}")
        return -1


def plamform_property_thread(info_dict: dict):
    HStategrid.gunElecFreq_time = info_dict.get("gunElecFreq")
    global property_start
    global dcPile_property, dc_work_property, dc_nonWork_property, dc_input_meter_property, BMS_property, meter_property
    dcPile_property = PeriodicFunctionCaller(info_dict.get("equipParamFreq", 600), _send_property_dcPile)
    fault_property = PeriodicFunctionCaller(info_dict.get("faultWarnings", 360), _send_property_fault)
    dc_work_property = PeriodicFunctionCaller(5, _send_property_dc_work)
    dc_nonWork_property = PeriodicFunctionCaller(info_dict.get("nonElecFreq", 180), _send_property_dc_nonWork)
    meter_property = PeriodicFunctionCaller(info_dict.get("dcMeterFreq", 300) * 60, _send_property_meter)
    BMS_property = PeriodicFunctionCaller(15, _send_property_BMS)
    dc_input_meter_property = PeriodicFunctionCaller(info_dict.get("acMeterFreq", 300) * 60, _send_property_dc_input_meter)
    if not dcPile_property.cleck_thread_status():
        dcPile_property.start_periodic_calling()
        time.sleep(1)
    if not fault_property.cleck_thread_status():
        fault_property.start_periodic_calling()
        time.sleep(1)
    if not dc_work_property.cleck_thread_status():
        dc_work_property.start_periodic_calling()
        time.sleep(1)
    if not dc_nonWork_property.cleck_thread_status():
        dc_nonWork_property.start_periodic_calling()
        time.sleep(1)
    if not meter_property.cleck_thread_status():
        meter_property.start_periodic_calling()
        time.sleep(1)
    if not BMS_property.cleck_thread_status():
        BMS_property.start_periodic_calling()
        time.sleep(1)
    if not dc_input_meter_property.cleck_thread_status():
        dc_input_meter_property.start_periodic_calling()
        time.sleep(1)

    property_start = 1


def _send_property_dcPile():
    if HStategrid.get_property_status() == 1:
        try:
            HStategrid.get_net()
            eleModelId = HStategrid.get_DeviceInfo("eleModelId")
            serModelId = HStategrid.get_DeviceInfo("serModelId")
            if eleModelId is None or serModelId is None or eleModelId == "" or serModelId == "":
                eleModelId = ""
                serModelId = ""
            netType = HStategrid.platform_data.get("netType", 13)
            sigVal = HStategrid.platform_data.get("sigVal", 10)
            netId = HStategrid.platform_data.get("netId", 14)
            dcPile = {
                "netType": netType,
                "sigVal": sigVal,
                "netId": netId,
                "acVolA": 380,
                "acCurA": 0,
                "acVolB": 380,
                "acCurB": 0,
                "acVolC": 380,
                "acCurC": 0,
                "caseTemp": 700,
                "inletTemp": 700,
                "outletTemp": 700,
                "eleModelId": eleModelId,
                "serModelId": serModelId,
            }
            plamform_property(15, dcPile)
        except Exception as e:
            HSyslog.log_info(f"Send_Property_to_Platform_dcPile Failed. {e}")
            return ""

        try:
            qrcode = HHhdlist.read_json_config("qrcode")
            if qrcode is None:
                qrcode = {}
            for i in range(0, HStategrid.gun_num):
                if not qrcode.get(f"{i}", False):
                    info_qrCode = {
                        "gun_id": i,
                        "source": i,
                        "content": HStategrid.get_DeviceInfo(f"qrCode{i}"),
                    }
                    HTools.Htool_app_QR_code_update(info_qrCode)
                    qrcode.update({f"{i}": True})
                    HHhdlist.save_json_config({"qrcode": qrcode})
            return "dcPile"
        except Exception as e:
            HSyslog.log_info(f"Send_QrCode Failed. {e}")
            return ""


def _send_property_fault():
    if HStategrid.get_property_status() == 1:
        try:
            if HHhdlist.device_fault != {}:
                for i in range(0, HStategrid.gun_num):
                    if HHhdlist.device_fault.get(i + 1, {}) != {}:
                        gunNo = i + 1
                        fault = {
                            "gunNo": gunNo,
                            "faultSum": HHhdlist.device_fault.get(gunNo).get("faultSum"),
                            "warnSum": HHhdlist.device_fault.get(gunNo).get("warnSum"),
                            "faultValue": HHhdlist.device_fault.get(gunNo).get("faultValue"),
                            "warnValue": HHhdlist.device_fault.get(gunNo).get("warnValue"),
                        }
                    else:
                        fault = {
                            "gunNo": i + 1,
                            "faultSum": 0,
                            "warnSum": 0,
                            "faultValue": [],
                            "warnValue": [],
                        }
                    send_totalFaultEvt(fault)
            return "fault"
        except Exception as e:
            HSyslog.log_info(f"Send_Property_to_Platform_totalFaultEvt Failed. {e}")
            return ""


def _send_property_dc_work():
    if HStategrid.get_property_status() == 1:
        try:
            for i in HHhdlist.gun.keys():
                if HHhdlist.gun.get(i).get(1) == 6:
                    preTradeNo_data = HHhdlist.device_charfer_p.get(i)
                    chgTime = int(preTradeNo_data.get("charge_time", 0))
                    dc_work = {
                        "gunNo": i,
                        "workStatus": 13,
                        "gunStatus": 10,
                        "eLockStatus": 11,
                        "DCK1Status": 11,
                        "DCK2Status": 11,
                        "DCPlusFuseStatus": 11,
                        "DCMinusFuseStatus": 11,
                        "conTemp1": HHhdlist.gun.get(i).get(122, 0) * 10,
                        "conTemp2": HHhdlist.gun.get(i).get(123, 0) * 10,
                        "dcVol": HHhdlist.gun.get(i).get(112, 0),
                        "dcCur": HHhdlist.gun.get(i).get(113, 0) * 10,
                        "preTradeNo": preTradeNo_data.get("preTradeNo", ""),
                        "tradeNo": preTradeNo_data.get("tradeNo", ""),
                        "chgType": preTradeNo_data.get("startType", 0),
                        "realPower": HHhdlist.gun.get(i).get(115, 0),
                        "chgTime": chgTime / 60,
                        "socVal": HHhdlist.bms.get(i).get(106, 0),
                        "needVol": HHhdlist.bms.get(i).get(100, 0),
                        "needCur": HHhdlist.bms.get(i).get(101, 0),
                        "chargeMode": HHhdlist.bms.get(i).get(102, 0) + 10,
                        "bmsVol": HHhdlist.gun.get(i).get(103, 0),
                        "bmsCur": HHhdlist.gun.get(i).get(104, 0),
                        "SingleMHV": HHhdlist.bms.get(i).get(105, 0),
                        "remainT": HHhdlist.bms.get(i).get(107, 0),
                        "MHTemp": HHhdlist.bms.get(i).get(109, 0) * 10,
                        "MLTemp": HHhdlist.bms.get(i).get(111, 0) * 10,
                        "totalElect": preTradeNo_data.get("total_kwh", 0),
                        "sharpElect": preTradeNo_data.get("sharp_kwh", 0),
                        "peakElect": preTradeNo_data.get("peak_kwh", 0),
                        "flatElect": preTradeNo_data.get("flat_kwh", 0),
                        "valleyElect": preTradeNo_data.get("valley_kwh", 0),
                        "totalCost": preTradeNo_data.get("total_cost", 0),
                        "totalPowerCost": preTradeNo_data.get("total_electric_cost", 0),
                        "totalServCost": preTradeNo_data.get("total_service_cost", 0)
                    }
                    if chgTime <= 60:
                        plamform_property(16, dc_work)
                        HStategrid.send_gunElecFreq[i] = int(time.time())
                    else:
                        if int(time.time()) - HStategrid.send_gunElecFreq[i] >= HStategrid.get_DeviceInfo("gunElecFreq"):
                            HStategrid.send_gunElecFreq[i] = int(time.time())
                            plamform_property(16, dc_work)
            return "dc_work"
        except Exception as e:
            HSyslog.log_info(f"Send_Property_to_Platform_dc_work Failed. {e}")
            return ""


def _send_property_dc_nonWork():
    if HStategrid.get_property_status() == 1:
        try:
            for i in HHhdlist.gun.keys():
                if HHhdlist.gun.get(i).get(1) != 6:
                    workStatus = HStategrid.workstatus(HHhdlist.gun.get(i).get(1), HHhdlist.gun.get(i).get(6))
                    gunStatus = HStategrid.gunStatus(HHhdlist.gun.get(i).get(6, 0))
                    dc_nonWork = {
                        "gunNo": i,
                        "workStatus": workStatus,
                        "gunStatus": gunStatus,
                        "eLockStatus": HHhdlist.gun.get(i).get(2, 0) + 10,
                        "DCK1Status": HHhdlist.gun.get(i).get(4, 0) + 10,
                        "DCK2Status": HHhdlist.gun.get(i).get(4, 0) + 10,
                        "DCPlusFuseStatus": 11,
                        "DCMinusFuseStatus": 11,
                        "conTemp1": HHhdlist.gun.get(i).get(122, 0) * 10,
                        "conTemp2": HHhdlist.gun.get(i).get(123, 0) * 10,
                        "dcVol": HHhdlist.gun.get(i).get(112, 0),
                        "dcCur": HHhdlist.gun.get(i).get(123, 0) * 10,
                    }
                    plamform_property(17, dc_nonWork)
            return "dc_nonWork"
        except Exception as e:
            HSyslog.log_info(f"Send_Property_to_Platform_dc_nonWork Failed. {e}")
            return ""


def _send_property_meter():
    if HStategrid.get_property_status() == 1:
        try:
            for i in HHhdlist.meter.keys():
                if HHhdlist.gun.get(i).get(1) == 6:
                    elec = HHhdlist.device_charfer_p.get(i).get("total_kwh", 0)
                else:
                    elec = 0

                if HHhdlist.device_charfer_p[i] == {}:
                    lastTrade = ""
                else:
                    lastTrade = HHhdlist.device_charfer_p.get(i).get("preTradeNo", "")
                mailAddr = HStategrid.get_DeviceInfo(f"meter{i}")
                meter = {
                    "gunNo": i,
                    "acqTime": HHhdlist.unix_time_14(time.time()),
                    "mailAddr": HStategrid.hex_to_ascii(mailAddr),
                    "meterNo": HStategrid.hex_to_ascii(mailAddr),
                    "assetId": "",
                    "sumMeter": HHhdlist.meter.get(i).get(0, 0),
                    "lastTrade": lastTrade,
                    "elec": elec,
                }
                plamform_property(18, meter)
                meter_log = {
                    "gunNo": i,
                    "acqTime": HHhdlist.unix_time_14(time.time()),
                    "mailAddr": mailAddr,
                    "meterNo": mailAddr,
                    "assetId": "",
                    "sumMeter": HHhdlist.meter.get(i).get(0, 0),
                    "lastTrade": lastTrade,
                    "elec": elec,
                }
                HStategrid.save_dcOutMeterIty(meter_log)
            return "meter"
        except Exception as e:
            HSyslog.log_info(f"Send_Property_to_Platform_meter Failed. {e}")
            return ""


def _send_property_BMS():
    if HStategrid.get_property_status() == 1:
        try:
            for i in HHhdlist.bms.keys():
                if HHhdlist.gun.get(i).get(1) == 6:
                    if HHhdlist.bms_sum.get(i) <= 6:
                        preTradeNo_data = HHhdlist.device_charfer_p.get(i)
                        BMS = {
                            "gunNo": i,
                            "preTradeNo": preTradeNo_data.get("preTradeNo", ""),
                            "tradeNo": preTradeNo_data.get("tradeNo", ""),
                            "socVal": HHhdlist.bms.get(i).get(106, 0),
                            "BMSVer": 11,
                            "BMSMaxVol": HHhdlist.bms.get(i).get(14, 0),
                            "batType": HHhdlist.bms.get(i).get(1, 0) + 10,
                            "batRatedCap": HHhdlist.bms.get(i).get(2, 0),
                            "batRatedTotalVol": HHhdlist.bms.get(i).get(3, 0),
                            "singlBatMaxAllowVol": HHhdlist.bms.get(i).get(11, 0),
                            "maxAllowCur": HHhdlist.bms.get(i).get(12, 0),
                            "battotalEnergy": HHhdlist.bms.get(i).get(13, 0),
                            "maxVol": HHhdlist.bms.get(i).get(14, 0),
                            "maxTemp": HHhdlist.bms.get(i).get(15, 0),
                            "batCurVol": HHhdlist.bms.get(i).get(17, 0),
                        }
                        plamform_property(19, BMS)
                        HStategrid.save_dcBmsRunIty(BMS)
                        HHhdlist.bms_sum[i] = HHhdlist.bms_sum[i] + 1
            return "BMS"
        except Exception as e:
            HSyslog.log_info(f"Send_Property_to_Platform_BMS Failed. {e}")
            return ""


def _send_property_dc_input_meter():
    if HStategrid.get_property_status() == 1:
        try:
            for i in HHhdlist.meter.keys():
                dc_input_meter = {
                    "gunNo": i,
                    "acqTime": HHhdlist.unix_time_14(time.time()),
                    "mailAddr": "",
                    "meterNo": "",
                    "assetId": "",
                    "sumMeter": 0,
                    "ApElect": 0,
                    "BpElect": 0,
                    "CpElect": 0,
                }
                plamform_property(20, dc_input_meter)
            return "dc_input_meter"
        except Exception as e:
            HSyslog.log_info(f"Send_Property_to_Platform_dc_input_meter Failed. {e}")
            return ""


# -------------------- 发送服务 ------------------ #

def plamform_server() -> None:
    server_callback(2, service_query_log)
    server_callback(3, service_dev_maintain)
    server_callback(4, service_lockCtrl)
    server_callback(5, service_issue_feeModel)
    server_callback(6, service_startCharge)
    server_callback(7, service_authCharge)
    server_callback(8, service_stopCharge)
    server_callback(10, service_rsvCharge)
    server_callback(9, service_confirmTrade)
    server_callback(11, service_groundLock_ctrl)
    server_callback(12, service_gateLock_ctrl)
    server_callback(13, service_orderCharge)
    server_callback(0, service_get_config)
    server_callback(1, service_update_config)
    server_callback(25, service_ota_update)
    server_callback(24, service_time_sync)
    server_callback(15, service_state_ever)
    server_callback(16, service_connectSucc)
    server_callback(17, service_disConnected)
    server_callback(18, service_reportReply)
    server_callback(19, service_trigEvevtReply)
    server_callback(20, service_certGet)
    server_callback(21, service_certSet)
    server_callback(22, service_deregCodeGet)
    server_callback(23, service_uidGet)
    server_callback(14, service_mainres)


def service_query_log(data_json):  # 日志查询
    try:
        HSyslog.log_info(f"Service_query_log: {data_json}")
        info_dict = json.loads(data_json)
        data = {
            "gunNo": info_dict.get("gunNo"),
            "startDate": info_dict.get("startDate", ""),
            "stopDate": info_dict.get("stopDate", 0),
            "askType": info_dict.get("askType", 0),
            "result": 11,
            "logQueryNo": info_dict.get("logQueryNo", "")
        }
        json_str = json.dumps(data)
        send_logQueryEvt(info_dict)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_query_log error: {data_json} .{e}")
        info_dict = json.loads(data_json)
        data = {
            "gunNo": info_dict.get("gunNo"),
            "startDate": info_dict.get("startDate", ""),
            "stopDate": info_dict.get("stopDate", 0),
            "askType": info_dict.get("askType", 0),
            "result": 12,
            "logQueryNo": info_dict.get("logQueryNo", "")
        }
        json_str = json.dumps(data)
        return json_str


def service_dev_maintain(data_json):  # 充电机状态控制
    HSyslog.log_info(f"Service_dev_maintain: {data_json}")
    info_dict = json.loads(data_json)
    ctrlType = info_dict.get("ctrlType", -1)
    try:
        if ctrlType == 11:
            data = {
                "ctrlType": ctrlType,
                "reason": 10
            }
            HStategrid.save_DeviceInfo("device_status", 2, "", ctrlType)
            subprocess.run(['sudo', 'reboot'])
        elif ctrlType == 12:
            data = {
                "ctrlType": ctrlType,
                "reason": 10
            }
            HStategrid.save_DeviceInfo("device_status", 2, "", ctrlType)
        elif ctrlType == 13:
            data = {
                "ctrlType": ctrlType,
                "reason": 10
            }
            HStategrid.save_DeviceInfo("device_status", 2, "", ctrlType)
            subprocess.run(['supervisorctl', 'stop', 'internal'])
            subprocess.run(['supervisorctl', 'stop', 'internal_ui'])
        elif ctrlType == 14:
            data = {
                "ctrlType": ctrlType,
                "reason": 10
            }
            HStategrid.save_DeviceInfo("device_status", 2, "", ctrlType)
            subprocess.run(['supervisorctl', 'restart', 'internal_ocpp'])
            subprocess.run(['supervisorctl', 'restart', 'internal'])
            subprocess.run(['supervisorctl', 'restart', 'internal_ui'])
        elif ctrlType == 15:
            data = {
                "ctrlType": ctrlType,
                "reason": 10
            }
            HStategrid.save_DeviceInfo("device_status", 2, "", ctrlType)
            subprocess.run(['supervisorctl', 'stop', 'internal'])
            subprocess.run(['supervisorctl', 'stop', 'internal_ui'])
        elif ctrlType == 17:
            data = {
                "ctrlType": ctrlType,
                "reason": 10
            }
            HStategrid.save_DeviceInfo("device_status", 2, "", ctrlType)
        elif ctrlType == 16:
            data = {
                "ctrlType": ctrlType,
                "reason": 10
            }
            HStategrid.save_DeviceInfo("device_status", 2, "", ctrlType)
            subprocess.run(['supervisorctl', 'stop', 'internal'])
            subprocess.run(['supervisorctl', 'stop', 'internal_ui'])
        else:
            data = {
                "ctrlType": ctrlType,
                "reason": 12
            }
            HStategrid.save_DeviceInfo("device_status", 2, "", ctrlType)
        json_str = json.dumps(data)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_dev_maintain error. {data_json} .{e}")
        data = {
            "ctrlType": info_dict.get("ctrlType"),
            "reason": 12
        }
        json_str = json.dumps(data)
        return json_str


def service_lockCtrl(data_json):  # 电子锁控制
    HSyslog.log_info(f"Service_lockCtrl: {data_json}")
    info_dict = json.loads(data_json)
    lockParam = info_dict.get("lockParam", -1)
    try:
        if lockParam == 10:
            info = {
                'device_type': 2,
                'device_num': info_dict.get("gunNo") - 1,
                'source': 0,
                'count': 1,
                'items': [{"id": 90, "type": 0, "intvalue": 1}]
            }
            HTools.Htool_app_set_parameters(info)
        if lockParam == 11:
            info = {
                'device_type': 2,
                'device_num': info_dict.get("gunNo"),
                'source': 0,
                'count': 1,
                'items': [{"id": 90, "type": 0, "intvalue": 0}]
            }
            HTools.Htool_app_set_parameters(info)

        try:
            data = {
                "gunNo": info_dict.get("gunNo"),
                "lockStatus": lockParam,
                "resCode": 10
            }
            json_str = json.dumps(data)
            return json_str
        except Exception as e:
            HSyslog.log_info(f"lockParam: {e}")
            data = {
                "gunNo": info_dict.get("gunNo"),
                "lockStatus": lockParam,
                "resCode": 13
            }
            json_str = json.dumps(data)
            return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_lockCtrl .{data_json} .{e}")
        data = {
            "gunNo": info_dict.get("gunNo"),
            "lockStatus": lockParam,
            "resCode": 13
        }
        json_str = json.dumps(data)
        return json_str


def service_issue_feeModel(data_json):  # 费率更新
    HSyslog.log_info(f"Service_issue_feeModel: {data_json}")
    info_dict = json.loads(data_json)
    chargeFee = info_dict.get("chargeFee")
    serviceFee = info_dict.get("serviceFee")
    try:
        HStategrid.save_FeeModel(info_dict)
        HStategrid.fee_model["fee_elect"] = chargeFee
        HStategrid.fee_model["fee_ser"] = serviceFee
        HTools.Htool_app_charge_rate_sync_message(info_dict)  # 传入设备
        msg = HHhdlist.fee_queue.get(timeout=5)
        if msg != -1:
            json_str = json.dumps(msg)
        else:
            data = {
                "eleModelId": HStategrid.get_DeviceInfo("eleModelId"),
                "serModelId": HStategrid.get_DeviceInfo("serModelId"),
                "result": 12
            }
            json_str = json.dumps(data)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_issue_feeModel .{data_json} .{e}")
        data = {
            "eleModelId": HStategrid.get_DeviceInfo("eleModelId"),
            "serModelId": HStategrid.get_DeviceInfo("serModelId"),
            "result": 12
        }
        json_str = json.dumps(data)
        return json_str


def service_startCharge(data_json):  # 启动充电
    try:
        HSyslog.log_info(f"Service_startCharge: {data_json}")
        info_dict = json.loads(data_json)
        gunNo = info_dict.get("gunNo")
        if info_dict.get("startMode") == 10:
            if HHhdlist.device_charfer_p.get(gunNo) != {}:
                data = {
                    "gunNo": gunNo,
                    "preTradeNo": info_dict.get("preTradeNo", ""),
                    "tradeNo": info_dict.get("tradeNo", ""),
                    "startResult": 14,
                    "faultCode": 3062,
                    "vinCode": ""
                }
                send_startChaResEvt(data)
                eleModelId = HStategrid.get_DeviceInfo("eleModelId")
                serModelId = HStategrid.get_DeviceInfo("serModelId")
                info = {
                    "gunNo": gunNo,
                    "preTradeNo": info_dict.get("preTradeNo", ""),
                    "tradeNo": "",
                    "vinCode": "",
                    "timeDivType": 10,
                    "chargeStartTime": int(time.time()),
                    "chargeEndTime": int(time.time()),
                    "startSoc": 0,
                    "endSoc": 0,
                    "reason": 3062,
                    "eleModelId": eleModelId,
                    "serModelId": serModelId,
                    "sumStart": HHhdlist.meter.get(gunNo).get(0, 0),
                    "sumEnd": HHhdlist.meter.get(gunNo).get(0, 0),
                    "totalElect": 0,
                    "sharpElect": 0,
                    "peakElect": 0,
                    "flatElect": 0,
                    "valleyElect": 0,
                    "totalPowerCost": 0,
                    "totalServCost": 0,
                    "sharpPowerCost": 0,
                    "peakPowerCost": 0,
                    "flatPowerCost": 0,
                    "valleyPowerCost": 0,
                    "sharpServCost": 0,
                    "peakServCost": 0,
                    "flatServCost": 0,
                    "valleyServCost": 0
                }
                send_orderUpdateEvt(info)
                try:
                    data = {
                        "gunNo": info_dict.get("gunNo"),
                        "preTradeNo": info_dict.get("preTradeNo", ""),
                        "tradeNo": ""
                    }
                    json_str = json.dumps(data)
                    return json_str
                except Exception as e:
                    HSyslog.log_info(f"Service_startCharge .{data_json} .{e}")
                    return ""
            else:
                if gunNo not in HHhdlist.device_charfer_p or HHhdlist.device_charfer_p.get(gunNo) != {}:
                    HHhdlist.device_charfer_p[gunNo] = {}
                HHhdlist.device_charfer_p[gunNo].update({"preTradeNo": info_dict.get("preTradeNo")})
                HHhdlist.device_charfer_p[gunNo].update({"tradeNo": info_dict.get("tradeNo")})
                HHhdlist.device_charfer_p[gunNo].update({"startType": info_dict.get("startType")})
                HHhdlist.device_charfer_p[gunNo].update({"chargeMode": info_dict.get("chargeMode")})
                HHhdlist.device_charfer_p[gunNo].update({"limitData": info_dict.get("limitData")})
                HHhdlist.device_charfer_p[gunNo].update({"stopCode": str(info_dict.get("stopCode"))})
                HHhdlist.device_charfer_p[gunNo].update({"startMode": info_dict.get("startMode")})
                HHhdlist.device_charfer_p[gunNo].update({"insertGunTime": info_dict.get("insertGunTime")})

                info = {
                    "info_id": info_dict.get("info_id"),
                    "gunNo": gunNo,
                }
                HTools.Htool_app_charge_control(info)  # 传入设备
                tradeNo = str(HStategrid.get_DeviceInfo("deviceName") + str("{:02}".format(gunNo)) +
                              HHhdlist.unix_time(int(time.time())) + HStategrid.charging_num() +
                              HStategrid.do_charging_num())
                HHhdlist.device_charfer_p[gunNo].update({"tradeNo": tradeNo})

                try:
                    data = {
                        "gunNo": info_dict.get("gunNo"),
                        "preTradeNo": info_dict.get("preTradeNo", ""),
                        "tradeNo": tradeNo
                    }
                    json_str = json.dumps(data)
                    return json_str
                except Exception as e:
                    HSyslog.log_info(f"Service_startCharge .{data_json} .{e}")
                    return ""

        elif info_dict.get("startMode") == 11:
            if HHhdlist.device_charfer_p.get(gunNo) != {}:
                data = {
                    "gunNo": gunNo,
                    "preTradeNo": info_dict.get(gunNo).get("preTradeNo", ""),
                    "tradeNo": info_dict.get("tradeNo", ""),
                    "startResult": 14,
                    "faultCode": 1008,
                    "vinCode": ""
                }
                send_startChaResEvt(data)
                try:
                    data = {
                        "gunNo": info_dict.get("gunNo"),
                        "preTradeNo": info_dict.get("preTradeNo", ""),
                        "tradeNo": info_dict.get("tradeNo", "")
                    }
                    json_str = json.dumps(data)
                    return json_str
                except Exception as e:
                    HSyslog.log_info(f"Service_startCharge .{data_json} .{e}")
                    return ""
            else:
                if gunNo not in HHhdlist.device_charfer_p:
                    HHhdlist.device_charfer_p[gunNo] = {}
                HHhdlist.device_charfer_p[gunNo].update({"preTradeNo": info_dict.get("preTradeNo")})
                HHhdlist.device_charfer_p[gunNo].update({"tradeNo": info_dict.get("tradeNo")})
                HHhdlist.device_charfer_p[gunNo].update({"startType": info_dict.get("startType")})
                HHhdlist.device_charfer_p[gunNo].update({"chargeMode": info_dict.get("chargeMode")})
                HHhdlist.device_charfer_p[gunNo].update({"limitData": info_dict.get("limitData")})
                HHhdlist.device_charfer_p[gunNo].update({"stopCode": str(info_dict.get("stopCode"))})
                HHhdlist.device_charfer_p[gunNo].update({"startMode": info_dict.get("startMode")})
                HHhdlist.device_charfer_p[gunNo].update({"insertGunTime": info_dict.get("insertGunTime")})

                info = {
                    "info_id": info_dict.get("info_id"),
                    "gunNo": gunNo,
                }

                HTools.Htool_app_charge_control(info)  # 传入设备
                tradeNo = str(HStategrid.get_DeviceInfo("deviceName") + str("{:02}".format(gunNo)) +
                              HHhdlist.unix_time(int(time.time())) + HStategrid.charging_num() +
                              HStategrid.do_charging_num())
                HHhdlist.device_charfer_p[gunNo].update({"tradeNo": tradeNo})

                try:
                    data = {
                        "gunNo": info_dict.get("gunNo"),
                        "preTradeNo": info_dict.get("preTradeNo", ""),
                        "tradeNo": tradeNo
                    }
                    json_str = json.dumps(data)
                    return json_str
                except Exception as e:
                    HSyslog.log_info(f"Service_startCharge .{data_json} .{e}")
                    return ""

    except Exception as e:
        HSyslog.log_info(f"Service_startCharge .{data_json} .{e}")
        return ""


def service_authCharge(data_json):  # 鉴权结果
    try:
        HSyslog.log_info(f"Service_authCharge: {data_json}")
        info_dict = json.loads(data_json)
        gunNo = info_dict.get("gunNo")

        HHhdlist.device_charfer_p[gunNo].update({"preTradeNo": info_dict.get("preTradeNo")})
        HHhdlist.device_charfer_p[gunNo].update({"chargeMode": info_dict.get("chargeMode")})
        HHhdlist.device_charfer_p[gunNo].update({"limitData": info_dict.get("limitData")})
        HHhdlist.device_charfer_p[gunNo].update({"stopCode": str(info_dict.get("stopCode"))})
        HHhdlist.device_charfer_p[gunNo].update({"startMode": info_dict.get("startMode")})
        HHhdlist.device_charfer_p[gunNo].update({"insertGunTime": info_dict.get("insertGunTime")})
        HHhdlist.device_charfer_p[gunNo].update({"oppoCode": info_dict.get("oppoCode")})

        info = {
            "info_id": info_dict.get("info_id"),
            "gunNo": gunNo,
            "result": info_dict.get("result")
        }
        HTools.Htool_app_charge_control(info)  # 传入设备
    except Exception as e:
        HSyslog.log_info(f"Service_authCharge .{data_json} .{e}")
        return ""

    try:
        data = {
            "gunNo": info_dict.get("gunNo"),
            "preTradeNo": info_dict.get("preTradeNo", ""),
            "tradeNo": info_dict.get("tradeNo", "")
        }
        json_str = json.dumps(data)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_authCharge .{data_json} .{e}")
        return ""


def service_stopCharge(data_json):  # 停止充电
    try:
        HSyslog.log_info(f"Service_stopCharge: {data_json}")
        info_dict = json.loads(data_json)
        gunNo = info_dict.get("gunNo")
        if gunNo not in HHhdlist.device_charfer_p:
            HHhdlist.device_charfer_p[gunNo] = {}
        HHhdlist.device_charfer_p[gunNo].update({"stopReason": info_dict.get("stopReason", "")})
        info = {
            "info_id": info_dict.get("info_id"),
            "gunNo": gunNo,
        }
        HTools.Htool_app_charge_control(info)  # 传入设备
    except Exception as e:
        HSyslog.log_info(f"Service_stopCharge .{data_json} .{e}")
        return ""

    try:
        data = {
            "gunNo": info_dict.get("gunNo"),
            "preTradeNo": info_dict.get("preTradeNo", ""),
            "tradeNo": info_dict.get("tradeNo", "")
        }
        json_str = json.dumps(data)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_stopCharge .{data_json} .{e}")
        return ""


def service_rsvCharge(data_json):  # 预约充电
    try:
        HSyslog.log_info(f"Service_rsvCharge: {data_json}")
        info_dict = json.loads(data_json)
        data = {
            "gunNo": info_dict.get("gunNo"),
            "appomathod": info_dict.get("appomathod"),
            "ret": 12,
            "reason": 12
        }
        json_str = json.dumps(data)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_rsvCharge .{data_json} .{e}")
        return ""


def service_confirmTrade(data_json):  # 充电记录上传确认
    try:
        HSyslog.log_info(f"Service_confirmTrade: {data_json}")
        info_dict = json.loads(data_json)
        gunNo = info_dict.get("gunNo")
        if info_dict.get("errcode") == 10:
            result = 0x00
        else:
            result = 0x01

        if HHhdlist.device_charfer_p[gunNo] != {}:
            device_session_id = HHhdlist.device_charfer_p.get(gunNo).get("device_session_id", "")
            if device_session_id == "":
                if info_dict.get("preTradeNo") != "":
                    device_session_id = HStategrid.get_DeviceOrder_preTradeNo(info_dict.get("preTradeNo", ""))
                else:
                    device_session_id = HStategrid.get_DeviceOrder_tradeNo(info_dict.get("tradeNo", ""))
        else:
            if info_dict.get("preTradeNo") != "":
                device_session_id = HStategrid.get_DeviceOrder_preTradeNo(info_dict.get("preTradeNo", ""))
            else:
                device_session_id = HStategrid.get_DeviceOrder_tradeNo(info_dict.get("tradeNo", ""))

        msg_body = {
            'cloud_session_id': info_dict.get("preTradeNo", ""),
            'device_session_id': device_session_id,
            'result': result
        }
        HTools.Htool_app_charge_record_response(msg_body)  # 传入设备
        if info_dict.get("preTradeNo") != "":
            if info_dict.get("preTradeNo") == HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo", ""):
                HHhdlist.device_charfer_p.update({gunNo: {}})
                HHhdlist.bms_sum.update({gunNo: 1})
        else:
            if info_dict.get("tradeNo") == HHhdlist.device_charfer_p.get(gunNo).get("tradeNo", ""):
                HHhdlist.device_charfer_p.update({gunNo: {}})
                HHhdlist.bms_sum.update({gunNo: 1})
        return 0
    except Exception as e:
        HSyslog.log_info(f"Service_confirmTrade .{data_json} .{e}")
        return -1


def service_groundLock_ctrl(data_json):  # 地锁控制
    try:
        HSyslog.log_info(f"Service_groundLock_ctrl: {data_json}")
        info_dict = json.loads(data_json)
        data = {
            "gunNo": info_dict.get("gunNo"),
            "result": info_dict.get("result") + 1,
            "reason": 12
        }
        json_str = json.dumps(data)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_groundLock_ctrl .{data_json} .{e}")
        return ""


def service_gateLock_ctrl(data_json):  # 门锁控制
    try:
        HSyslog.log_info(f"Service_gateLock_ctrl: {data_json}")
        info_dict = json.loads(data_json)
        data = {
            "lockNo": info_dict.get("lockNo"),
            "result": 11
        }
        json_str = json.dumps(data)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_gateLock_ctrl .{data_json} .{e}")
        return ""


def service_orderCharge(data_json):  # 充电策略服务
    try:
        HSyslog.log_info(f"Service_orderCharge: {data_json}")
        info_dict = json.loads(data_json)
        try:
            log = threading.Thread(target=set_orderCharge, args=(info_dict,))
            log.start()
        except Exception as e:
            HSyslog.log_info(f"Service_orderCharge .{data_json} .{e}")
            return ""

        data = {
            "preTradeNo": info_dict.get("preTradeNo", ""),
            "result": 11,
            "reason": 10
        }
        json_str = json.dumps(data)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_orderCharge .{data_json} .{e}")
        return ""


def service_get_config(data_json):  # 获取配置
    try:
        HSyslog.log_info(f"Service_get_config: {data_json}")
        qrCode = []
        for i in range(0, HStategrid.gun_num):
            qrCode.append(HStategrid.get_DeviceInfo(f"qrCode{i}"))
        data = {
            "equipParamFreq": HStategrid.get_DeviceInfo("equipParamFreq"),
            "gunElecFreq": HStategrid.get_DeviceInfo("gunElecFreq"),
            "nonElecFreq": HStategrid.get_DeviceInfo("nonElecFreq"),
            "faultWarnings": HStategrid.get_DeviceInfo("faultWarnings"),
            "acMeterFreq": HStategrid.get_DeviceInfo("acMeterFreq"),
            "dcMeterFreq": HStategrid.get_DeviceInfo("dcMeterFreq"),
            "offlinChaLen": HStategrid.get_DeviceInfo("offlinChaLen"),
            "grndLock": HStategrid.get_DeviceInfo("grndLock"),
            "doorLock": HStategrid.get_DeviceInfo("doorLock"),
            "encodeCon": HStategrid.get_DeviceInfo("encodeCon"),
            "qrCode": qrCode
        }
        json_str = json.dumps(data)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_get_config .{data_json} .{e}")
        return ""


def service_update_config(data_json):  # 更新配置
    HSyslog.log_info(f"Service_update_config: {data_json}")
    info_dict = json.loads(data_json)
    HStategrid.save_DeviceInfo("equipParamFreq", 2, "null", info_dict.get("equipParamFreq"))
    HStategrid.save_DeviceInfo("gunElecFreq", 2, "null", info_dict.get("gunElecFreq"))
    HStategrid.save_DeviceInfo("nonElecFreq", 2, "null", info_dict.get("nonElecFreq"))
    HStategrid.save_DeviceInfo("faultWarnings", 2, "null", info_dict.get("faultWarnings"))
    HStategrid.save_DeviceInfo("acMeterFreq", 2, "null", info_dict.get("acMeterFreq"))
    HStategrid.save_DeviceInfo("dcMeterFreq", 2, "null", info_dict.get("dcMeterFreq"))
    HStategrid.save_DeviceInfo("offlinChaLen", 2, "null", info_dict.get("offlinChaLen"))
    HStategrid.save_DeviceInfo("grndLock", 2, "null", info_dict.get("grndLock"))
    HStategrid.save_DeviceInfo("doorLock", 2, "null", info_dict.get("doorLock"))
    HStategrid.save_DeviceInfo("encodeCon", 2, "null", info_dict.get("encodeCon"))
    try:
        info_offlinChaLen = {
            'device_type': 0,
            'device_num': 0,
            'source': 0,
            'count': 2,
            'items': [{"id": 125, "type": 0, "intvalue": 0},
                      {"id": 130, "type": 0, "intvalue": int(info_dict.get("offlinChaLen")) * 60}]
        }
        HTools.Htool_app_set_parameters(info_offlinChaLen)
    except Exception as e:
        HSyslog.log_info(f"Service_update_config .{info_offlinChaLen} .{e}")
        return -1

    try:
        global property_start
        global dcPile_property, fault_property, dc_work_property, dc_nonWork_property, dc_input_meter_property, BMS_property, meter_property
        HStategrid.set_flaut_status(1)
        if property_start == 0:
            plamform_property_thread(info_dict)
        else:
            dcPile_property.set_interval(info_dict.get("equipParamFreq"))
            fault_property.set_interval(info_dict.get("faultWarnings"))
            dc_work_property.set_interval(5)
            dc_nonWork_property.set_interval(info_dict.get("nonElecFreq"))
            dc_input_meter_property.set_interval(info_dict.get("acMeterFreq") * 60)
            BMS_property.set_interval(30)
            meter_property.set_interval(info_dict.get("dcMeterFreq") * 60)
    except Exception as e:
        HSyslog.log_info(f"Service_update_config .{e}")
        return -1

    try:
        deviceCode = HStategrid.get_DeviceInfo("deviceCode")
        gun_num = HStategrid.gun_num
        if HStategrid.Sign_type == HStategrid.SIGN_TYPE.deviceCode.value:
            qrCode = f"https://cdn-evone-oss.echargenet.com/IntentServe/index.html?M&qrcode=gwwl//:{HStategrid.Vendor_Code}:1.0.0:3:{deviceCode}:FFFFFFFFFFFF:00"
        elif HStategrid.Sign_type == HStategrid.SIGN_TYPE.deviceRegCode.value:
            qrCode = f"https://cdn-evone-oss.echargenet.com/IntentServe/index.html?M&qrcode=gwwl//:{HStategrid.Vendor_Code}:1.0.0:1:{deviceCode}:FFFFFFFFFFFF:00"
        else:
            deviceName = HStategrid.get_DeviceInfo("deviceName")
            qrCode = f"https://cdn-evone-oss.echargenet.com/IntentServe/index.html?M&qrcode=gwwl//:{HStategrid.Vendor_Code}:1.0.0:2:{deviceName}:FFFFFFFFFFFF:00"
        for i in range(0, gun_num):
            info_qrCode = {
                "gun_id": i,
                "source": i,
                "content": qrCode + f"{i + 1}",
            }
            HTools.Htool_app_QR_code_update(info_qrCode)

        for i in range(0, gun_num):
            HStategrid.save_DeviceInfo("qrCode" + str(i), 1, qrCode + f"{i + 1}", 0)
            return 10
    except Exception as e:
        HSyslog.log_info(f"qrCode .{data_json} .{e}")
        return -1


def service_ota_update(new_version: str):  # 固件升级
    status = 0
    try:
        for gun, charge in HHhdlist.device_charfer_p.items():
            if charge == {}:
                status = status + 1
    except Exception as e:
        HSyslog.log_info(f"Service_ota_update .{status} .{e}")
        return [-4, -4]

    if status == HStategrid.gun_num:
        if new_version == "suss":
            try:
                ota_info = {
                    "mode": 1,
                    "type": 0x04,
                    "device_id": 0xff,
                    "command": 1,
                    "auto_exit": 1,
                    "soft_version": HStategrid.get_before_last_dot(HStategrid.dtu_ota)[0],
                    "hard_version": "20.0.0",
                    "location": "/opt/hhd/dtu20.tar.gz",
                }
                HTools.Htool_app_upgrade_control(ota_info)
            except Exception as e:
                HSyslog.log_info(f"Service_ota_update .{new_version} .{e}")
                return [-4, -4]

        else:
            try:
                dtu_ota_version = HStategrid.get_VerInfoEvt(4)
                if new_version != dtu_ota_version:
                    HHhdlist.ota_version = new_version
                    HSyslog.log_info(f"new_version: {new_version}")
                    HStategrid.dtu_ota = new_version
                    buffer = (" " * (8 * 1024 * 1024)).encode("utf-8")
                    size = len(buffer)
                    return [buffer, size]
                else:
                    HSyslog.log_info(f"ota: {new_version}")
            except Exception as e:
                HSyslog.log_info(f"Service_ota_update .{new_version} .{e}")
                return [-4, -4]
    else:
        get_otaprogress(-4)
        return [-4, -4]


def service_time_sync(data_json):  # 时钟同步
    try:
        HSyslog.log_info(f"Service_time_sync: {data_json}")
        HSyslog.log_info(data_json)
        info_dict = json.loads(data_json)
        time_dict = {
            "year": info_dict.get("year"),
            "month": info_dict.get("month"),
            "day": info_dict.get("day"),
            "hour": info_dict.get("hour"),
            "minute": info_dict.get("minute"),
            "second": info_dict.get("second"),
        }
        HTools.Htool_app_time_sync(time_dict)
        year = info_dict.get("year")
        month = info_dict.get("month")
        day = info_dict.get("day")
        hour = info_dict.get("hour")
        minute = info_dict.get("minute")
        second = info_dict.get("second")

        time_obj = datetime(year, month, day, hour, minute, second)
        # 转换为所需格式的字符串
        formatted_time = time_obj.strftime("%Y-%m-%d %H:%M:%S")
        command_time = f"sudo date -s '{formatted_time}'"
        subprocess.run(command_time, shell=True, check=True, capture_output=True, text=True)
        command = f"sudo hwclock --systohc"
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return 0
    except Exception as e:
        HSyslog.log_info(f"Service_time_sync .{data_json} .{e}")
        return ""


def service_state_ever(data_json):  # 打印消息
    info_dict = json.loads(data_json)
    # print("\033[92m",
    #       "received state event -- ",
    #       "0x{:04X}".format(-info_dict.get("ev")),
    #       info_dict.get("msg"),
    #       "\033[0m")


def service_connectSucc(data_json):  # 连接成功
    try:
        HSyslog.log_info(f"Service_connectSucc: {data_json}")
        info_dict = json.loads(data_json)
        HStategrid.set_link_init_status(info_dict.get("onlink_status"))
        while True:
            if HHhdlist.device_mqtt_status:
                HStategrid.set_flaut_status(1)
                send_firmwareEvt()
                send_verInfoEvt("DTU")
                send_askConfigEvt()
                command_time = f"sudo cp /opt/hhd/ex_cloud/DeviceCode.json /root"
                subprocess.run(command_time, shell=True, check=True, capture_output=True, text=True)
                if HStategrid.fee_model.get("fee_elect") is None or HStategrid.fee_model.get("fee_ser") is None:
                    HStategrid.get_FeeModel()
                break
        HSyslog.log_info(f"onlink_status: {HStategrid.link_init_status}")
        return HStategrid.get_link_init_status()
    except Exception as e:
        HSyslog.log_info(f"Service_connectSucc .{data_json} .{e}")
        return -1


def service_disConnected(data_json):  # 断开连接
    try:
        HTools.Htool_app_net_status(HHhdlist.net_type.no_net.value, 0, HHhdlist.net_id.id_4G.value)
        HSyslog.log_info(f"Service_disConnected: {data_json}")
        info_dict = json.loads(data_json)
        HStategrid.set_link_init_status(info_dict.get("onlink_status"))
        HSyslog.log_info(f"onlink_status: {HStategrid.link_init_status}")
        return HStategrid.get_link_init_status()
    except Exception as e:
        HSyslog.log_info(f"Service_disConnected .{data_json} .{e}")
        return -1


def service_reportReply(data_json):  # 属性回调
    pass


def service_trigEvevtReply(data_json):  # 事件回调
    try:
        data_dict = json.loads(data_json)
        msgid = data_dict.get("msgid")
        code = data_dict.get("code")
        message = data_dict.get("message")

        # if HStategrid.ack_num == {}:
        #     return -1
        # else:
        #     if msgid in HStategrid.ack_num.keys() and code == 200 and message == "success":
        #         HStategrid.ack_num[msgid].update({"ack": True})
        #     else:
        #         HStategrid.ack_num[msgid].update({"ack": False})
    except Exception as e:
        HSyslog.log_info(f"Service_trigEvevtReply .{data_json} .{e}")
        return -1


def service_certGet(data_json):  # 获取属性
    pass


def service_certSet(data_json):  # 设置属性
    try:
        HSyslog.log_info(f"Service_certSet: {data_json}")
        info_dict = json.loads(data_json)
        HStategrid.save_DeviceInfo("Vendor_Code", 1, f"{HStategrid.Vendor_Code}", 0)
        HStategrid.save_DeviceInfo("device_type", 1, "01", 0)
        HStategrid.save_DeviceInfo("productKey", 1, info_dict.get("product_key"), 0)
        HStategrid.save_DeviceInfo("deviceName", 1, info_dict.get("device_name"), 0)
        HStategrid.save_DeviceInfo("deviceSecret", 1, info_dict.get("device_secret"), 0)

        return 0
    except Exception as e:
        HSyslog.log_info(f"Service_certSet .{data_json} .{e}")
        return -1


def service_deregCodeGet(data_json):  # 获取注册码
    try:
        HSyslog.log_info(f"Service_deregCodeGet: {data_json}")
        device_reg_code = HStategrid.get_DeviceInfo("registerCode")
        if device_reg_code is not None and device_reg_code != "":
            return device_reg_code
        else:
            return ""
    except Exception as e:
        HSyslog.log_info(f"Service_deregCodeGet .{data_json} .{e}")
        return -1


def service_uidGet(data_json):  # 获取设备UID
    try:
        HSyslog.log_info(f"Service_uidGet: {data_json}")
        deviceCode = HStategrid.get_DeviceInfo("deviceCode")
        if deviceCode is not None and deviceCode != "":
            return deviceCode
    except Exception as e:
        HSyslog.log_info(f"Service_uidGet .{data_json} .{e}")
        return -1


def service_mainres(data_json):  # 设备状态查询
    try:
        HSyslog.log_info(f"Service_mainres: {data_json}")
        info_dict = json.loads(data_json)
        ctrlType = HStategrid.get_DeviceInfo("device_status")
        if ctrlType is None:
            ctrlType = 14
        data = {
            "ctrlType": ctrlType,
            "result": 10
        }
        json_str = json.dumps(data)
        HSyslog.log_info(json_str)
        return json_str
    except Exception as e:
        HSyslog.log_info(f"Service_mainres .{data_json} .{e}")
        return ""


def send_firmwareEvt():
    param_id = [135, 103, 110, 121, 113, 114, 115, 117, 101, 104, 111, 129, 141, 116]
    get_data = {
        "device_type": 0,
        "device_num": 0,
        "model": 0,
        "source": 0,
        "count": len(param_id),
        "param_id": param_id,
    }
    HTools.Htool_app_fetch_parameter(get_data)
    time.sleep(1)
    try:
        eleModelId = HStategrid.get_DeviceInfo("eleModelId")
        serModelId = HStategrid.get_DeviceInfo("serModelId")
        HStategrid.gun_num = HStategrid.get_DeviceInfo("00110")
        if HStategrid.get_DeviceInfo("00141") is not None:
            if HStategrid.get_DeviceInfo("00141") == 0 or HStategrid.get_DeviceInfo("00141") == 1:
                stakeModel = f"HHD_DC_All-in-One PC_{HStategrid.gun_num}"
                # stakeModel = f"HQC-SDK"
                HHhdlist.device_type = 1
            else:
                stakeModel = f"HHD_Qunchong PC_{HStategrid.gun_num}"
                HHhdlist.device_type = 2
        else:
            stakeModel = f"HHD_DC_All-in-One PC_{HStategrid.gun_num}"
        if eleModelId is None or eleModelId == "":
            eleModelId = ""
        if serModelId is None or serModelId == "":
            serModelId = ""
        outMeter = []
        if HStategrid.get_DeviceInfo("meter1") is not None and HStategrid.get_DeviceInfo("meter1") != "":
            for i in range(1, HStategrid.gun_num + 1):
                outMeter.append(HStategrid.hex_to_ascii(HStategrid.get_DeviceInfo(f"meter{i}")))
        else:
            for i in range(1, HStategrid.gun_num + 1):
                if i % 2 == 1:
                    outMeter.append(HStategrid.hex_to_ascii("{:02}".format(i) + "000000000055"))
                    HStategrid.save_DeviceInfo(f"meter{i}", 1, "{:02}".format(i) + "000000000055", 0)
                if i % 2 == 0:
                    outMeter.append(HStategrid.hex_to_ascii("{:02}".format(i) + "000000000066"))
                    HStategrid.save_DeviceInfo(f"meter{i}", 1, "{:02}".format(i) + "000000000066", 0)
        simNo = HStategrid.get_DeviceInfo("00102")
        if simNo is None:
            simNo = ""
        info_dict = {
            "simNo": simNo,
            "eleModelId": eleModelId,
            "serModelId": serModelId,
            "stakeModel": stakeModel,
            "vendorCode": int(HStategrid.Vendor_Code),
            "simMac": str(HStategrid.get_mac_address("eth1")),
            "devSn": str(HStategrid.get_DeviceInfo("deviceCode")),
            "devType": 12,
            "portNum": HStategrid.gun_num,
            "longitude": 0,
            "latitude": 0,
            "height": 0,
            "gridType": 10,
            "btMac": "",
            "meaType": 10,
            "otRate": HStategrid.gun_num * HStategrid.get_DeviceInfo("00117") * 0.01,
            # "otRate": 1200,
            "otMinVol": float(HStategrid.get_DeviceInfo("00114") * 0.1),
            "otMaxVol": float(HStategrid.get_DeviceInfo("00113") * 0.1),
            # "otMinVol": 2000,
            # "otMaxVol": 10000,
            "otCur": 2500,
            "inMeter": [],
            "outMeter": outMeter,
            "CT": 0,
            "isGateLock": 10,
            "isGroundLock": 10
        }
        if HHhdlist.device_charfer_p == {}:
            for i in range(0, HStategrid.gun_num):
                HHhdlist.device_charfer_p[i + 1] = {}
        deviceCode = HStategrid.get_DeviceInfo("deviceCode")
        if HStategrid.Sign_type == HStategrid.SIGN_TYPE.deviceCode.value:
            qrCode = f"https://cdn-evone-oss.echargenet.com/IntentServe/index.html?M&qrcode=gwwl//:{HStategrid.Vendor_Code}:1.0.0:3:{deviceCode}:FFFFFFFFFFFF:00"
        elif HStategrid.Sign_type == HStategrid.SIGN_TYPE.deviceRegCode.value:
            qrCode = f"https://cdn-evone-oss.echargenet.com/IntentServe/index.html?M&qrcode=gwwl//:{HStategrid.Vendor_Code}:1.0.0:1:{deviceCode}:FFFFFFFFFFFF:00"
        else:
            deviceName = HStategrid.get_DeviceInfo("deviceName")
            qrCode = f"https://cdn-evone-oss.echargenet.com/IntentServe/index.html?M&qrcode=gwwl//:{HStategrid.Vendor_Code}:1.0.0:2:{deviceName}:FFFFFFFFFFFF:00"
        qrcode_ack = {}
        HSyslog.log_info(HStategrid.gun_num)
        for i in range(0, HStategrid.gun_num):
            info_qrCode = {
                "gun_id": i,
                "source": i,
                "content": qrCode + f"{i + 1}",
            }
            HTools.Htool_app_QR_code_update(info_qrCode)
            qrcode_ack.update({i: True})
        plamform_event(0, info_dict)
        HHhdlist.save_json_config({"qrcode": qrcode_ack})
        for i in range(0, HStategrid.gun_num):
            HStategrid.save_DeviceInfo("qrCode" + str(i), 1, qrCode + f"{i + 1}", 0)
        return 0
    except Exception as e:
        HSyslog.log_info(f"send_firmwareEvts error: {e}")
        return -1


def send_askFeeModelEvt(info_dict: dict):
    HTools.Htool_app_charge_rate_request_response(0)
    return plamform_event(1, info_dict)


def send_startChargeAuthEvt(info_dict: dict):
    return plamform_event(2, info_dict)


def send_startChaResEvt(info_dict: dict):
    return plamform_event(3, info_dict)


def send_stopChaResEvt(info_dict: dict):
    return plamform_event(4, info_dict)


def send_orderUpdateEvt(info_dict):
    return plamform_event(5, info_dict)


def send_totalFaultEvt(info_dict):
    return plamform_event(6, info_dict)


def send_dcStChEvt(info_dict):
    return plamform_event(8, info_dict)


def send_groundLockEvt():
    info_dict = {
        "gunNo": 0,
        "lockState": 0,
        "powerType": 0,
        "cellState": 0,
        "lockerState": 0,
        "lockerForced": 0,
        "lowPower": 0,
        "soc": 0,
        "openCnt": 0,
    }
    return plamform_event(9, info_dict)


def send_smartLockEvent():
    info_dict = {
        "lockNo": 0,
        "lockState": 0,
    }
    return plamform_event(10, info_dict)


def send_askConfigEvt():
    if HStategrid.get_DeviceInfo("equipParamFreq"):
        global property_start
        global dcPile_property, fault_property, dc_work_property, dc_nonWork_property, dc_input_meter_property, BMS_property, meter_property
        try:
            qrCode = []
            for i in range(0, HStategrid.gun_num):
                qrCode.append(HStategrid.get_DeviceInfo(f"qrCode{i}"))
            info_dict = {
                "equipParamFreq": HStategrid.get_DeviceInfo("equipParamFreq"),
                "gunElecFreq": HStategrid.get_DeviceInfo("gunElecFreq"),
                "nonElecFreq": HStategrid.get_DeviceInfo("nonElecFreq"),
                "acMeterFreq": HStategrid.get_DeviceInfo("acMeterFreq"),
                "dcMeterFreq": HStategrid.get_DeviceInfo("dcMeterFreq"),
                "faultWarnings": HStategrid.get_DeviceInfo("faultWarnings"),
                "offlinChaLen": HStategrid.get_DeviceInfo("offlinChaLen"),
                "grndLock": HStategrid.get_DeviceInfo("grndLock"),
                "doorLock": HStategrid.get_DeviceInfo("doorLock"),
                "encodeCon": HStategrid.get_DeviceInfo("encodeCon"),
                "qrCode": qrCode
            }
            time.sleep(0.1)
        except Exception as e:
            HSyslog.log_info(f"Send_askConfigEvt .{info_dict} .{e}")
        try:
            HStategrid.set_flaut_status(1)
            if property_start == 0:
                plamform_property_thread(info_dict)
            else:
                dcPile_property.set_interval(info_dict.get("equipParamFreq"))
                fault_property.set_interval(info_dict.get("faultWarnings"))
                dc_work_property.set_interval(5)
                dc_nonWork_property.set_interval(info_dict.get("nonElecFreq"))
                dc_input_meter_property.set_interval(info_dict.get("acMeterFreq") * 60)
                BMS_property.set_interval(30)
                meter_property.set_interval(info_dict.get("dcMeterFreq") * 60)

            set_data_dev_config(json.dumps(info_dict))
            return 0
        except Exception as e:
            HSyslog.log_info(f"Send_askConfigEvt .{info_dict} .{e}")
            return -1
    else:
        info_dict = {
            "dev": "SDK_v1.1.7"
        }
        return plamform_event(11, info_dict)


def send_verInfoEvt(device_type):
    for device, device_code in HStategrid.device_hard.items():
        if device == device_type:
            data = {
                "type": device_code,
                "device_id": 255
            }
            HTools.Htool_app_read_version_number(data)
            time.sleep(1)
        try:
            data = HStategrid.get_VerInfoEvt(device_code)
            sdk_version = HStategrid.get_DeviceInfo("SDKVersion")
            ui_version = HStategrid.get_DeviceInfo("UIVersion")
            info_dict = {
                "devRegMethod": 10,
                "pileSoftwareVer": f"Charger:{data[0]}",
                "pileHardwareVer": data[1],
                "sdkVer": "SDK_v1.1.7"
            }
            return plamform_event(13, info_dict)
        except Exception as e:
            HSyslog.log_info(f"Send_verInfoEvt .{e}")
            return -1


def send_logQueryEvt(info_dict):
    log = threading.Thread(target=get_log, args=(info_dict,), daemon=True)
    log.start()


def get_log(info_dict: dict):
    startDate = info_dict.get("startDate")
    stopDate = info_dict.get("stopDate")
    log_path = "/opt/hhd/LOG"
    syslog_path = "/var/log"
    if info_dict.get("askType") == 12:
        files = [f for f in os.listdir(log_path) if os.path.isfile(os.path.join(log_path, f))]
        log_list = []
        for file in files:
            file_path = os.path.join(log_path, file)
            with open(file_path, "r", encoding='utf-8') as f:
                lines = f.readlines()
                first_line = lines[0].strip()[:19] if lines else ""
                last_line = lines[-1].strip()[:19] if lines else ""
            first_time = int(datetime.timestamp(datetime.strptime(first_line, '%Y-%m-%d %H:%M:%S')))
            last_time = int(datetime.timestamp(datetime.strptime(last_line, '%Y-%m-%d %H:%M:%S')))
            if last_time <= int(startDate):
                pass
            elif first_time <= int(startDate) and (int(startDate) <= last_time <= int(stopDate)):
                log_list.append({file: [int(startDate), last_time]})
            elif first_time >= int(startDate) and last_time <= int(stopDate):
                log_list.append({file: [first_time, last_time]})
            elif first_time <= int(stopDate) <= last_time:
                log_list.append({file: [first_time, int(stopDate)]})
            elif first_time >= int(stopDate):
                pass
            else:
                pass
        sorted_list = sorted(log_list, key=lambda x: list(x.values())[0][0])

        for log_file in sorted_list:
            file_path = os.path.join(log_path, list(log_file.keys())[0])
            with open(file_path, "r", encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    log_first = int(datetime.timestamp(datetime.strptime(line.strip()[:19], '%Y-%m-%d %H:%M:%S')))
                    if int(startDate) <= log_first <= int(stopDate):
                        data = {
                            "gunNo": info_dict.get("gunNo"),
                            "startDate": startDate,
                            "stopDate": stopDate,
                            "askType": info_dict.get("askType"),
                            "result": 11,
                            "logQueryNo": info_dict.get("logQueryNo"),
                            "retType": 10,
                            "logQueryEvtSum": 1,
                            "logQueryEvtNo": 1,
                            "dataArea": str(line).
                            replace('"', "'").
                            replace(',', ';'),
                        }
                        plamform_event(14, data)
                        time.sleep(0.1)
    if info_dict.get("askType") == 10:
        preTradeNo_order = HStategrid.get_log_DeviceOrder(startDate, stopDate)
        for order in preTradeNo_order:
            dict_info = {
                "gunNo": order[1],
                "preTradeNo": order[2],
                "tradeNo": order[3],
                "vinCode": order[4],
                "timeDivType": order[5],
                "chargeStartTime": order[6],
                "chargeEndTime": order[7],
                "startSoc": order[8],
                "endSoc": order[9],
                "reason": order[10],
                "eleModelId": order[11],
                "serModelId": order[12],
                "sumStart": order[13],
                "sumEnd": order[14],
                "totalElect": order[15],
                "sharpElect": order[16],
                "peakElect": order[17],
                "flatElect": order[18],
                "valleyElect": order[19],
                "totalPowerCost": order[20],
                "totalServCost": order[21],
                "sharpPowerCost": order[22],
                "peakPowerCost": order[23],
                "flatPowerCost": order[24],
                "valleyPowerCost": order[25],
                "sharpServCost": order[26],
                "peakServCost": order[27],
                "flatServCost": order[28],
                "valleyServCost": order[29],
            }
            data = {
                "gunNo": info_dict.get("gunNo"),
                "startDate": startDate,
                "stopDate": stopDate,
                "askType": info_dict.get("askType"),
                "result": 11,
                "logQueryNo": info_dict.get("logQueryNo"),
                "retType": 10,
                "logQueryEvtSum": 1,
                "logQueryEvtNo": 1,
                "dataArea": dict_info
            }
            plamform_event(14, data)
            time.sleep(0.1)
    if info_dict.get("askType") == 11:
        dcOutMeterIty_list = HStategrid.get_log_dcOutMeterIty(startDate, stopDate)
        for order in dcOutMeterIty_list:
            dict_info = {
                "gunNo": order[1],
                "acqTime": order[2],
                "mailAddr": HStategrid.hex_to_ascii(order[3]),
                "meterNo": HStategrid.hex_to_ascii(order[4]),
                "assetId": order[5],
                "sumMeter": order[6],
                "lastTrade": order[8],
                "elec": order[7],
            }
            data = {
                "gunNo": info_dict.get("gunNo"),
                "startDate": startDate,
                "stopDate": stopDate,
                "askType": info_dict.get("askType"),
                "result": 11,
                "logQueryNo": info_dict.get("logQueryNo"),
                "retType": 10,
                "logQueryEvtSum": 1,
                "logQueryEvtNo": 1,
                "dataArea": dict_info
            }
            plamform_event(14, data)
            time.sleep(0.1)
    if info_dict.get("askType") == 13:
        file_pattern = os.path.join(syslog_path, 'syslog*')
        all_syslog_files = glob.glob(file_pattern)
        gz_files = [file for file in all_syslog_files if file.endswith('.gz')]
        normal_files = [file for file in all_syslog_files if not file.endswith('.gz')]
        all_files = gz_files + normal_files
        sorted_files = sorted(all_files, key=os.path.getmtime)
        for file in sorted_files:
            if file.endswith('.gz'):
                with gzip.open(file, 'rt', encoding='gbk', errors='ignore') as file:  # 使用 'rt' 模式读取文本内容
                    for line in file:
                        first_15_chars = line[:15]
                        timestamp = int(HStategrid.date_to_time(first_15_chars))
                        if int(startDate) <= timestamp <= int(stopDate):
                            data = {
                                "gunNo": info_dict.get("gunNo"),
                                "startDate": startDate,
                                "stopDate": stopDate,
                                "askType": info_dict.get("askType"),
                                "result": 11,
                                "logQueryNo": info_dict.get("logQueryNo"),
                                "retType": 10,
                                "logQueryEvtSum": 1,
                                "logQueryEvtNo": 1,
                                "dataArea": str(line).
                                replace('"', "'").
                                replace(',', ';'),
                            }
                            HSyslog.log_info(data)
                            plamform_event(14, data)
                            time.sleep(0.1)
            else:
                with open(file, 'r', encoding='gbk', errors='ignore') as file:
                    for line in file:
                        first_15_chars = line[:15]
                        timestamp = int(HStategrid.date_to_time(first_15_chars))
                        if int(startDate) <= timestamp <= int(stopDate):
                            data = {
                                "gunNo": info_dict.get("gunNo"),
                                "startDate": startDate,
                                "stopDate": stopDate,
                                "askType": info_dict.get("askType"),
                                "result": 11,
                                "logQueryNo": info_dict.get("logQueryNo"),
                                "retType": 10,
                                "logQueryEvtSum": 1,
                                "logQueryEvtNo": 1,
                                "dataArea": str(line).
                                replace('"', "'").
                                replace(',', ';'),
                            }
                            HSyslog.log_info(data)
                            plamform_event(14, data)
                            time.sleep(0.1)
    if info_dict.get("askType") == 14:
        dcBmsRunIty_list = HStategrid.get_log_dcBmsRunIty(startDate, stopDate)
        for order in dcBmsRunIty_list:
            dict_info = {
                "gunNo": order[1],
                "preTradeNo": order[2],
                "tradeNo": order[3],
                "socVal": order[4],
                "BMSVer": order[5],
                "BMSMaxVol": order[6],
                "batType": order[7],
                "batRatedCap": order[8],
                "batRatedTotalVol": order[9],
                "singlBatMaxAllowVol": order[10],
                "maxAllowCur": order[11],
                "battotalEnergy": order[12],
                "maxVol": order[13],
                "maxTemp": order[14],
                "batCurVol": order[15],
            }
            data = {
                "gunNo": info_dict.get("gunNo"),
                "startDate": startDate,
                "stopDate": stopDate,
                "askType": info_dict.get("askType"),
                "result": 11,
                "logQueryNo": info_dict.get("logQueryNo"),
                "retType": 10,
                "logQueryEvtSum": 1,
                "logQueryEvtNo": 1,
                "dataArea": dict_info
            }
            plamform_event(14, data)
            time.sleep(0.1)


def set_orderCharge(info_dict: dict):
    HSyslog.log_info("开始限功率 。。。 ")
    preTradeNo = info_dict.get("preTradeNo")
    num = info_dict.get("num")
    validTime = info_dict.get("validTime")
    kw = info_dict.get("kw")
    charger_power = []
    for i in range(0, num):
        if i == 0 and validTime[i] != "0000":
            charger_power.append({"start_time": "0000", "stop_time": validTime[i], "kw": kw[num - 1]})
        elif i == num - 1 and validTime[i] != "2400":
            charger_power.append({"start_time": validTime[i], "stop_time": "2400", "kw": kw[i]})
        else:
            if i == num - 1 and validTime[i] == "2400":
                pass
            else:
                charger_power.append({"start_time": validTime[i], "stop_time": validTime[i + 1], "kw": kw[i]})

    gunNo = None
    for gun, data in HHhdlist.device_charfer_p.items():
        if data.get("preTradeNo") == preTradeNo:
            gunNo = gun

    if gunNo is not None and charger_power != []:
        while True:
            for power in charger_power:
                if preTradeNo == HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo"):
                    if int(power.get("stop_time")) >= int(HStategrid.get_current_time_hhmm()) > int(power.get("start_time")):
                        HSyslog.log_info(f"充电电压： {HHhdlist.gun.get(gunNo).get(112)}")
                        HSyslog.log_info(f"充电电流： {HHhdlist.gun.get(gunNo).get(113)}")
                        HSyslog.log_info(f"充电功率： {HHhdlist.gun.get(gunNo).get(112) * HHhdlist.gun.get(gunNo).get(113)}")
                        wk = power.get("kw") * 10000
                        HSyslog.log_info(f"限功率： {wk}")
                        if abs((HHhdlist.gun.get(gunNo).get(112) * HHhdlist.gun.get(gunNo).get(113)) - (power.get("kw") * 10000)) > 50000:
                            info_orderCharge = {
                                'device_type': 2,
                                'device_num': gunNo - 1,
                                "source": 0,
                                'count': 1,
                                'items': [{"id": 169, "type": 0, "intvalue": power.get("kw") * 10}]
                            }
                            HTools.Htool_app_set_parameters(info_orderCharge)
                            time.sleep(30)
                        else:
                            time.sleep(30)
                    else:
                        time.sleep(1)
                else:
                    info_orderCharge = {
                        'device_type': 2,
                        'device_num': gunNo - 1,
                        'count': 1,
                        "source": 0,
                        'items': [{"id": 169, "type": 0, "intvalue": 25000}]
                    }
                    HTools.Htool_app_set_parameters(info_orderCharge)
                    return False
    else:
        return False
