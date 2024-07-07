import queue
import threading
from datetime import datetime
from enum import Enum

ota_version = None

device_mqtt_status = False
qr_queue = queue.Queue()
fee_queue = queue.Queue()

device_charfer_p = {}  # 平台充电参数
'''
device_charfer_p{
    1:{}
    2:{}
}
'''

device_flaut_warn = {}  # 告警故障
'''
{
    0: {'flaut': [1000], 'warn': [1002], 'regular': [1004]}, 
    1: {'flaut': [1001]}, 
    2: {'flaut': [1001]}, 
    3: {'flaut': [1001]}, 
    6: {'regular': [1005]}}
}
'''
chargeSys = {}  # 系统
cabinet = {}  # 主机柜
gun = {}  # 枪
pdu = {}  # 模块控制器
module = {}  # 模块
bms = {}  # bms
meter = {}  # 电表
parkLock = {}  # 地锁

authstart = threading.Event()
gun_status = {}
charger_status = {
    "leisure": 0,
    "starting": 1,
    "charging": 2,
    "stopping": 3,
    "finish": 4,
    "fault": 5,
}

bms_sum = {}

topic_app_net_status = '/hqc/sys/network-state'
topic_app_device_fault_query = '/hqc/cloud/event-notify/fault'
topic_app_telemetry_remote_query = '/hqc/cloud/event-notify/info'
topic_app_charge_request_response = '/hqc/main/event-reply/request-charge'
topic_app_charge_control = '/hqc/main/event-notify/control-charge'
topic_app_app_authentication_response = '/hqc/main/event-reply/check-vin'
topic_app_charge_record_response = '/hqc/main/event-reply/charge-record'
topic_app_charge_settlement = '/hqc/main/event-notify/charge-account'
topic_app_account_recharge = '/hqc/cloud/event-notify/recharge'
topic_app_charge_rate_request_response = '/hqc/cloud/event-reply/request-rate'
topic_app_charge_start_strategy_request_response = '/hqc/cloud/event-reply/request-startup'
topic_app_power_allocation_strategy_request_response = '/hqc/cloud/event-reply/request-dispatch'
topic_app_offline_list_version_response = '/hqc/cloud/event-reply/request-offlinelist'
topic_app_charge_session_response = '/hqc/main/event-reply/charge-session'
topic_app_set_parameters = '/hqc/main/event-notify/update-param'
topic_app_QR_code_update = '/hqc/main/event-notify/update-qrcode'
topic_app_charge_rate_sync_message = '/hqc/main/event-notify/update-rate'
topic_app_charge_start_strategy_sync = '/hqc/main/event-notify/update-startup'
topic_app_power_allocation_strategy_sync = '/hqc/main/event-notify/update-dispatch'
topic_app_offline_list_version_sync = '/hqc/main/event-notify/update-offlinelist'
topic_app_offline_list_item_operation_log = '/hqc/main/event-notify/offlinelist-log'
topic_app_clear_faults_events = '/hqc/main/event-notify/clear'
topic_app_upgrade_control = '/hqc/sys/upgrade-notify/notify'
topic_app_read_version_number = '/hqc/sys/upgrade-notify/version'
topic_app_fetch_parameter = '/hqc/main/event-notify/read-param'
topic_app_fetch_current_Historical_fault = '/hqc/main/event-notify/read-fault'
topic_app_fetch_event = '/hqc/main/event-notify/read-event'
topic_app_time_sync = '/hqc/sys/time-sync'


class net_type(Enum):  # 网络状态
    no_net = 0
    other_net = 1
    net_4G = 2
    net_5G = 3
    NB_IOT = 4
    WIFI = 5
    wired_net = 6


class net_id(Enum):  # 网络运营商
    unknow = 0
    id_4G = 1
    id_cable = 2
    id_WIFI = 3


#  充电枪遥测
Gun_Pistol = {
    0: None,
    1: None,
    2: None,
    3: None,
    4: None,
    5: None,
    6: None,
    7: None,
    8: None,
    9: None,
    10: None,
    11: None,
    12: None,
    110: None,
    111: None,
    112: None,
    113: None,
    114: None,
    115: None,
    116: None,
    117: None,
    118: None,
    119: None,
    120: None,
    121: None,
    122: None,
    123: None,
    124: None,
    125: None,
    126: None,
    127: None,
    128: None,
    129: None,
    130: None,
}

#  充电系统遥测
Device_Pistol = {
    20: None,
    21: None,
    22: None,
    23: None,
    24: None,
    25: None,
    26: None,
    27: None,
    28: None,
    29: None,
    31: None,
    32: None,
}

#  功率柜遥测
Power_Pistol = {
    0: None,
    1: None,
    2: None,
    3: None,
    4: None,
    110: None,
    111: None,
    112: None,
    113: None,
    114: None,
    115: None,
    116: None,
    117: None,
    118: None,
    119: None,
}

#  功率单元遥测
Power_Unit_Pistol = {
    1: None,
    2: None,
    3: None,
    4: None,
    5: None,
    6: None,
}

#  功率控制遥信
Power_Crrl_Plug = {
    1: None,
    2: None,
    3: None,
    4: None,
    5: None,
    6: None,
}

#  BMS遥测
BMS_disposable_Pistol = {
    0: None,
    1: None,
    2: None,
    3: None,
    4: None,
    5: None,
    6: None,
    7: None,
    8: None,
    9: None,
    10: None,
    11: None,
    12: None,
    13: None,
    14: None,
    15: None,
    16: None,
    17: None,
    18: None,
    100: None,
    101: None,
    102: None,
    103: None,
    104: None,
    105: None,
    106: None,
    107: None,
    108: None,
    109: None,
    110: None,
    111: None,
    112: None,
    113: None,
}

#  电表遥测
Meter_Pistol = {
    0: None,
    1: None,
    2: None,
    3: None,
    4: None,
    5: None,
    6: None,
}

#  地锁遥信
Ground_Plug = {
    0: None,
    1: None,
}


def do_start_source(i):
    if i == 10:
        return 0x01
    elif i == 11:
        return 0x07
    elif i == 12:
        return 0x3F
    elif i == 13:
        return 0x01
    elif i == 14:
        return 0x3F
    elif i == 15:
        return 0x04


def unix_time(unix_t):
    dt_time = datetime.fromtimestamp(unix_t)
    return dt_time.strftime("%y%m%d")


def unix_time_14(unix_t):
    dt_time = datetime.fromtimestamp(unix_t)
    return dt_time.strftime("%Y%m%d%H%M%S")

