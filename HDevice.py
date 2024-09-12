#!/bin/python3

from enum import Enum
import random
from paho.mqtt import client as mqtt_client
import time
import queue

import HSyslog
import HTools
import HStategrid
import HHhdlist

from PROTOCOL import *

thmc = None
DtoP_queue = queue.Queue()
package_num = 0  # 包序号


class HMqttClient:
    def __init__(self, broker, port) -> None:
        self.broker = broker
        self.port = port
        self.topiclist = None
        self.connectStatus = False
        self.client_id = None
        self.clientDev = None

    def connect_mqtt(self) -> mqtt_client:
        self.client_id = f'internation-{random.randint(0, 1000)}'
        client = mqtt_client.Client(self.client_id)
        client.on_connect = self.on_connect  # 连接成功时的回调函数
        client.on_message = self.on_message  # 连接成功时的订阅函数
        client.on_disconnect = self.on_disconnect  # 断开连接的回调函数
        client.connect(self.broker, self.port, keepalive=60)
        self.clientDev = client
        return self.clientDev

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connectStatus = True
            HSyslog.log_info("Connected to MQTT Broker!")
            HHhdlist.device_mqtt_status = True
        else:
            self.connectStatus = False
            HSyslog.log_info(f"Failed to connect, return code {rc}")
            HHhdlist.device_mqtt_status = False

    def on_message(self, client, userdata, msg):
        self.__subscribe(msg.payload.decode('utf-8', 'ignore'), msg.topic)

    def on_disconnect(self, client, userdata, rc):
        HSyslog.log_info("check connection is closed! rc = {}".format(rc))
        self.connectStatus = False
        self.clientDev.disconnect()

    def on_publish(self, client, userdata, mid):
        pass

    def init_mqtt(self, client):
        client.on_publish = self.on_publish
        client.on_disconnect = self.on_disconnect

    def subscribe(self):  # 订阅
        for dic in app_func_dict.keys():
            if app_func_dict.get(dic).get("isSubscribe"):
                self.clientDev.subscribe(topic=dic, qos=app_func_dict.get(dic).get("qos"))
        if HStategrid.link_init_status == 1:
            app_net_status(HHhdlist.net_type.net_4G.value, 3, HHhdlist.net_id.id_4G.value)
        else:
            app_net_status(HHhdlist.net_type.no_net.value, 0, HHhdlist.net_id.id_4G.value)

    def publish(self, topic, msg, qos):  # 发布
        if self.connectStatus:
            result = self.clientDev.publish(topic, msg, qos)
            if not result[0]:
                print(f"Send: {msg} to topic: {topic}")
                if topic != '/hqc/sys/network-state':
                    HSyslog.log_info(f"Send_to_Device: {msg} to topic: {topic}")
                return True
            else:
                HSyslog.log_info(f"Failed to send message to topic {topic}")
                return False

        return False

    def __subscribe(self, msg, topic) -> bool:
        print(f"Received: {msg} from topic:{topic}")
        if topic != "/hqc/main/telemetry-notify/info":
            HSyslog.log_info(f"Received_from_Device: {msg} to topic: {topic}")
        app_subscribe(msg, topic)
        return True


def analysis_msg_dict(func_dict: dict, msg_dict: dict, topic: str):
    version = msg_dict.get('version', "")  # string
    package_num = msg_dict.get('package_num', -1)  # int
    package_seq = msg_dict.get('package_seq', -1)  # int
    sub_pkt_num = msg_dict.get('sub_pkt_num', -1)  # int
    need_response = msg_dict.get('need_response', False)  # bool
    func_dict['func'](msg_dict.get('body', {}))


def app_subscribe(msg: str, topic: str):
    if topic not in app_func_dict.keys():
        HSyslog.log_info("does not exist this topic")
        return False
    if not app_func_dict[topic]['func']:
        return False
    msg_dict = json.loads(msg)
    analysis_msg_dict(app_func_dict[topic], msg_dict, topic)


def modify_msg_head(msg: dict):
    global package_num
    package_num += 1
    msg['package_num'] = package_num
    '''修改包间序号，分包数量，消息是否需要确认'''

    return msg


def app_publish(topic: str, msg_body: dict):
    msg_dict = {'version': '1.1.1',
                'package_num': -1,  # 包序号
                'package_seq': 1,  # 包头序号
                'sub_pkt_num': 1,  # 分包数量
                'need_response': False,  # 消息是否需要确认
                'body': msg_body
                }
    '''修改包头'''
    msg_dict = modify_msg_head(msg_dict)
    msg = json.dumps(msg_dict)
    qos = app_func_dict[topic]["qos"]
    msg = {"topic": topic, "msg": msg, "qos": qos}
    if msg_body.get("info_id", -1) != -1:
        if msg_body.get("info_id", -1) == 8:
            HHhdlist.device_charfer_p[msg_body.get("gun_id") + 1]["stop_package_num"] = msg_dict.get("package_num")
        elif msg_body.get("info_id", -1) == 6:
            HHhdlist.device_charfer_p[msg_body.get("gun_id") + 1]["start_package_num"] = msg_dict.get("package_num")
    DtoP_queue.put(msg)


def keep_mqtt(broker, port):
    global thmc
    thmc = HMqttClient(broker, port)
    isFirst = True
    hmclient = None
    while True:
        if not thmc.connectStatus:
            if isFirst:
                isFirst = False
                try:
                    HSyslog.log_info('!!!!! MQTT重连 !!!!!')
                    hmclient = thmc.connect_mqtt()  # 客户端对象
                except Exception as e:
                    HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")
                    isFirst = True
                if thmc.connectStatus and thmc.client:
                    hmclient.loop_start()
            else:
                hmclient.loop_stop()
                try:
                    hmclient.reconnect()
                except Exception as e:
                    HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")
                HSyslog.log_info('will send netstatus')
                hmclient.loop_start()
                thmc.subscribe()
        else:
            if hmclient._state == 2 or hmclient._state == 0:
                hmclient.disconnect()
                thmc.connectStatus = False
                HSyslog.log_info("The connection is Closed! state is {}".format(hmclient._state))

        time.sleep(1)


def do_link_mqtt():
    mqttKeepThread = threading.Thread(target=keep_mqtt, args=["127.0.0.1", 1883])
    mqttKeepThread.start()
    HSyslog.log_info("do_link_mqtt")


def __mqtt_send_data():
    while True:
        if not DtoP_queue:
            time.sleep(0.5)
        else:
            try:
                if DtoP_queue.empty():
                    time.sleep(0.5)
                else:
                    msg = dict(DtoP_queue.get())
                    if "topic" not in msg.keys():
                        continue
                    thmc.publish(msg.get("topic"), msg.get("msg", ""), msg.get("qos", 0))
            except Exception as e:
                raise Exception("program exit")


def do_mqtt_send_data():
    mqttSendThread = threading.Thread(target=__mqtt_send_data)
    mqttSendThread.start()
    HSyslog.log_info("do_mqtt_send_data")


def __mqtt_period_event():
    period_time = time.time()
    while True:
        if int(time.time()) - int(period_time) > 5:
            if HStategrid.link_init_status == 1:
                app_net_status(HHhdlist.net_type.wired_net.value, 3, HHhdlist.net_id.id_4G.value)
            if HStategrid.link_init_status == 0:
                app_net_status(HHhdlist.net_type.no_net.value, 0, HHhdlist.net_id.id_4G.value)
            period_time = time.time()
        time.sleep(1)


def do_mqtt_period():
    mqttPeriodThread = threading.Thread(target=__mqtt_period_event)
    mqttPeriodThread.start()
    HSyslog.log_info("do_mqtt_period")


'''#################################### subscribe  analysis_msg ####################################'''
'''设备故障消息'''


def app_device_fault(msg_body_dict: dict):
    faultSum = msg_body_dict.get('faultSum', -1)  # int
    warnSum = msg_body_dict.get('warnSum', -1)  # int
    faultVal = msg_body_dict.get('faultVal', [])  # array
    warnVal = msg_body_dict.get('warnVal', [])  # array

    if HStategrid.get_flaut_status():
        fault_warn_code = {}  # {"device_num":[]}
        if warnSum < 0 or faultSum < 0:
            HSyslog.log_info("故障告警信息错误")
            return -1
        elif warnSum > 0 or faultSum > 0:
            for info in faultVal:
                for device_type, device_data in HStategrid.flaut_warning_type.items():  # device_type:device
                    for flaut_type, flaut_data in device_data.items():  # flaut_type:flaut
                        for flaut_id, flaut_list in flaut_data.items():  # flaut_id:1000
                            if info.get("fault_id") in flaut_list:
                                if (
                                        flaut_id in HStategrid.flaut_warning_type["gun"]["flaut"].keys() or
                                        flaut_id in HStategrid.flaut_warning_type["gun"]["warn"].keys() or
                                        flaut_id in HStategrid.flaut_warning_type["gun"]["regular"].keys()
                                ):
                                    if info.get("device_num") not in fault_warn_code:  # 枪
                                        fault_warn_code[info.get("device_num")] = {}
                                    if flaut_type not in fault_warn_code[info.get("device_num")]:
                                        fault_warn_code[info.get("device_num")][flaut_type] = []
                                    if flaut_id not in fault_warn_code[info.get("device_num")][flaut_type]:
                                        fault_warn_code[info.get("device_num")][flaut_type].append(flaut_id)

            for info in warnVal:
                for device_type, device_data in HStategrid.flaut_warning_type.items():  # device_type:device
                    for flaut_type, flaut_data in device_data.items():  # flaut_type:flaut
                        for flaut_id, flaut_list in flaut_data.items():  # flaut_id:1000
                            if info.get("fault_id") in flaut_list:
                                if (
                                        flaut_id in HStategrid.flaut_warning_type["gun"]["flaut"].keys() or
                                        flaut_id in HStategrid.flaut_warning_type["gun"]["warn"].keys() or
                                        flaut_id in HStategrid.flaut_warning_type["gun"]["regular"].keys()
                                ):
                                    if info.get("device_num") not in fault_warn_code:  # 枪
                                        fault_warn_code[info.get("device_num")] = {}
                                    if flaut_type not in fault_warn_code[info.get("device_num")]:
                                        fault_warn_code[info.get("device_num")][flaut_type] = []
                                    if flaut_id not in fault_warn_code[info.get("device_num")][flaut_type]:
                                        fault_warn_code[info.get("device_num")][flaut_type].append(flaut_id)
        else:
            if warnSum == 0 and faultSum == 0:
                HSyslog.log_info("故障告警数量为零")

        info = {}
        HHhdlist.device_flaut_warn = fault_warn_code
        if fault_warn_code != {}:
            for gun_id in fault_warn_code.keys():
                if fault_warn_code.get(gun_id).get("flaut", 0) == 0:
                    faultnum = 0
                else:
                    faultnum = len(fault_warn_code.get(gun_id).get("flaut"))
                if fault_warn_code.get(gun_id).get("warn", 0) == 0:
                    warnnum = 0
                else:
                    warnnum = len(fault_warn_code.get(gun_id).get("warn"))
                info = {
                    "gunNo": gun_id,
                    "faultSum": faultnum,
                    "warnSum": warnnum,
                    "faultValue": fault_warn_code.get(gun_id).get("flaut", []),
                    "warnValue": fault_warn_code.get(gun_id).get("warn", []),
                }
                HTools.Htool_send_totalFaultEvt(info)

            return 0
        else:
            for i in range(0, HStategrid.get_DeviceInfo("00110")):
                info = {
                    "gunNo": i + 1,
                    "faultSum": 0,
                    "warnSum": 0,
                    "faultValue": [],
                    "warnValue": [],
                }
                HTools.Htool_send_totalFaultEvt(info)
            return 0


'''设备故障查询消息'''
'''type = 0x00:全量获取'''


def app_device_fault_query(type: int):
    msg_body = {'type': type}
    topic = HHhdlist.topic_app_device_fault_query
    app_publish(topic, msg_body)
    return True


'''遥测遥信消息,'''


def app_telemetry_telesignaling(msg_body_dict: dict):
    chargeSys = {}
    cabinet = {}
    gun = {}
    pdu = {}
    module = {}
    bms = {}
    meter = {}
    parkLock = {}
    try:
        dev_type = msg_body_dict.get('dcCharger')  # 设备类型
        if dev_type != -1:
            for sub_dev_type, sub_dev_data in dev_type.items():  # 子设备遍历
                if sub_dev_type == "chargeSys":
                    for gun_id, gun_data in sub_dev_data.items():
                        gun_id = int(gun_id) + 1
                        chargeSys[gun_id] = {}
                        for key, value in gun_data.items():
                            if int(key) in HHhdlist.Device_Pistol.keys():
                                chargeSys[gun_id][int(key)] = value
                        if gun_id not in HHhdlist.chargeSys.keys():
                            HHhdlist.chargeSys[gun_id] = {}
                        HHhdlist.chargeSys[gun_id].update(chargeSys[gun_id])
                if sub_dev_type == "cabinet":
                    for gun_id, gun_data in sub_dev_data.items():
                        gun_id = int(gun_id) + 1
                        cabinet[gun_id] = {}
                        for key, value in gun_data.items():
                            if key != "extend":
                                if int(key) in HHhdlist.Power_Pistol.keys():
                                    cabinet[gun_id][int(key)] = value
                        if gun_id not in HHhdlist.cabinet.keys():
                            HHhdlist.cabinet[gun_id] = {}
                        HHhdlist.cabinet[gun_id].update(cabinet[gun_id])
                if sub_dev_type == "gun":
                    for gun_id, gun_data in sub_dev_data.items():
                        gun_id = int(gun_id) + 1
                        gun[gun_id] = {}
                        for key, value in gun_data.items():
                            if int(key) in HHhdlist.Gun_Pistol.keys():
                                gun[gun_id][int(key)] = value
                        if gun_id not in HHhdlist.gun.keys():
                            HHhdlist.gun[gun_id] = {}
                        HHhdlist.gun[gun_id].update(gun[gun_id])
                if sub_dev_type == "pdu":
                    for gun_id, gun_data in sub_dev_data.items():
                        gun_id = int(gun_id) + 1
                        pdu[gun_id] = {}
                        for key, value in gun_data.items():
                            if int(key) in HHhdlist.Power_Crrl_Plug.keys():
                                pdu[gun_id][int(key)] = value
                        if gun_id not in HHhdlist.pdu.keys():
                            HHhdlist.pdu[gun_id] = {}
                        HHhdlist.pdu[gun_id].update(pdu[gun_id])
                if sub_dev_type == "module":
                    for gun_id, gun_data in sub_dev_data.items():
                        gun_id = int(gun_id) + 1
                        module[gun_id] = {}
                        for key, value in gun_data.items():
                            if int(key) in HHhdlist.Power_Unit_Pistol.keys():
                                module[gun_id][int(key)] = value
                        if gun_id not in HHhdlist.module.keys():
                            HHhdlist.module[gun_id] = {}
                        HHhdlist.module[gun_id].update(module[gun_id])
                if sub_dev_type == "bms":
                    for gun_id, gun_data in sub_dev_data.items():
                        gun_id = int(gun_id) + 1
                        bms[gun_id] = {}
                        for key, value in gun_data.items():
                            if int(key) in HHhdlist.BMS_disposable_Pistol.keys():
                                bms[gun_id][int(key)] = value
                        if gun_id not in HHhdlist.bms.keys():
                            HHhdlist.bms[gun_id] = {}
                        HHhdlist.bms[gun_id].update(bms[gun_id])
                if sub_dev_type == "meter":
                    for gun_id, gun_data in sub_dev_data.items():
                        gun_id = int(gun_id) + 1
                        meter[gun_id] = {}
                        for key, value in gun_data.items():
                            if int(key) in HHhdlist.Meter_Pistol.keys():
                                meter[gun_id][int(key)] = value
                        if gun_id not in HHhdlist.meter.keys():
                            HHhdlist.meter[gun_id] = {}
                        HHhdlist.meter[gun_id].update(meter[gun_id])
                if sub_dev_type == "parkLock":
                    for gun_id, gun_data in sub_dev_data.items():
                        gun_id = int(gun_id) + 1
                        parkLock[gun_id] = {}
                        for key, value in gun_data.items():
                            if int(key) in HHhdlist.Ground_Plug.keys():
                                parkLock[gun_id][int(key)] = value
                        if gun_id not in HHhdlist.parkLock.keys():
                            HHhdlist.parkLock[gun_id] = {}
                        HHhdlist.parkLock[gun_id].update(parkLock[gun_id])

    except Exception as e:
        HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")

    # HSyslog.log_info(f"chargeSys: {HHhdlist.chargeSys}")
    # HSyslog.log_info(f"cabinet: {HHhdlist.cabinet}")
    # HSyslog.log_info(f"gun: {HHhdlist.gun}")
    # HSyslog.log_info(f"pdu: {HHhdlist.pdu}")
    # HSyslog.log_info(f"module: {HHhdlist.module}")
    # HSyslog.log_info(f"bms: {HHhdlist.bms}")
    # HSyslog.log_info(f"meter: {HHhdlist.meter}")
    # HSyslog.log_info(f"parkLock: {HHhdlist.parkLock}")
    # HSyslog.log_info(f"HHhdlist.device_charfer_p: {HHhdlist.device_charfer_p}")

    for i in HHhdlist.gun.keys():
        gun_stus = HHhdlist.gun.get(i).get(6)
        if i not in HHhdlist.gun_status:
            HHhdlist.gun_status[i] = gun_stus
            if gun_stus == 1:
                data = {
                    "gunNo": i,
                    "yxOccurTime": int(time.time()),
                    "connCheckStatus": 10
                }
            else:
                data = {
                    "gunNo": i,
                    "yxOccurTime": int(time.time()),
                    "connCheckStatus": 11
                }
            HHhdlist.gun_status[i] = gun_stus
            HTools.Htool_send_dcStChEvt(data)
        else:
            if HHhdlist.gun_status[i] != gun_stus:
                if gun_stus == 1:
                    data = {
                        "gunNo": i,
                        "yxOccurTime": int(time.time()),
                        "connCheckStatus": 10
                    }
                else:
                    data = {
                        "gunNo": i,
                        "yxOccurTime": int(time.time()),
                        "connCheckStatus": 11
                    }
                HHhdlist.gun_status[i] = gun_stus
                HTools.Htool_send_dcStChEvt(data)

    if HStategrid.get_property_status() == 0:
        HStategrid.set_property_status(1)


'''遥测遥信查询消息'''


def app_telemetry_remote_query():
    msg = {

    }
    topic = HHhdlist.topic_app_telemetry_remote_query
    app_publish(topic, msg)
    return True


'''充电请求消息'''


def app_charge_request(msg_body_dict: dict):
    gun_id = msg_body_dict.get('gun_id', -1)  # int
    session_id = msg_body_dict.get('session_id', '')  # string
    start_source = msg_body_dict.get('start_source', -1)  # int
    charge_type = msg_body_dict.get('charge_type', -1)  # int
    stop_type = msg_body_dict.get('stop_type', -1)  # int
    stop_condition = msg_body_dict.get('stop_condition', -1)  # int
    gunNo = gun_id + 1
    try:
        tradeNo = str(HStategrid.get_DeviceInfo("deviceName") + str("{:02}".format(gunNo)) +
                      HHhdlist.unix_time(int(time.time())) + HStategrid.charging_num() +
                      HStategrid.do_charging_num())
        HHhdlist.device_charfer_p[gunNo].update({"start_source": start_source})
        HHhdlist.device_charfer_p[gunNo].update({"charge_type": charge_type})
        HHhdlist.device_charfer_p[gunNo].update({"stop_type": stop_type})
        HHhdlist.device_charfer_p[gunNo].update({"startType": 11})
        HHhdlist.device_charfer_p[gunNo].update({"stop_condition": stop_condition})
        HHhdlist.device_charfer_p[gunNo].update({"device_session_id": str(session_id)})

        if "vin" in HHhdlist.device_charfer_p.get(gunNo):
            auth_data = {
                "gunNo": gunNo,
                "preTradeNo": "",
                "tradeNo": tradeNo,
                "startType": 11,
                "authCode": HHhdlist.device_charfer_p.get("vin"),
                "batterySOC": 0,
                "batteryCap": 0,
                "chargeTimes": 0,
                "batteryVol": 0
            }
            HTools.Htool_send_startChargeAuthEvt(auth_data)

        msg_body = {
            'gun_id': gun_id,
            'cloud_session_id': "",
            'device_session_id': session_id,
            'request_result': 1,
            'failure_reason': 0,
            'temp_strategy': {
                'delay_time': 0,
                'stop_type': 0,
                'stop_condition': 0
            },
            'temp_rate': {
                'rate_id': "",
                'count': 0,
                'items': []
            }
        }
        app_charge_request_response(msg_body)
        HHhdlist.device_charfer_p[gunNo].update({"tradeNo": tradeNo})
        HHhdlist.device_charfer_p[gunNo].update({"delay_time": 0})
        HHhdlist.device_charfer_p[gunNo].update({"stop_type": 0})
        HHhdlist.device_charfer_p[gunNo].update({"stop_condition": 0})
        HHhdlist.device_charfer_p[gunNo].update({"cloud_session_id": tradeNo})
        HHhdlist.device_charfer_p[gunNo].update({"delay_time": 0})
    except Exception as e:
        HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")


'''充电记录应答消息'''


def app_charge_record_response(msg_body_dict: dict):
    topic = HHhdlist.topic_app_charge_record_response
    app_publish(topic, msg_body_dict)
    return True


'''充电控制应答消息'''


def app_charging_control_response(msg_body_dict: dict):
    gun_id = msg_body_dict.get('gun_id', -1)  # int
    package_num = msg_body_dict.get('package_num', -1)  # int
    result = msg_body_dict.get('result', -1)  # int
    reason = msg_body_dict.get('reason', -1)  # int
    time = msg_body_dict.get('time', -1)  # int
    gunNo = gun_id + 1

    if package_num == HHhdlist.device_charfer_p.get(gunNo).get("start_package_num"):
        startResult = 10
        if gunNo not in HHhdlist.device_flaut_warn:
            faultCode = 0
        else:
            faultCode = HHhdlist.device_flaut_warn.get(gunNo).get("flaut")
        if result == 0:
            startResult = 10
            faultCode = 0
        if result == 1:
            if reason == 1:
                startResult = 11
            if reason == 2:
                startResult = 14
        data = {
            "gunNo": gunNo,
            "preTradeNo": HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo"),
            "tradeNo": HHhdlist.device_charfer_p.get(gunNo).get("tradeNo"),
            "startResult": startResult,
            "faultCode": faultCode,
            "vinCode": HHhdlist.device_charfer_p.get(gunNo).get("vin")
        }
        HTools.Htool_send_startChaResEvt(data)
    if package_num == HHhdlist.device_charfer_p.get(gunNo).get("stop_package_num"):
        pass
        workStatus = HStategrid.workstatus(HHhdlist.gun.get(gunNo).get(1), HHhdlist.gun.get(gunNo).get(6))
        dc_nonWork = {
            "gunNo": gunNo,
            "workStatus": workStatus,
            "gunStatus": HHhdlist.gun.get(gunNo).get(6, 0) + 10,
            "eLockStatus": HHhdlist.gun.get(gunNo).get(2, 0) + 10,
            "DCK1Status": HHhdlist.gun.get(gunNo).get(4, 0) + 10,
            "DCK2Status": HHhdlist.gun.get(gunNo).get(4, 0) + 10,
            "DCPlusFuseStatus": 12,
            "DCMinusFuseStatus": 12,
            "conTemp1": HHhdlist.gun.get(gunNo).get(122, 0) * 10,
            "conTemp2": HHhdlist.gun.get(gunNo).get(123, 0) * 10,
            "dcVol": HHhdlist.gun.get(gunNo).get(112, 0),
            "dcCur": HHhdlist.gun.get(gunNo).get(123, 0),
        }
        HTools.Htool_plamform_property(17, dc_nonWork)


'''VIN鉴权消息'''


def app_vin_authentication(msg_body_dict: dict):
    gun_id = msg_body_dict.get('gun_id', -1)  # int
    type = msg_body_dict.get('type', -1)  # int
    content = msg_body_dict.get('content', '')  # string
    start_source = msg_body_dict.get('start_source', -1)  # int
    extras = msg_body_dict.get('extras', '')  # string
    gunNo = gun_id + 1

    try:
        if type == 2:
            HHhdlist.device_charfer_p[gunNo].update({"vin": content})
            HHhdlist.device_charfer_p[gunNo].update({"card_id": ""})
        if type == 1:
            HHhdlist.device_charfer_p[gunNo].update({"vin": content})
            HHhdlist.device_charfer_p[gunNo].update({"card_id": extras})

        HHhdlist.device_charfer_p[gunNo].update({"start_source": start_source})
        HSyslog.log_info(HHhdlist.device_charfer_p)
        if HHhdlist.device_charfer_p.get(gunNo).get("startType") != 11:
            stop_code = HHhdlist.device_charfer_p.get(gunNo).get("stopCode")
            balance = HHhdlist.device_charfer_p.get(gunNo).get("balance")
            billing = HHhdlist.device_charfer_p.get(gunNo).get("billing")
            overdraft_limit = HHhdlist.device_charfer_p.get(gunNo).get("overdraft_limit")
            electric_discount = HHhdlist.device_charfer_p.get(gunNo).get("electric_discount")
            service_discount = HHhdlist.device_charfer_p.get(gunNo).get("service_discount")
            multi_charge = HHhdlist.device_charfer_p.get(gunNo).get("multi_charge")
            account_info = {
                "stop_code": str(stop_code),
                "balance": int(balance),
                "billing": int(billing),
                "overdraft_limit": int(overdraft_limit),
                "electric_discount": int(electric_discount),
                "service_discount": int(service_discount),
                "multi_charge": int(multi_charge),
            }
            data = {
                "gun_id": gun_id,
                "result": 1,
                "failure_reason": 0,
                "account_info": account_info
            }
            app_authentication_response(data)
        else:
            if "vin" in HHhdlist.device_charfer_p.get(gunNo):
                auth_data = {
                    "gunNo": gunNo,
                    "preTradeNo": "",
                    "tradeNo": HHhdlist.device_charfer_p.get(gunNo).get("tradeNo"),
                    "startType": 11,
                    "authCode": HHhdlist.device_charfer_p.get(gunNo).get("vin"),
                    "batterySOC": 0,
                    "batteryCap": 0,
                    "chargeTimes": 0,
                    "batteryVol": 0
                }
                HTools.Htool_send_startChargeAuthEvt(auth_data)
                HHhdlist.authstart.wait(timeout=3)
                if not HHhdlist.authstart.is_set():
                    account_info = {
                        "stop_code": HHhdlist.device_charfer_p.get(gunNo).get("stopCode"),
                        "balance": 0,
                        "billing": 0,
                        "overdraft_limit": 0,
                        "electric_discount": 0,
                        "service_discount": 0,
                        "multi_charge": 0,
                    }
                    data = {
                        "gun_id": gun_id,
                        "result": 0,
                        "failure_reason": 0,
                        "account_info": account_info
                    }
                    app_authentication_response(data)
    except Exception as e:
        HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")


'''充电记录消息'''


def app_charging_record(msg_body_dict: dict):
    gunNo = msg_body_dict.get('gun_id') + 1
    device_session_id = HHhdlist.device_charfer_p.get(gunNo).get("device_session_id", "")
    if HHhdlist.device_charfer_p[gunNo] != {}:
        if device_session_id == "":
            device_order = {
                "gun_id": gunNo,  # int
                "cloud_session_id": msg_body_dict.get('cloud_session_id', ''),  # string
                "device_session_id": msg_body_dict.get('device_session_id', ''),  # string
                "start_time": msg_body_dict.get('start_time', -1),  # int
                "stop_time": msg_body_dict.get('stop_time', -1),  # int
                "charge_time": msg_body_dict.get('charge_time', -1),  # int
                "start_meter_value": msg_body_dict.get('start_meter_value', -1),  # int
                "stop_meter_value": msg_body_dict.get('stop_meter_value', -1),  # int
                "start_soc": msg_body_dict.get('start_soc', -1),  # int
                "stop_soc": msg_body_dict.get('stop_soc', -1),  # int
                "bat_max_vol": msg_body_dict.get('bat_max_vol', -1),  # int
                "bat_max_vol_num": msg_body_dict.get('bat_max_vol_num', -1),  # int
                "bat_min_vol": msg_body_dict.get('bat_min_vol', -1),  # int
                "bat_min_vol_num": msg_body_dict.get('bat_min_vol_num', -1),  # int
                "bat_max_tempereture": msg_body_dict.get('bat_max_tempereture', -1),  # int
                "bat_max_tempereture_num": msg_body_dict.get('bat_max_tempereture_num', -1),  # int
                "bat_min_tempereture": msg_body_dict.get('bat_min_tempereture', -1),  # int
                "bat_min_tempereture_num": msg_body_dict.get('bat_min_tempereture_num', -1),  # int
                "start_source": msg_body_dict.get('start_source', -1),  # int
                "stop_type": msg_body_dict.get('stop_type', -1),  # int
                "stop_condition": msg_body_dict.get('stop_condition', -1),  # int
                "stop_reason": msg_body_dict.get('stop_reason', -1),  # int
                "normal_end": msg_body_dict.get('normal_end', -1),  # int
                "electric_rate_id": msg_body_dict.get('electric_rate_id', ''),  # string
                "cusp_energy": msg_body_dict.get('cusp_energy', -1),  # int 尖电量
                "cusp_electric_cost": msg_body_dict.get('cusp_electric_cost', -1),  # int      尖电费
                "cusp_service_cost": msg_body_dict.get('cusp_service_cost', -1),  # int   尖服务费
                "peak_energy": msg_body_dict.get('peak_energy', -1),  # int   峰电量
                "peak_electric_cost": msg_body_dict.get('peak_electric_cost', -1),  # int
                "peak_service_cost": msg_body_dict.get('peak_service_cost', -1),  # int
                "normal_energy": msg_body_dict.get('normal_energy', -1),  # int
                "normal_electric_cost": msg_body_dict.get('normal_electric_cost', -1),  # int
                "normal_service_cost": msg_body_dict.get('normal_service_cost', -1),  # int
                "valley_energy": msg_body_dict.get('valley_energy', -1),  # int
                "valley_electric_cost": msg_body_dict.get('valley_electric_cost', -1),  # int
                "valley_service_cost": msg_body_dict.get('valley_service_cost', -1),  # int
                "deep_valley_energy": msg_body_dict.get('deep_valley_energy', -1),
                "deep_valley_electric_cost": msg_body_dict.get('deep_valley_electric_cost', -1),
                "deep_valley_service_cost": msg_body_dict.get('deep_valley_service_cost', -1),
                "total_energy": msg_body_dict.get('total_energy', -1),  # int
                "total_electric_cost": msg_body_dict.get('total_electric_cost', -1),  # int
                "total_service_cost": msg_body_dict.get('total_service_cost', -1),  # int
                "total_cost": msg_body_dict.get('total_cost', -1),  # int
                "card_id": msg_body_dict.get('card_id', ''),  # string
                "user_id": msg_body_dict.get('user_id', ''),  # string
                "vin": msg_body_dict.get('vin', ''),  # string
                "record_type": msg_body_dict.get('record_type', -1),  # int
                "main_session_id": msg_body_dict.get('main_session_id', ''),  # string
                "connect_time": msg_body_dict.get('connect_time', -1),  # int
                "multi_mode": msg_body_dict.get('multi_mode', -1),  # int
                "interval_count": msg_body_dict.get('interval_count', -1),  # int
                "interval": msg_body_dict.get('interval', []),  # array
            }
            HHhdlist.device_charfer_p[gunNo].update({"order": device_order})

            reason = HStategrid.stop_reason(msg_body_dict.get('stop_reason', -1))

            if HHhdlist.device_charfer_p.get(gunNo) != {}:
                data = {
                    "gunNo": gunNo,
                    "preTradeNo": HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo", ""),
                    "tradeNo": HHhdlist.device_charfer_p.get(gunNo).get("tradeNo", ""),
                    "startResult": 11,
                    "faultCode": reason,
                    "vinCode": ""
                }
                HTools.Htool_send_startChaResEvt(data)

            timeDivType = 10
            eleModelId = ""
            serModelId = ""
            if msg_body_dict.get('electric_rate_id', '') == HStategrid.get_DeviceInfo("feeid"):
                eleModelId = HStategrid.get_DeviceInfo("eleModelId")
                serModelId = HStategrid.get_DeviceInfo("serModelId")
            info = {
                "gunNo": gunNo,
                "preTradeNo": HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo", ""),
                "tradeNo": HHhdlist.device_charfer_p.get(gunNo).get("tradeNo", ""),
                "vinCode": HHhdlist.device_charfer_p.get(gunNo).get("vin", ""),
                "timeDivType": timeDivType,
                "chargeStartTime": HHhdlist.device_charfer_p.get(gunNo).get("order").get("start_time"),
                "chargeEndTime": HHhdlist.device_charfer_p.get(gunNo).get("order").get("stop_time"),
                "startSoc": HHhdlist.device_charfer_p.get(gunNo).get("order").get("start_soc"),
                "endSoc": HHhdlist.device_charfer_p.get(gunNo).get("order").get("stop_soc"),
                "reason": reason,
                "eleModelId": eleModelId,
                "serModelId": serModelId,
                "sumStart": HHhdlist.device_charfer_p.get(gunNo).get("order").get("start_meter_value"),
                "sumEnd": HHhdlist.device_charfer_p.get(gunNo).get("order").get("stop_meter_value"),
                "totalElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("total_energy"),
                "sharpElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("cusp_energy"),
                "peakElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("peak_energy"),
                "flatElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("normal_energy"),
                "valleyElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("valley_energy"),
                "totalPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("total_electric_cost") * 10,
                "totalServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("total_service_cost") * 10,
                "sharpPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("cusp_electric_cost") * 10,
                "peakPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("peak_electric_cost") * 10,
                "flatPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("normal_electric_cost") * 10,
                "valleyPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("valley_electric_cost") * 10,
                "sharpServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("cusp_service_cost") * 10,
                "peakServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("peak_service_cost") * 10,
                "flatServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("normal_service_cost") * 10,
                "valleyServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("valley_service_cost") * 10,
                "device_session_id": HHhdlist.device_charfer_p.get(gunNo).get("order").get("device_session_id")
            }
            HTools.Htool_orderUpdateEvt(info)
            HStategrid.save_DeviceOrder(info)
        else:
            if msg_body_dict.get('device_session_id') == device_session_id:
                try:
                    device_order = {
                        "gun_id": gunNo,  # int
                        "cloud_session_id": msg_body_dict.get('cloud_session_id', ''),  # string
                        "device_session_id": msg_body_dict.get('device_session_id', ''),  # string
                        "start_time": msg_body_dict.get('start_time', -1),  # int
                        "stop_time": msg_body_dict.get('stop_time', -1),  # int
                        "charge_time": msg_body_dict.get('charge_time', -1),  # int
                        "start_meter_value": msg_body_dict.get('start_meter_value', -1),  # int
                        "stop_meter_value": msg_body_dict.get('stop_meter_value', -1),  # int
                        "start_soc": msg_body_dict.get('start_soc', -1),  # int
                        "stop_soc": msg_body_dict.get('stop_soc', -1),  # int
                        "bat_max_vol": msg_body_dict.get('bat_max_vol', -1),  # int
                        "bat_max_vol_num": msg_body_dict.get('bat_max_vol_num', -1),  # int
                        "bat_min_vol": msg_body_dict.get('bat_min_vol', -1),  # int
                        "bat_min_vol_num": msg_body_dict.get('bat_min_vol_num', -1),  # int
                        "bat_max_tempereture": msg_body_dict.get('bat_max_tempereture', -1),  # int
                        "bat_max_tempereture_num": msg_body_dict.get('bat_max_tempereture_num', -1),  # int
                        "bat_min_tempereture": msg_body_dict.get('bat_min_tempereture', -1),  # int
                        "bat_min_tempereture_num": msg_body_dict.get('bat_min_tempereture_num', -1),  # int
                        "start_source": msg_body_dict.get('start_source', -1),  # int
                        "stop_type": msg_body_dict.get('stop_type', -1),  # int
                        "stop_condition": msg_body_dict.get('stop_condition', -1),  # int
                        "stop_reason": msg_body_dict.get('stop_reason', -1),  # int
                        "normal_end": msg_body_dict.get('normal_end', -1),  # int
                        "electric_rate_id": msg_body_dict.get('electric_rate_id', ''),  # string
                        "cusp_energy": msg_body_dict.get('cusp_energy', -1),  # int 尖电量
                        "cusp_electric_cost": msg_body_dict.get('cusp_electric_cost', -1),  # int      尖电费
                        "cusp_service_cost": msg_body_dict.get('cusp_service_cost', -1),  # int   尖服务费
                        "peak_energy": msg_body_dict.get('peak_energy', -1),  # int   峰电量
                        "peak_electric_cost": msg_body_dict.get('peak_electric_cost', -1),  # int
                        "peak_service_cost": msg_body_dict.get('peak_service_cost', -1),  # int
                        "normal_energy": msg_body_dict.get('normal_energy', -1),  # int
                        "normal_electric_cost": msg_body_dict.get('normal_electric_cost', -1),  # int
                        "normal_service_cost": msg_body_dict.get('normal_service_cost', -1),  # int
                        "valley_energy": msg_body_dict.get('valley_energy', -1),  # int
                        "valley_electric_cost": msg_body_dict.get('valley_electric_cost', -1),  # int
                        "valley_service_cost": msg_body_dict.get('valley_service_cost', -1),  # int
                        "deep_valley_energy": msg_body_dict.get('deep_valley_energy', -1),
                        "deep_valley_electric_cost": msg_body_dict.get('deep_valley_electric_cost', -1),
                        "deep_valley_service_cost": msg_body_dict.get('deep_valley_service_cost', -1),
                        "total_energy": msg_body_dict.get('total_energy', -1),  # int
                        "total_electric_cost": msg_body_dict.get('total_electric_cost', -1),  # int
                        "total_service_cost": msg_body_dict.get('total_service_cost', -1),  # int
                        "total_cost": msg_body_dict.get('total_cost', -1),  # int
                        "card_id": msg_body_dict.get('card_id', ''),  # string
                        "user_id": msg_body_dict.get('user_id', ''),  # string
                        "vin": msg_body_dict.get('vin', ''),  # string
                        "record_type": msg_body_dict.get('record_type', -1),  # int
                        "main_session_id": msg_body_dict.get('main_session_id', ''),  # string
                        "connect_time": msg_body_dict.get('connect_time', -1),  # int
                        "multi_mode": msg_body_dict.get('multi_mode', -1),  # int
                        "interval_count": msg_body_dict.get('interval_count', -1),  # int
                        "interval": msg_body_dict.get('interval', []),  # array
                    }
                    HHhdlist.device_charfer_p[gunNo].update({"order": device_order})

                    timeDivType = 10
                    eleModelId = ""
                    serModelId = ""
                    if msg_body_dict.get('electric_rate_id', '') == HStategrid.get_DeviceInfo("feeid"):
                        eleModelId = HStategrid.get_DeviceInfo("eleModelId")
                        serModelId = HStategrid.get_DeviceInfo("serModelId")

                    reason = HStategrid.stop_reason(msg_body_dict.get('stop_reason', -1))
                    data = {
                        "gunNo": gunNo,
                        "preTradeNo": HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo", ""),
                        "tradeNo": HHhdlist.device_charfer_p.get(gunNo).get("tradeNo", ""),
                        "stopResult": 10,
                        "resultCode": reason,
                        "stopFailReson": 10
                    }
                    HTools.Htool_send_stopChaResEvt(data)

                    info = {
                        "gunNo": gunNo,
                        "preTradeNo": HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo", ""),
                        "tradeNo": HHhdlist.device_charfer_p.get(gunNo).get("tradeNo", ""),
                        "vinCode": HHhdlist.device_charfer_p.get(gunNo).get("order").get("vin", ""),
                        "timeDivType": timeDivType,
                        "chargeStartTime": HHhdlist.device_charfer_p.get(gunNo).get("order").get("start_time", ""),
                        "chargeEndTime": HHhdlist.device_charfer_p.get(gunNo).get("order").get("stop_time", ""),
                        "startSoc": HHhdlist.device_charfer_p.get(gunNo).get("order").get("start_soc", ""),
                        "endSoc": HHhdlist.device_charfer_p.get(gunNo).get("order").get("stop_soc", ""),
                        "reason": reason,
                        "eleModelId": eleModelId,
                        "serModelId": serModelId,
                        "sumStart": HHhdlist.device_charfer_p.get(gunNo).get("order").get("start_meter_value"),
                        "sumEnd": HHhdlist.device_charfer_p.get(gunNo).get("order").get("stop_meter_value"),
                        "totalElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("total_energy"),
                        "sharpElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("cusp_energy"),
                        "peakElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("peak_energy"),
                        "flatElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("normal_energy"),
                        "valleyElect": HHhdlist.device_charfer_p.get(gunNo).get("order").get("valley_energy"),
                        "totalPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get(
                            "total_electric_cost") * 10,
                        "totalServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get(
                            "total_service_cost") * 10,
                        "sharpPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get(
                            "cusp_electric_cost") * 10,
                        "peakPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get(
                            "peak_electric_cost") * 10,
                        "flatPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get(
                            "normal_electric_cost") * 10,
                        "valleyPowerCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get(
                            "valley_electric_cost") * 10,
                        "sharpServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get(
                            "cusp_service_cost") * 10,
                        "peakServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get("peak_service_cost") * 10,
                        "flatServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get(
                            "normal_service_cost") * 10,
                        "valleyServCost": HHhdlist.device_charfer_p.get(gunNo).get("order").get(
                            "valley_service_cost") * 10,
                        "device_session_id": HHhdlist.device_charfer_p.get(gunNo).get("order").get("device_session_id")
                    }
                    HTools.Htool_orderUpdateEvt(info)
                    HStategrid.save_DeviceOrder(info)
                except Exception as e:
                    print(f"{e} .{inspect.currentframe().f_lineno}")
                    return False

    else:
        try:
            timeDivType = 10
            eleModelId = ""
            serModelId = ""
            device_session_id = msg_body_dict.get('device_session_id', "")
            preTradeNo_order = HStategrid.get_DeviceOrder(device_session_id)
            if preTradeNo_order is None:
                tradeNo = ""
                preTradeNo = ""
            else:
                tradeNo = preTradeNo_order[3]
                preTradeNo = preTradeNo_order[2]

            if msg_body_dict.get('electric_rate_id', '') == HStategrid.get_DeviceInfo("feeid"):
                eleModelId = HStategrid.get_DeviceInfo("eleModelId")
                serModelId = HStategrid.get_DeviceInfo("serModelId")

            reason = HStategrid.stop_reason(msg_body_dict.get('stop_reason', -1))

            info = {
                "gunNo": msg_body_dict.get('gun_id', -1) + 1,
                "preTradeNo": preTradeNo,
                "tradeNo": tradeNo,
                "vinCode": msg_body_dict.get('vin', ''),
                "timeDivType": timeDivType,
                "chargeStartTime": msg_body_dict.get('start_time', -1),
                "chargeEndTime": msg_body_dict.get('stop_time', -1),
                "startSoc": msg_body_dict.get('start_soc', -1),
                "endSoc": msg_body_dict.get('stop_soc', -1),
                "reason": reason,
                "eleModelId": eleModelId,
                "serModelId": serModelId,
                "sumStart": msg_body_dict.get('start_meter_value', -1),
                "sumEnd": msg_body_dict.get('stop_meter_value', -1),
                "totalElect": msg_body_dict.get('total_energy', -1),
                "sharpElect": msg_body_dict.get('cusp_energy', -1),
                "peakElect": msg_body_dict.get('peak_energy', -1),
                "flatElect": msg_body_dict.get("normal_energy"),
                "valleyElect": msg_body_dict.get("valley_energy"),
                "totalPowerCost": msg_body_dict.get("total_electric_cost") * 10,
                "totalServCost": msg_body_dict.get("total_service_cost") * 10,
                "sharpPowerCost": msg_body_dict.get("cusp_electric_cost") * 10,
                "peakPowerCost": msg_body_dict.get("peak_electric_cost") * 10,
                "flatPowerCost": msg_body_dict.get("normal_electric_cost") * 10,
                "valleyPowerCost": msg_body_dict.get("valley_electric_cost") * 10,
                "sharpServCost": msg_body_dict.get("cusp_service_cost") * 10,
                "peakServCost": msg_body_dict.get("peak_service_cost") * 10,
                "flatServCost": msg_body_dict.get("normal_service_cost") * 10,
                "valleyServCost": msg_body_dict.get("valley_service_cost") * 10,
                "device_session_id": device_session_id
            }
            HTools.Htool_orderUpdateEvt(info)
            HStategrid.save_DeviceOrder(info)
        except Exception as e:
            HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")
            return False


'''充电费用消息'''


def app_charge_fee(msg_body_dict: dict):
    gunNo = msg_body_dict.get("gun_id") + 1
    if HHhdlist.device_charfer_p.get(gunNo) != {}:
        if HHhdlist.device_charfer_p.get(gunNo).get("device_session_id") == msg_body_dict.get("device_session_id"):
            HHhdlist.device_charfer_p[gunNo].update({"charge_time": msg_body_dict.get('charge_time', -1)})
            HHhdlist.device_charfer_p[gunNo].update({"sharp_kwh": msg_body_dict.get('cusp_energy', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"sharp_electric_charge": msg_body_dict.get('cusp_electric_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"sharp_service_charge": msg_body_dict.get('sharp_service_charge', -1)})
            HHhdlist.device_charfer_p[gunNo].update({"peak_kwh": msg_body_dict.get('peak_energy', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"peak_electric_charge": msg_body_dict.get('peak_electric_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update({"peak_service_charge": msg_body_dict.get('peak_service_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update({"flat_kwh": msg_body_dict.get('normal_energy', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"flat_electric_charge": msg_body_dict.get('normal_electric_energy', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"flat_service_charge": msg_body_dict.get('normal_service_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update({"valley_kwh": msg_body_dict.get('valley_energy', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"valley_electric_charge": msg_body_dict.get('valley_electric_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"valley_service_charge": msg_body_dict.get('valley_service_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update({"deep_valley_energy": msg_body_dict.get('deep_valley_energy', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"deep_valley_electric_cost": msg_body_dict.get('deep_valley_electric_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"deep_valley_service_cost": msg_body_dict.get('deep_valley_service_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update({"total_kwh": msg_body_dict.get('total_energy', -1)})
            HHhdlist.device_charfer_p[gunNo].update(
                {"total_electric_cost": msg_body_dict.get('total_electric_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update({"total_service_cost": msg_body_dict.get('total_service_cost', -1)})
            HHhdlist.device_charfer_p[gunNo].update({"total_cost": msg_body_dict.get('total_cost', -1)})


'''充电电量冻结消息'''


def app_charge_battery_frozen(msg_body_dictdict: dict):
    gun_id = msg_body_dictdict.get('gun_id', -1)  # int
    cloud_session_id = msg_body_dictdict.get('cloud_session_id', '')  # string
    device_session_id = msg_body_dictdict.get('device_session_id', '')  # string
    count = msg_body_dictdict.get('count', -1)  # int
    items = msg_body_dictdict.get('items', [])  # array
    connect_id = gun_id + 1
    data = {}


'''账户充值应答消息'''


def app_account_recharge_response(msg_body_dict: dict):
    result = msg_body_dict.get('result', -1)  # int
    reason = msg_body_dict.get('reason', -1)  # int


'''充电费率请求消息'''


def app_rate_request(msg_body_dict: dict):
    count = msg_body_dict.get('count', -1)  # int
    items = msg_body_dict.get('items', [])  # array
    try:
        info = {}
        if count == -1:
            HSyslog.log_info(f"费率请求错误")
        if 0 < count < 8:
            info = {
                "gunNo": 1,
                "eleModelId": HStategrid.get_DeviceInfo("eleModelId"),
                "serModelId": HStategrid.get_DeviceInfo("serModelId")
            }
        if count == 0:
            info = {
                "gunNo": 1,
                "eleModelId": "",
                "serModelId": ""
            }
        HTools.Htool_send_askFeeModelEvt(info)
    except Exception as e:
        HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")


'''充电启动策略请求消息'''


# 0x5A
def app_charge_start_strategy_request(msg_body_dict: dict):
    count = msg_body_dict.get('count', -1)  # int


'''功率分配策略请求消息'''


#  0x5B
def app_power_allocation_policy_request(msg_body_dict: dict):
    count = msg_body_dict.get('count', -1)  # int


'''离线名单版本请求消息'''


# 0x5C
def app_offline_list_version_request(msg_body_dict: dict):
    count = msg_body_dict.get('count', -1)  # int


'''充电会话消息'''


#  0x5D
def app_charge_session(msg_body_dict: dict):
    gun_id = msg_body_dict.get('gun_id', -1)  # int
    cloud_session_id = msg_body_dict.get('cloud_session_id', '')  # string
    device_session_id = msg_body_dict.get('device_session_id', '')  # string
    user_id = msg_body_dict.get('user_id', '')  # string
    card_id = msg_body_dict.get('card_id', '')  # string
    connect_time = msg_body_dict.get('connect_time', -1)  # int
    start_charge_time = msg_body_dict.get('start_charge_time', -1)  # int
    start_meter_value = msg_body_dict.get('start_meter_value', -1)  # int
    start_soc = msg_body_dict.get('start_soc', -1)  # int
    start_source = msg_body_dict.get('start_source', -1)  # int
    stop_type = msg_body_dict.get('stop_type', -1)  # int
    stop_condition = msg_body_dict.get('stop_condition', -1)  # int
    offline_mode = msg_body_dict.get('offline_mode', -1)  # int
    charge_mode = msg_body_dict.get('charge_mode', -1)  # int
    gunNo = gun_id + 1

    try:
        HHhdlist.device_charfer_p[gunNo].update({"cloud_session_id": cloud_session_id})
        HHhdlist.device_charfer_p[gunNo].update({"device_session_id": str(device_session_id)})
        HHhdlist.device_charfer_p[gunNo].update({"connect_time": connect_time})
        HHhdlist.device_charfer_p[gunNo].update({"start_charge_time": start_charge_time})
        HHhdlist.device_charfer_p[gunNo].update({"start_meter_value": start_meter_value})
        HHhdlist.device_charfer_p[gunNo].update({"start_soc": start_soc})
        HHhdlist.device_charfer_p[gunNo].update({"start_source": start_source})
        HHhdlist.device_charfer_p[gunNo].update({"stop_type": stop_type})
        HHhdlist.device_charfer_p[gunNo].update({"stop_condition": stop_condition})
        HHhdlist.device_charfer_p[gunNo].update({"offline_mode": offline_mode})
        HHhdlist.device_charfer_p[gunNo].update({"charge_mode": charge_mode})

        app_charge_session_response(0)
    except Exception as e:
        HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")


'''读取版本号消息'''


#  0x5E
def app_read_version_number(msg_body_dict: dict):
    topic = HHhdlist.topic_app_read_version_number
    app_publish(topic, msg_body_dict)


# 参数设置消息
#  0x5F
def app_set_param_notify(msg_body_dict: dict):
    devtype = msg_body_dict.get('device_type', -1)
    device_num = msg_body_dict.get('device_num', -1)  # int
    count = msg_body_dict.get('count', -1)  # int
    items = msg_body_dict.get('items', -1)


'''设置参数应答消息'''


#  0x60
def app_set_parameter_response(msg_body_dict: dict):
    return msg_body_dict


'''二维码更新应答消息'''


#  0x61
def app_QR_code_update_response(msg_body_dict: dict):
    gun_id = msg_body_dict.get('gun_id', -1)  # int
    source = msg_body_dict.get('source', -1)  # int
    result = msg_body_dict.get('result', -1)  # int
    reason = msg_body_dict.get('reason', -1)  # int

    data = {
        "gun_id": gun_id,
        "result": result
    }
    HHhdlist.qr_queue.put(data)


'''充电费率同步应答消息'''


#  0x62
def app_charge_rate_sync_response(msg_body_dict: dict):
    id = msg_body_dict.get('id', '')  # string
    result = msg_body_dict.get('result', -1)  # int
    reason = msg_body_dict.get('reason', -1)  # int

    data = {}
    if result == 0:
        data["eleModelId"] = HStategrid.get_DeviceInfo("eleModelId")
        data["serModelId"] = HStategrid.get_DeviceInfo("serModelId")
        data["result"] = 10
    elif result == 1 and reason == 1:
        data["eleModelId"] = HStategrid.get_DeviceInfo("eleModelId")
        data["serModelId"] = HStategrid.get_DeviceInfo("serModelId")
        data["result"] = 11
    else:
        data["eleModelId"] = HStategrid.get_DeviceInfo("eleModelId")
        data["serModelId"] = HStategrid.get_DeviceInfo("serModelId")
        data["result"] = 12

    HHhdlist.fee_queue.put(data)


'''充电启动策略同步应答消息'''


#  0x63
def app_charge_start_strategy_sync_response(msg_body_dict: dict):
    id = msg_body_dict.get('id', '')  # string
    last_updated = msg_body_dict.get('last_updated', -1)  # int
    result = msg_body_dict.get('result', -1)  # int
    reason = msg_body_dict.get('reason', -1)  # int


'''功率分配策略同步应答消息'''


#  0x64
def app_power_allocation_strategy_sync_response(msg_body_dict: dict):
    id = msg_body_dict.get('id', '')  # string
    last_updated = msg_body_dict.get('last_updated', -1)  # int
    result = msg_body_dict.get('result', -1)  # int
    reason = msg_body_dict.get('reason', -1)  # int


'''离线名单版本同步应答消息'''


#  0x65
def app_offline_list_version_sync_response(msg_body_dict: dict):
    result = msg_body_dict.get('result', -1)  # int
    reason = msg_body_dict.get('reason', -1)  # int


'''离线名单项操作日志应答消息'''


#  0x66
def app_offline_list_operation_log_response(msg_body_dict: dict):
    id = msg_body_dict.get('id', '')  # string
    type = msg_body_dict.get('type', -1)  # int
    version = msg_body_dict.get('version', -1)  # int
    result = msg_body_dict.get('result', -1)  # int
    reason = msg_body_dict.get('reason', -1)  # int


'''清除故障、事件应答消息'''


#  0x67
def app_clear_faults_event_response(msg_body_dict: dict):
    type = msg_body_dict.get('type', -1)  # int
    result = msg_body_dict.get('result', -1)  # int


'''升级控制应答消息'''


#  0x68
def app_upgrade_control_response(msg_body_dict: dict):
    type = msg_body_dict.get('type', -1)  # int
    device_id = msg_body_dict.get('device_id', -1)  # int
    command = msg_body_dict.get('command', -1)  # int
    result = msg_body_dict.get('result', -1)  # int
    if result == 0:
        get_otaprogress(-4)
    if result == 1:
        get_otaprogress(0)


'''升级进度消息'''


#  0x69
def app_upgrade_progress(msg_body_dict: dict):
    type = msg_body_dict.get('type', -1)  # int
    device_id = msg_body_dict.get('device_id', -1)  # int
    process = msg_body_dict.get('process', -1)  # int
    if 0 <= process <= 100:
        get_otaprogress(int(process))


'''升级结果消息'''


#  0x6A
def app_upgrade_result(msg_body_dict: dict):
    type = msg_body_dict.get('type', -1)  # int
    device_id = msg_body_dict.get('device_id', -1)  # int
    result = msg_body_dict.get('result', -1)  # int

    if type == 4:
        if result == 1:
            if HHhdlist.ota_version is not None:
                set_version(HHhdlist.ota_version)
            HStategrid.save_DeviceInfo("dtu_ota_version", 1, HStategrid.get_before_last_dot(HStategrid.dtu_ota)[1], 0)
            get_otaprogress(100)
        if result == 0:
            get_otaprogress(-4)
            file_ota = "/opt/hhd/dtu20.tar.gz"
            if os.path.isfile(file_ota):
                os.remove(file_ota)
            else:
                pass


'''读取版本号应答消息'''


#  0x6B
def app_read_version_number_response(msg_body_dict: dict):
    type = msg_body_dict.get('type', -1)  # int
    device_id = msg_body_dict.get('device_id', -1)  # int
    soft_version = msg_body_dict.get('soft_version', [])  # string
    hard_version = msg_body_dict.get('hard_version', [])  # string

    if type == 4:
        for i in range(0, len(soft_version)):
            dtu_ota_version = HStategrid.get_DeviceInfo("dtu_ota_version")
            if dtu_ota_version is None:
                dtu_ota_version = ".00"
                HStategrid.save_DeviceInfo("dtu_ota_version", 1, ".00", 0)
            HStategrid.save_VerInfoEvt(i, 4, hard_version[i], soft_version[i], dtu_ota_version)
    if type == 0:
        for i in range(0, len(soft_version)):
            tiu_ota_version = HStategrid.get_DeviceInfo("tiu_ota_version")
            if tiu_ota_version is None:
                tiu_ota_version = ".00"
                HStategrid.save_DeviceInfo("tiu_ota_version", 1, ".00", 0)
            HStategrid.save_VerInfoEvt(i, 0, hard_version[i], soft_version[i], tiu_ota_version)
    if type == 3:
        for i in range(0, len(soft_version)):
            ccu_ota_version = HStategrid.get_DeviceInfo("ccu_ota_version")
            if ccu_ota_version is None:
                ccu_ota_version = ".00"
                HStategrid.save_DeviceInfo("ccu_ota_version", 1, ".00", 0)
            HStategrid.save_VerInfoEvt(i, 3, hard_version[i], soft_version[i], ccu_ota_version)
    if type == 1:
        for i in range(0, len(soft_version)):
            gcu_ota_version = HStategrid.get_DeviceInfo("gcu_ota_version")
            if gcu_ota_version is None:
                gcu_ota_version = ".00"
                HStategrid.save_DeviceInfo("gcu_ota_version", 1, ".00", 0)
            HStategrid.save_VerInfoEvt(i, 1, hard_version[i], soft_version[i], gcu_ota_version)
    if type == 2:
        for i in range(0, len(soft_version)):
            pdu_ota_version = HStategrid.get_DeviceInfo("pdu_ota_version")
            if pdu_ota_version is None:
                pdu_ota_version = ".00"
                HStategrid.save_DeviceInfo("pdu_ota_version", 1, ".00", 0)
            HStategrid.save_VerInfoEvt(i, 2, hard_version[i], soft_version[i], pdu_ota_version)


'''参数读取应答消息'''


#  0x6C
def app_parameter_fetch_response(msg_body_dict: dict):
    device_type = msg_body_dict.get('device_type', -1)  # int
    device_num = msg_body_dict.get('device_num', -1)  # int
    invalid_id = msg_body_dict.get('invalid_id', [])  # array
    count = msg_body_dict.get('count', -1)  # int
    param_info = msg_body_dict.get('param_info', [])  # array

    try:
        for i in range(0, count):
            param_info_id = param_info[i].get("id")
            data_type = param_info[i].get("type", -1)

            if data_type == 0:
                param_info_value = param_info[i].get("intvalue")
                HStategrid.save_DeviceInfo(str(device_type) + str(device_num) + str(param_info_id), 2, "null",
                                           param_info_value)
            if data_type == 1:
                param_info_value = param_info[i].get("boolvalue")
                HStategrid.save_DeviceInfo(str(device_type) + str(device_num) + str(param_info_id), 4, "null",
                                           param_info_value)
            if data_type == 2:
                param_info_value = param_info[i].get("floatvalue")
                HStategrid.save_DeviceInfo(str(device_type) + str(device_num) + str(param_info_id), 3, "null",
                                           param_info_value)
            if data_type == 3:
                param_info_value = param_info[i].get("strvalue")
                HStategrid.save_DeviceInfo(str(device_type) + str(device_num) + str(param_info_id), 1, param_info_value,
                                           0)

        return 0
    except Exception as e:
        HSyslog.log_info(f"app_parameter_fetch_response's error: {e} .{inspect.currentframe().f_lineno}")


'''时间同步消息'''


def app_time_sync(device_time):
    msg = {
        'year': device_time.get("year"),
        'month': device_time.get("month"),
        'day': device_time.get("day"),
        'hour': device_time.get("hour"),
        'minute': device_time.get("minute"),
        'second': device_time.get("second")
    }
    topic = HHhdlist.topic_app_time_sync
    app_publish(topic, msg)
    return True


'''当前/历史读取应答消息'''


#  0x6D
def app_current_history_fetch_response(msg_body_dict: dict):
    total = msg_body_dict.get('total', -1)  # int
    count = msg_body_dict.get('count', -1)  # int
    type = msg_body_dict.get('type', -1)  # int
    faults = msg_body_dict.get('faults', [])  # array
    faults_device_num = []
    faults_fault_id = []
    faults_start_time = []
    faults_end_time = []
    faults_desc = []
    if len(faults) == count:
        for i in range(0, count):
            faults_device_num.append(faults[i].get('device_num', -1))  # int
            faults_fault_id.append(faults[i].get('fault_id', -1))  # int
            faults_start_time.append(faults[i].get('start_time', -1))  # int
            faults_end_time.append(faults[i].get('end_time', -1))  # int
            faults_desc.append(faults[i].get('device_num', ''))  # string


'''事件读取应答消息'''


#  0x6E
def app_event_Event_fetch_response(msg_body_dict: dict):
    total = msg_body_dict.get('total', -1)  # int
    count = msg_body_dict.get('count', -1)  # int
    events = msg_body_dict.get('events', [])  # array
    events_device_num = []
    events_event_id = []
    events_time = []
    events_reserved = []
    events_desc = []
    if len(events) == count:
        for i in range(0, count):
            events_device_num.append(events[i].get('device_num', -1))  # int
            events_event_id.append(events[i].get('event_id', -1))  # int
            events_time.append(events[i].get('time', -1))  # int
            events_reserved.append(events[i].get('reserved', -1))  # int
            events_desc.append(events[i].get('desc', ''))  # string


#################################################################################################

'''网络状态信息'''
'''netSigVal(信号强度等级)：0-31'''


def app_net_status(netType: Enum, netSigVal: int, netId: Enum):
    msg_body = {'netType': netType,
                'netSigVal': netSigVal,
                'netid': netId
                }
    topic = HHhdlist.topic_app_net_status
    app_publish(topic, msg_body)
    return True


'''充电请求应答消息'''


def app_charge_request_response(msg_body_dict: dict):
    topic = HHhdlist.topic_app_charge_request_response
    app_publish(topic, msg_body_dict)
    return True


'''充电控制消息'''


def app_charge_control(msg_body_dict: dict):
    info = msg_body_dict.get("info_id", "")
    if info != "":
        if info == 7:
            gunNo = msg_body_dict.get("gunNo")
            if msg_body_dict.get("result") == 10:
                result = 1
                failure_reason = 0
            elif msg_body_dict.get("result") == 17 or msg_body_dict.get("result") == 15:
                result = 0
                failure_reason = 2
            elif msg_body_dict.get("result") == 24 or msg_body_dict.get("result") == 25:
                result = 0
                failure_reason = 3
            else:
                result = 0
                failure_reason = 1

            account_info = {
                "stop_code": HHhdlist.device_charfer_p.get(gunNo).get("stopCode"),
                "balance": 0,
                "billing": 0,
                "overdraft_limit": 0,
                "electric_discount": 0,
                "service_discount": 0,
                "multi_charge": 0,
            }
            data = {
                "gun_id": gunNo - 1,
                "result": result,
                "failure_reason": failure_reason,
                "account_info": account_info
            }
            app_authentication_response(data)
            HHhdlist.authstart.set()

            data1 = {
                "gunNo": gunNo,
                "preTradeNo": HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo"),
                "tradeNo": HHhdlist.device_charfer_p.get(gunNo).get("tradeNo"),
                "startResult": 10,
                "faultCode": 0,
                "vinCode": HHhdlist.device_charfer_p.get(gunNo).get("vin"),
            }
            HTools.Htool_send_startChaResEvt(data1)

            HHhdlist.device_charfer_p[gunNo].update({"balance": 0})
            HHhdlist.device_charfer_p[gunNo].update({"billing": 0})
            HHhdlist.device_charfer_p[gunNo].update({"overdraft_limit": 0})
            HHhdlist.device_charfer_p[gunNo].update({"electric_discount": 0})
            HHhdlist.device_charfer_p[gunNo].update({"service_discount": 0})
            HHhdlist.device_charfer_p[gunNo].update({"multi_charge": 0})
        if info == 8:
            gunNo = msg_body_dict.get("gunNo")
            msg = {
                'info_id': info,
                'gun_id': gunNo - 1,
                'command_type': 0x01,
                'start_source': HHhdlist.device_charfer_p.get(gunNo).get("start_source"),
                'user_id': HHhdlist.device_charfer_p.get(gunNo).get("user_id"),
                'appointment_time': 0,
                'cloud_session_id': HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo"),
                'multi_charge_mode': 0,
                'account_info': {
                    'stop_code': HHhdlist.device_charfer_p.get(gunNo).get("stopCode"),
                    'balance': HHhdlist.device_charfer_p.get(gunNo).get("balance"),
                    'billing': HHhdlist.device_charfer_p.get(gunNo).get("billing"),
                    'overdraft_limit': HHhdlist.device_charfer_p.get(gunNo).get("overdraft_limit"),
                    'electric_discount': HHhdlist.device_charfer_p.get(gunNo).get("electric_discount"),
                    'service_discount': HHhdlist.device_charfer_p.get(gunNo).get("service_discount"),
                    'multi_charge': HHhdlist.device_charfer_p.get(gunNo).get("multi_charge"),
                },
                'temp_strategy': {
                    'delay_time': HHhdlist.device_charfer_p.get(gunNo).get("delay_time"),
                    'stop_type': HHhdlist.device_charfer_p.get(gunNo).get("stop_type"),
                    'stop_condition': HHhdlist.device_charfer_p.get(gunNo).get("stop_condition"),
                },
                'temp_rate': {
                    'rate_id': "",
                    'count': 0,
                    'items': []
                }
            }
            topic = HHhdlist.topic_app_charge_control
            app_publish(topic, msg)
        if info == 6:
            try:
                gunNo = msg_body_dict.get("gunNo")
                deviceName = HStategrid.get_DeviceInfo("deviceName")
                stop_type = HStategrid.get_stop_type(HHhdlist.device_charfer_p.get(gunNo).get("chargeMode"))
                stop_condition = HStategrid.get_stop_condition(HHhdlist.device_charfer_p.get(gunNo).get("chargeMode"),
                                                               HHhdlist.device_charfer_p.get(gunNo).get("limitData"))
                start_source = HStategrid.get_start_source(HHhdlist.device_charfer_p.get(gunNo).get("startType"))
                msg = {
                    'info_id': info,
                    'gun_id': gunNo - 1,
                    'command_type': 0,
                    'start_source': start_source,
                    'user_id': deviceName,
                    'appointment_time': 0,
                    'cloud_session_id': HHhdlist.device_charfer_p.get(gunNo).get("preTradeNo"),
                    'multi_charge_mode': 0,
                    'account_info': {
                        'stop_code': HHhdlist.device_charfer_p.get(gunNo).get("stopCode"),
                        'balance': 0,
                        'billing': 0,
                        'overdraft_limit': 0,
                        'electric_discount': 0,
                        'service_discount': 0,
                        'multi_charge': 0,
                    },
                    'temp_strategy': {
                        'delay_time': -1,
                        'stop_type': stop_type,
                        'stop_condition': stop_condition,
                    },
                    'temp_rate': {
                        'rate_id': "",
                        'count': 0,
                        'items': []
                    }
                }
                topic = HHhdlist.topic_app_charge_control
                app_publish(topic, msg)

                HHhdlist.device_charfer_p[gunNo].update({"balance": 0})
                HHhdlist.device_charfer_p[gunNo].update({"overdraft_limit": 0})
                HHhdlist.device_charfer_p[gunNo].update({"electric_discount": 0})
                HHhdlist.device_charfer_p[gunNo].update({"service_discount": 0})
                HHhdlist.device_charfer_p[gunNo].update({"multi_charge": 0})
                HHhdlist.device_charfer_p[gunNo].update({"billing": 0})
                HHhdlist.device_charfer_p[gunNo].update({"user_id": deviceName})
                HHhdlist.device_charfer_p[gunNo].update({"delay_time": -1})
                HHhdlist.device_charfer_p[gunNo].update({"stop_type": 0})
                HHhdlist.device_charfer_p[gunNo].update({"stop_condition": 0})
            except Exception as e:
                HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")
                HSyslog.log_info(HHhdlist.device_charfer_p.get("preTradeNo") + e)
    else:
        HSyslog.log_info("控制消息有误")
    return True


'''车辆VIN鉴权应答消息'''


def app_authentication_response(msg_body_dict: dict):
    try:
        topic = HHhdlist.topic_app_app_authentication_response
        app_publish(topic, msg_body_dict)
        return True
    except Exception as e:
        HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")
        return False


'''充电结算消息'''


def app_charge_settlement(gun_id: int,  # 充电枪ID
                          cloud_session_id: str,  # 充电会话ID（平台）
                          user_id: str,  # 用户ID/卡ID
                          balance: int,  # 余额 分辨率0.001元
                          kwh: int,  # 充电电量 分辨率0.001kW.h
                          electric_charge: int,  # 充电电费 分辨率0.001元
                          service_charge: int,  # 充电服务费 分辨率0.001元
                          total_cost: int  # 充电总费用 分辨率0.001元
                          ):
    msg_body = {
        'gun_id': gun_id,
        'cloud_session_id': cloud_session_id,
        'user_id': user_id,
        'balance': balance,
        'kwh': kwh,
        'electric_charge': electric_charge,
        'service_charge': service_charge,
        'total_cost': total_cost
    }
    topic = HHhdlist.topic_app_charge_settlement
    app_publish(topic, msg_body)
    return True


'''账户充值消息'''


def app_account_recharge(gun_id: int,
                         cloud_session_id: str,
                         user_id: str,
                         card_id: str,
                         balance: int
                         ):
    msg_body = {
        'gun_id': gun_id,
        'cloud_session_id': cloud_session_id,
        'user_id': user_id,
        'card_id': card_id,
        'balance': balance,
    }
    topic = HHhdlist.topic_app_account_recharge
    app_publish(topic, msg_body)
    return True


'''充电费率请求应答消息'''


def app_charge_rate_request_response(result: int):  # 0:成功， 1：失败
    if result not in range(0, 2):
        HSyslog.log_info("app_charge_rate_request_response para error")
        return False
    msg_body = {
        'result': result
    }
    topic = HHhdlist.topic_app_charge_rate_request_response
    app_publish(topic, msg_body)
    return True


'''充电启动策略请求应答消息'''


def app_charge_start_strategy_request_response(result: int):  # 0:成功， 1：失败
    if result not in range(0, 2):
        HSyslog.log_info("app_charge_start_strategy_request_response para error")
        return False
    msg_body = {
        'result': result
    }
    topic = HHhdlist.topic_app_charge_start_strategy_request_response
    app_publish(topic, msg_body)
    return True


'''功率分配策略请求应答消息'''


def app_power_allocation_strategy_request_response(result: int):  # 0:失败， 1：成功
    if result not in range(0, 2):
        HSyslog.log_info("app_power_allocation_strategy_request_response para error")
        return False
    msg_body = {
        'result': result
    }
    topic = HHhdlist.topic_app_power_allocation_strategy_request_response
    app_publish(topic, msg_body)
    return True


'''离线名单版本应答消息'''


def app_offline_list_version_response(result: int):  # 0:成功， 1：失败
    if result not in range(0, 2):
        HSyslog.log_info("app_offline_list_version_response para error")
        return False
    msg_body = {
        'result': result
    }
    topic = HHhdlist.topic_app_offline_list_version_response
    app_publish(topic, msg_body)
    return True


'''充电会话应答消息'''


def app_charge_session_response(result: int):  # 0:成功， 1：失败
    if result not in range(0, 2):
        HSyslog.log_info("app_charge_session_response para error")
        return False
    msg_body = {
        'result': result
    }
    topic = HHhdlist.topic_app_charge_session_response
    app_publish(topic, msg_body)
    return True


'''设置参数消息'''


def app_set_parameters(msg_body_dict: dict):
    topic = HHhdlist.topic_app_set_parameters
    app_publish(topic, msg_body_dict)
    return True


'''二维码更新消息'''


def app_QR_code_update(msg_body_dict: dict):
    topic = HHhdlist.topic_app_QR_code_update
    app_publish(topic, msg_body_dict)
    return True


'''充电费率同步消息'''


def app_charge_rate_sync_message(msg_body_dict: dict, type=1, count=1):
    try:
        eleModelId = msg_body_dict.get("eleModelId", "")
        serModelId = msg_body_dict.get("serModelId", "")
        timeNum = msg_body_dict.get("TimeNum", 0)  # 1-48
        timeSeg = msg_body_dict.get("TimeSeg", [])
        segFlag = msg_body_dict.get("SegFlag", [])
        chargeFee = msg_body_dict.get("chargeFee", [])
        serviceFee = msg_body_dict.get("serviceFee", [])
    except Exception as e:
        HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")
        HSyslog.log_info(f"app_charge_rate_sync_message: {msg_body_dict}")
        return False

    try:
        if timeSeg[0] == "0000":
            msg = {
                "type": type,  # 1:全量下发
                "count": count,  # [0-8]
                "items": [],
            }
            msg_items = {
                "num": count,  # 从1开始
                "id": eleModelId + serModelId,
                "count": timeNum,  # [1-16]
                "contents": [],
                "commencement_date": int(time.time()),
                "last_updated": int(time.time()),
                "charge_type": 0,
            }
            for i in range(0, timeNum):
                msg_items_contents = {"num": i + 1, "type": None, "start_time": None, "stop_time": None,
                                      "electric_rate": None,
                                      "service_rate": None}
                if segFlag[i] - 9 < 0:
                    break
                msg_items_contents["type"] = segFlag[i] - 9
                msg_items_contents["start_time"] = int(timeSeg[i][0:2]) * 3600 + int(timeSeg[i][2:4]) * 60
                if i == timeNum - 1:
                    msg_items_contents["stop_time"] = 86400
                else:
                    msg_items_contents["stop_time"] = int(timeSeg[i + 1][0:2]) * 3600 + int(
                        timeSeg[i + 1][2:4]) * 60
                msg_items_contents["electric_rate"] = chargeFee[segFlag[i] - 9 - 1] * 100
                msg_items_contents["service_rate"] = serviceFee[segFlag[i] - 9 - 1] * 100

                msg_items["contents"].append(msg_items_contents)
                # print("msg_items[contents]: ", msg_items["contents"])

            msg["items"].append(msg_items)
        else:
            msg = {
                "type": type,  # 1:全量下发
                "count": count,  # [0-8]
                "items": [],
            }
            msg_items = {
                "num": count,  # 从1开始
                "id": eleModelId + serModelId,
                "count": timeNum + 1,  # [1-16]
                "contents": [],
                "commencement_date": int(time.time()),
                "last_updated": int(time.time()),
                "charge_type": 0,
            }
            for i in range(0, timeNum):
                msg_items_contents = {"num": i + 2, "type": None, "start_time": None, "stop_time": None,
                                      "electric_rate": None,
                                      "service_rate": None}
                if segFlag[i] - 9 < 0:
                    break
                msg_items_contents["type"] = segFlag[i] - 9
                msg_items_contents["start_time"] = int(timeSeg[i][0:2]) * 3600 + int(timeSeg[i][2:4]) * 60
                if i == timeNum - 1:
                    msg_items_contents["stop_time"] = 86400
                else:
                    msg_items_contents["stop_time"] = int(timeSeg[i + 1][0:2]) * 3600 + int(
                        timeSeg[i + 1][2:4]) * 60
                msg_items_contents["electric_rate"] = chargeFee[segFlag[i] - 9 - 1] * 100
                msg_items_contents["service_rate"] = serviceFee[segFlag[i] - 9 - 1] * 100

                msg_items["contents"].append(msg_items_contents)
                # print("msg_items[contents]: ", msg_items["contents"])

            msg["items"].append(msg_items)
            msg.get("items")[count - 1].get("contents").insert(0, {
                "num": 1,
                "type": 1,
                "start_time": 0,
                "stop_time": int(timeSeg[0][0:2]) * 3600 + int(timeSeg[0][2:4]) * 60 - 1,
                "electric_rate": 0,
                "service_rate": 0
            })

        HStategrid.save_DeviceInfo("feeid", 1, eleModelId + serModelId, 0)
        HStategrid.save_DeviceInfo("eleModelId", 1, eleModelId, 0)
        HStategrid.save_DeviceInfo("serModelId", 1, serModelId, 0)
        topic = HHhdlist.topic_app_charge_rate_sync_message
        app_publish(topic, msg)
        return True
    except Exception as e:
        HSyslog.log_info(f"{e} .{inspect.currentframe().f_lineno}")
        HSyslog.log_info(f"app_charge_rate_sync_message: {msg}")
        return False


'''充电启动策略同步消息'''


def app_charge_start_strategy_sync():
    msg = {

    }
    topic = HHhdlist.topic_app_charge_start_strategy_sync
    app_publish(topic, msg)
    return True


'''功率分配策略同步消息'''


def app_power_allocation_strategy_sync(info: dict):
    msg = {
        "type": 1,
        "count": None,
        "items": []
    }
    items_mas = {
        "num": None,
        "id": None,
        "commencement_date": None,
        "last_updated": None,
        "count": None,
        "strategy": None
    }
    strategy_items_msg = {
        "num": None,
        "start_time": None,
        "stop_time": None,
        "type": None,
        "allot_priority": None,
        "charge_priority": None,
    }
    topic = HHhdlist.topic_app_power_allocation_strategy_sync
    app_publish(topic, msg)
    return True


'''离线名单版本同步消息'''


def app_offline_list_version_sync():
    msg = {

    }
    topic = HHhdlist.topic_app_offline_list_version_sync
    app_publish(topic, msg)
    return True


'''离线名单项操作日志消息'''


def app_offline_list_item_operation_log():
    msg = {

    }
    topic = HHhdlist.topic_app_offline_list_item_operation_log
    app_publish(topic, msg)
    return True


'''清除故障、事件消息'''


def app_clear_faults_events():
    msg = {

    }
    topic = HHhdlist.topic_app_clear_faults_events
    app_publish(topic, msg)
    return True


'''升级控制消息'''


def app_upgrade_control(msg_body_dict: dict):
    topic = HHhdlist.topic_app_upgrade_control
    app_publish(topic, msg_body_dict)
    return True


'''参数读取消息'''


def app_fetch_parameter(msg_body_dict: dict):
    topic = HHhdlist.topic_app_fetch_parameter
    app_publish(topic, msg_body_dict)
    return True


'''当前/历史故障读取消息'''


def app_fetch_current_Historical_fault():
    msg = {

    }
    topic = HHhdlist.topic_app_fetch_current_Historical_fault
    app_publish(topic, msg)
    return True


'''事件读取消息'''


def app_fetch_event():
    msg = {

    }
    topic = HHhdlist.topic_app_fetch_event
    app_publish(topic, msg)
    return True


app_func_dict = {
    "/hqc/sys/time-sync": {"isSubscribe": False, "isResp": False, "qos": 0, "func": None},
    "/hqc/sys/network-state": {"isSubscribe": False, "isResp": False, "qos": 0, "func": None},
    "/hqc/main/telemetry-notify/fault": {"isSubscribe": True, "isResp": False, "qos": 1,
                                         "func": app_device_fault},
    "/hqc/cloud/event-notify/fault": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/telemetry-notify/info": {"isSubscribe": True, "isResp": False, "qos": 0,
                                        "func": app_telemetry_telesignaling},
    "/hqc/cloud/event-notify/info": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/event-notify/request-charge": {"isSubscribe": True, "isResp": True, "qos": 2,
                                              "func": app_charge_request},
    "/hqc/main/event-reply/request-charge": {"isSubscribe": False, "isResp": False, "qos": 2, "func": None},
    "/hqc/main/event-notify/control-charge": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/event-reply/control-charge": {"isSubscribe": True, "isResp": False, "qos": 2,
                                             "func": app_charging_control_response},
    "/hqc/main/event-notify/check-vin": {"isSubscribe": True, "isResp": True, "qos": 2,
                                         "func": app_vin_authentication},
    "/hqc/main/event-reply/check-vin": {"isSubscribe": False, "isResp": False, "qos": 2, "func": None},
    "/hqc/ui/event-notify/auth-gun": {"isSubscribe": False, "isResp": False, "qos": 2, "func": None},
    "/hqc/main/event-notify/charge-record": {"isSubscribe": True, "isResp": True, "qos": 2,
                                             "func": app_charging_record},
    "/hqc/main/event-reply/charge-record": {"isSubscribe": False, "isResp": False, "qos": 2, "func": None},
    "/hqc/main/event-notify/charge-cost": {"isSubscribe": True, "isResp": False, "qos": 2,
                                           "func": app_charge_fee},
    "/hqc/main/event-notify/charge-elec": {"isSubscribe": True, "isResp": False, "qos": 2,
                                           "func": app_charge_battery_frozen},
    "/hqc/main/event-notify/charge-account": {"isSubscribe": False, "isResp": False, "qos": 1, "func": None},
    "/hqc/cloud/event-notify/recharge": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/cloud/event-reply/recharge": {"isSubscribe": True, "isResp": False, "qos": 2,
                                        "func": app_account_recharge_response},
    "/hqc/cloud/event-notify/request-rate": {"isSubscribe": True, "isResp": True, "qos": 2,
                                             "func": app_rate_request},
    "/hqc/cloud/event-reply/request-rate": {"isSubscribe": False, "isResp": False, "qos": 2, "func": None},
    "/hqc/cloud/event-notify/request-startup": {"isSubscribe": True, "isResp": True, "qos": 2,
                                                "func": app_charge_start_strategy_request},
    "/hqc/cloud/event-reply/request-startup": {"isSubscribe": False, "isResp": False, "qos": 2, "func": None},
    "/hqc/cloud/event-notify/request-dispatch": {"isSubscribe": True, "isResp": True, "qos": 2,
                                                 "func": app_power_allocation_policy_request},
    "/hqc/cloud/event-reply/request-dispatch": {"isSubscribe": False, "isResp": False, "qos": 2, "func": None},
    "/hqc/cloud/event-notify/request-offlinelist": {"isSubscribe": True, "isResp": True, "qos": 2,
                                                    "func": app_offline_list_version_request},
    "/hqc/cloud/event-reply/request-offlinelist": {"isSubscribe": False, "isResp": False, "qos": 2, "func": None},
    "/hqc/main/event-notify/charge-session": {"isSubscribe": True, "isResp": True, "qos": 1,
                                              "func": app_charge_session},
    "/hqc/main/event-reply/charge-session": {"isSubscribe": False, "isResp": False, "qos": 1, "func": None},
    "/hqc/main/event-notify/update-param": {"isSubscribe": False, "isResp": True, "qos": 2,
                                            "func": None},
    "/hqc/main/event-reply/update-param": {"isSubscribe": True, "isResp": False, "qos": 2,
                                           "func": app_set_parameter_response},
    "/hqc/main/event-notify/update-qrcode": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/event-reply/update-qrcode": {"isSubscribe": True, "isResp": False, "qos": 2,
                                            "func": app_QR_code_update_response},
    "/hqc/main/event-notify/update-rate": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/event-reply/update-rate": {"isSubscribe": True, "isResp": False, "qos": 2,
                                          "func": app_charge_rate_sync_response},
    "/hqc/main/event-notify/update-startup": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/event-reply/update-startup": {"isSubscribe": True, "isResp": False, "qos": 2,
                                             "func": app_charge_start_strategy_sync_response},
    "/hqc/main/event-notify/update-dispatch": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/event-reply/update-dispatch": {"isSubscribe": True, "isResp": False, "qos": 2,
                                              "func": app_power_allocation_strategy_sync_response},
    "/hqc/main/event-notify/update-offlinelist": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/event-reply/update-offflinelist": {"isSubscribe": True, "isResp": False, "qos": 2,
                                                  "func": app_offline_list_version_sync_response},
    "/hqc/main/event-notify/offlinelist-log": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/event-reply/offlinelist-log": {"isSubscribe": True, "isResp": False, "qos": 2,
                                              "func": app_offline_list_operation_log_response},
    "/hqc/main/event-notify/clear": {"isSubscribe": False, "isResp": True, "qos": 2, "func": None},
    "/hqc/main/event-reply/clear": {"isSubscribe": True, "isResp": False, "qos": 2,
                                    "func": app_clear_faults_event_response},
    "/hqc/sys/upgrade-notify/notify": {"isSubscribe": False, "isResp": True, "qos": 1, "func": None},
    "/hqc/sys/upgrade-reply/notify": {"isSubscribe": True, "isResp": False, "qos": 1,
                                      "func": app_upgrade_control_response},
    "/hqc/sys/upgrade-notify/process": {"isSubscribe": True, "isResp": False, "qos": 0,
                                        "func": app_upgrade_progress},
    "/hqc/sys/upgrade-notify/result": {"isSubscribe": True, "isResp": False, "qos": 1,
                                       "func": app_upgrade_result},
    "/hqc/sys/upgrade-notify/version": {"isSubscribe": False, "isResp": True, "qos": 1,
                                        "func": None},
    "/hqc/sys/upgrade-reply/version": {"isSubscribe": True, "isResp": False, "qos": 1,
                                       "func": app_read_version_number_response},
    "/hqc/main/event-notify/read-param": {"isSubscribe": False, "isResp": True, "qos": 1, "func": None},
    "/hqc/main/event-reply/read-param": {"isSubscribe": True, "isResp": False, "qos": 1,
                                         "func": app_parameter_fetch_response},
    "/hqc/main/event-notify/read-fault": {"isSubscribe": False, "isResp": True, "qos": 1, "func": None},
    "/hqc/main/event-reply/read-fault": {"isSubscribe": True, "isResp": False, "qos": 1,
                                         "func": app_current_history_fetch_response},
    "/hqc/main/event-notify/read-event": {"isSubscribe": False, "isResp": True, "qos": 1, "func": None},
    "/hqc/main/event-reply/read-event": {"isSubscribe": True, "isResp": False, "qos": 1,
                                         "func": app_event_Event_fetch_response}
}
