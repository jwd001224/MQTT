import glob
import gzip
import inspect
import os
import queue
import re
import subprocess
import time
from datetime import datetime
import sqlite3

import HSyslog

"""国网平台"""

link_init_status = 0
property_status = 0
flaut_status = 0
net_status = 0

platform_data = {
    "netType": 13,
    "sigVal": 10,
    "netId": 14,
}

current_timestamp = time.time()  # 系统精确时间
log_queue = queue.Queue()

deviceCode = None  # 出厂编码
Vendor_Code = 1031  # 厂商代码
Manufacture_Date = None  # 出厂日期
device_type = {  # 设备类型
    "DC": "01",
    "AC": "02",
    "AC/DC": "03",
    "Gateway": "04"
}

data_path = "/opt/hhd/Platform.db"
syslog_path = '/var/log'  # 替换为实际路径
dtu_ota = ""
heartbeat = 0

device_hard = {
    "DTU": 4,
    "TIU": 0,
    "GCU": 1,
    "PDU": 2,
    "CCU": 3,
}

ack_num = {}

flaut_warning_type = {
    "device": {
        "regular": {},
        "flaut": {
            3030: [],
            3031: [47],
            3032: [16, 72],
            3034: [21, 75],
            3035: [400],
            3038: [31, 102, 103, 104, 406, 445],
            3039: [],
            3040: [30, 407, 409],
            3042: [39, 167],
            3048: [],
            3049: [95],
            3055: [110, 501],
            3056: [22, 40, 92, 93, 446],
            3064: [],
            3065: [96, 97, 98, 506, 507, 508],
            3073: [28, 29, 440, 441, 442, 443, 444, 447, 448, 449, 450, 451, 452, 453, 454, 455, 456, 457],
            3074: [],
            3075: [],
            3076: [],
            3077: [],
            3078: [],
            3079: [],
            3080: [],
            3081: [],
            3083: [],
            3084: [17, 73],
            3085: [41, 74],
        },
        "warn": {
            3041: [32],
            3052: [80, 258],
            3067: [],
            3068: [],
            3086: [46],
        }
    },
    "gun": {
        "regular": {
            1000: [13, 191, 227],  # 充满停止
            1001: [51, 52],  # 触控屏手动停止
            1002: [3, 4, 5, 11, 9, 24],  # 后台停止充电
            1003: [33],  # 达到设定充电时长停止
            1004: [37],  # 达到设定充电电量停止
            1005: [34],  # 达到设置充电金额停止
            1006: [],  # 达到离线停机条件
            1007: [35, 36, 57, 228, 229],  # 达到 SOC 终止条件停止
            1008: [20],
            1009: [1],
            1010: [],
            1011: [230]
        },
        "flaut": {
            3033: [15, 71],
            3036: [261],
            3037: [],
            3043: [58, 91],
            3044: [45],
            3045: [99],
            3046: [100, 101],
            3047: [108],
            3050: [152, 153, 154, 156, 157, 158, 159, 166, 604, 605],
            3051: [94, 606, 607],
            3054: [19, 76, 77, 78, 79],
            3057: [],
            3058: [],
            3059: [],
            3060: [],
            3061: [],
            3062: [25, 26, 27],
            3069: [165],
            3070: [601, 603],
            3071: [602, 610, 611],
            3072: [168],
            3082: [55],
            4008: [42, 43, 112, 121, 122, 124, 125, 126, 401, 402],
            4009: [131, 132, 133, 403],
            4010: [135, 136, 405],
            4011: [134, 404],
            4012: [138, 408],
            4013: [18, 105],
            4014: [],
            4015: [],
            4016: [],
            4018: [111, 502],
            4019: [],
            4020: [],
            4021: [],
            4022: [],
            5001: [],
            5002: [187],
            5003: [192, 193],
            5004: [202],
            5005: [197],
            5006: [224],
            5007: [243],
            5008: [56, 209],
            5009: [237],
            5010: [],
            5011: [184],
            5012: [246, 249, 250, 251, 252, 253, 254, 255, 256],
            5013: [],
            5014: [155, 232],
            5015: [233, 234],
            5016: [],
            5017: [],
            5018: [231, 239, 242, 257],
            5019: [213],
            5020: [214],
            5021: [215],
            5022: [216],
            5023: [217],
            5024: [218, 236],
            5025: [219],
            5026: [220, 235],
            5027: [],
            5028: [],
            5029: [238, 241],
            5030: [],
            5031: [],
            5032: [],
            5033: [],
            5034: [240],
            5035: [],
            5037: [],
            5038: [],
        },
        "warn": {
            3053: [81, 82, 259, 260],
            3063: [],
            3066: [],
            4017: [123],
            4023: [],
            5036: [],
        }
    }
}

AC_charger_faults = {
    "3000": [],
    "3001": [],
    "3002": [],
    "3003": [],
    "3004": [],
    "3005": [],
    "3006": [],
    "3007": [],
    "3008": [],
    "3009": [],
    "3010": [],
    "3011": [],
    "3012": [],
    "3013": [],
    "3014": [],
    "3015": [],
    "3016": [],
    "3017": [],
    "3018": [],
    "3019": [],
    "3020": [],
    "3021": [],
    "3022": [],
    "3023": [],
    "3024": [],
    "3025": [],
    "3026": [],
    "3027": [],
    "3028": [],
    "3029": []
}  # 交流设备异常
AC_charger_power_faults = {
    "4000": [],
    "4001": [],
    "4002": [],
    "4003": [],
    "4004": [],
    "4005": [],
    "4006": [],
    "4007": []
}  # 交流电源异常
AC_charger_car_faults = {
    "5000": []
}  # 交流车辆异常

DC_charger_faults = {
    "3030": [],
    "3031": [47],
    "3032": [16, 72],
    "3033": [15, 71],
    "3034": [21, 75],
    "3035": [400],
    "3036": [261],
    "3037": [],
    "3038": [31, 102, 103, 104, 406, 445],
    "3039": [],
    "3040": [30, 407, 409],
    "3041": [32],
    "3042": [39, 167],
    "3043": [58, 91],
    "3044": [45],
    "3045": [99],
    "3046": [100, 101],
    "3047": [108],
    "3048": [],
    "3049": [95],
    "3050": [152, 153, 154, 156, 157, 158, 159, 166, 604, 605],
    "3051": [94, 606, 607],
    "3052": [80, 258],
    "3053": [81, 82, 259, 260],
    "3054": [19, 76, 77, 78, 79],
    "3055": [110, 501],
    "3056": [22, 40, 92, 93, 446],
    "3057": [],
    "3058": [],
    "3059": [],
    "3060": [],
    "3061": [],
    "3062": [25, 26, 27],
    "3063": [],
    "3064": [],
    "3065": [96, 97, 98, 506, 507, 508],
    "3066": [],
    "3067": [],
    "3068": [],
    "3069": [165],
    "3070": [601, 603],
    "3071": [602, 610, 611],
    "3072": [168],
    "3073": [28, 29, 440, 441, 442, 443, 444, 447, 448, 449, 450, 451, 452, 453, 454, 455, 456, 457],
    "3074": [],
    "3075": [],
    "3076": [],
    "3077": [],
    "3078": [],
    "3079": [],
    "3080": [],
    "3081": [],
    "3082": [55],
    "3083": [],
    "3084": [17, 73],
    "3085": [41, 74],
    "3086": [46]
}  # 直流设备异常
DC_charger_power_faults = {
    "4008": [42, 43, 112, 121, 122, 124, 125, 126, 401, 402],
    "4009": [131, 132, 133, 403],
    "4010": [135, 136, 405],
    "4011": [134, 404],
    "4012": [138, 408],
    "4013": [18, 105],
    "4014": [],
    "4015": [],
    "4016": [],
    "4017": [123],
    "4018": [111, 502],
    "4019": [],
    "4020": [],
    "4021": [],
    "4022": [],
    "4023": []
}  # 直流电源异常
DC_charger_car_faults = {
    "5001": [],
    "5002": [187],
    "5003": [192, 193],
    "5004": [202],
    "5005": [197],
    "5006": [224],
    "5007": [243],
    "5008": [56, 209],
    "5009": [237],
    "5010": [],
    "5011": [184],
    "5012": [246, 249, 250, 251, 252, 253, 254, 255, 256],
    "5013": [],
    "5014": [155, 232],
    "5015": [233, 234],
    "5016": [],
    "5017": [],
    "5018": [231, 239, 242, 257],
    "5019": [213],
    "5020": [214],
    "5021": [215],
    "5022": [216],
    "5023": [217],
    "5024": [218, 236],
    "5025": [219],
    "5026": [220, 235],
    "5027": [],
    "5028": [],
    "5029": [238, 241],
    "5030": [],
    "5031": [],
    "5032": [],
    "5033": [],
    "5034": [240],
    "5035": [],
    "5036": [],
    "5037": [],
    "5038": []
}  # 直流车辆异常


def hex_to_ascii(hex_str):
    bytes_object = bytes.fromhex(hex_str)  # 将十六进制字符串转换为字节对象
    return bytes_object.decode("ASCII")  # 解码为ASCII字符串


def workstatus(status_hex, bat_hex):
    if status_hex == 1 and bat_hex == 0:
        return 10
    if status_hex == 1 and bat_hex == 1:
        return 11
    if 6 > status_hex > 1 == bat_hex:
        return 12
    if 9 > status_hex > 6 and bat_hex == 1:
        return 14
    if status_hex == 10:
        return 15
    if status_hex == 9:
        return 16


def gunStatus(gunStatus):
    if gunStatus == 1:
        return 10
    if gunStatus == 0:
        return 11


def get_formatted_date():
    global Manufacture_Date
    current_time = datetime.now()
    Manufacture_Date = current_time.strftime("%y%m%d")
    return Manufacture_Date


def generate_unique_code():
    result = get_DeviceInfo("Serial_Number")
    if result:
        return result
    else:
        formatted_date = int(time.time())
        code = str(formatted_date)[-4:]
        save_DeviceInfo("Serial_Number", 1, str(code), 0)
        save_DeviceInfo("formatted_date", 1, str(formatted_date), 0)
        return code


def set_deviceCode():
    code = str(str(Vendor_Code) + get_formatted_date() + device_type.get("DC") + generate_unique_code())
    save_DeviceInfo("deviceCode", 1, str(code), 0)
    return code


def set_link_init_status(value):
    global link_init_status
    link_init_status = value
    return link_init_status


def get_link_init_status():
    global link_init_status
    return link_init_status


def get_ip_from_resolv():
    if os.path.getsize("/etc/resolv.conf") == 0:
        with open("/etc/resolv.conf", 'a') as file:
            file.write("nameserver 8.8.8.8\n")
        return "10.111.186.1"
    else:
        with open("/etc/resolv.conf", 'r') as file:
            lines = file.readlines()
            # 提取最后一行中的 IP 地址
            for line in lines:
                if line.startswith("nameserver"):
                    return "10.111.186.1"
    return "10.111.186.1"


def ping_ip(IP):
    ping_process = subprocess.Popen(
        ['ping', '-c', '4', IP],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    ping_output, ping_error = ping_process.communicate()
    return ping_output.decode('utf-8'), ping_process.returncode


def parse_ping_output(output):
    try:
        loss_match = re.search(r'(\d+)% packet loss', output)
        rtt_match = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/[\d.]+ ms', output)

        if loss_match:
            packet_loss = int(loss_match.group(1))
        else:
            packet_loss = 100  # 如果没有找到丢包率信息，则认为是100%丢包

        if rtt_match:
            average_latency = float(rtt_match.group(1))
        else:
            average_latency = None

        return packet_loss, average_latency
    except Exception as e:
        print(f"Error parsing ping output: {e}")
        return None, None


def calculate_sigval(packet_loss, latency):
    if latency is None:
        return 0

    if packet_loss < 100:
        # 假设 500ms 为最高延迟，计算 sigVal
        sigVal = int((1 - min(latency / 500, 1)) * 32)
        return sigVal
    else:
        return 0


def get_net():
    global net_status
    IP = get_ip_from_resolv()
    ping_output, return_code = ping_ip(IP)
    platform_data["netId"] = 14
    try:
        if return_code == 0:
            try:
                packet_loss, average_latency = parse_ping_output(ping_output)
                # 检查丢包率
                if packet_loss is not None and average_latency is not None:
                    if packet_loss <= 90:
                        platform_data["sigVal"] = calculate_sigval(packet_loss, average_latency)
                        net_status = 1
                    else:
                        platform_data["sigVal"] = calculate_sigval(packet_loss, average_latency)
                        net_status = 0
            except Exception as e:
                print(f"Error calculating sigVal: {e}")
                return 0
        else:
            platform_data["sigVal"] = 0
            net_status = 0
    except Exception as e:
        print("\033[91m" + f"{e} .{inspect.currentframe().f_lineno}" + "\033[0m")
        HSyslog.log_info(f"get_net: {return_code} . {ping_output} .{e} .{inspect.currentframe().f_lineno}")

    try:
        # 获取网络接口信息
        ifconfig_process = subprocess.Popen(['ifconfig'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ifconfig_output, _ = ifconfig_process.communicate()
        # 检查网络接口类型
        if 'wlan' in str(ifconfig_output):
            platform_data["netType"] = 16
        elif 'eth' in str(ifconfig_output):
            platform_data["netType"] = 17
        elif 'ppp0' in str(ifconfig_output):
            platform_data["netType"] = 13
        else:
            platform_data["netType"] = 10
    except Exception as e:
        print("\033[91m" + f"{e} .{inspect.currentframe().f_lineno}" + "\033[0m")
        HSyslog.log_info(f"get_net: {return_code} . {ping_output} .{e} .{inspect.currentframe().f_lineno}")


def get_ping():
    IP = get_ip_from_resolv()
    ping_output, return_code = ping_ip(IP)
    if return_code == 0:
        try:
            packet_loss, average_latency = parse_ping_output(ping_output)
            if packet_loss is not None and average_latency is not None:
                if packet_loss <= 100:
                    return 1
                else:
                    return 0
        except Exception as e:
            HSyslog.log_info(f"Error calculating sigVal: {e}")
            return 0
    else:
        return 0


def disable_network_interface(interface):
    command = f"sudo ifconfig {interface} down"
    subprocess.run(command, shell=True, check=True, capture_output=True, text=True)


# 调用函数禁用 eth0 接口
disable_network_interface("eth0")


def get_mac_address(interface):
    try:
        mac_bytes = get_DeviceInfo("mac_bytes")
        if mac_bytes is None:
            mac_bytes = open(f"/sys/class/net/{interface}/address").read().strip()
            save_DeviceInfo("mac_bytes", 1, mac_bytes, 0)
        # mac = ":".join([mac_bytes[i:i+2] for i in range(0, 12, 2)])
        return mac_bytes
    except FileNotFoundError:
        return None


def set_property_status(info: int):
    global property_status
    property_status = info


def get_property_status():
    global property_status
    return property_status


def set_flaut_status(info: int):
    global flaut_status
    flaut_status = info


def get_flaut_status():
    global flaut_status
    return flaut_status


def stop_reason(code: int):
    for device_type, device_data in flaut_warning_type.items():  # device_type:device
        for flaut_type, flaut_data in device_data.items():  # flaut_type:flaut
            for flaut_id, flaut_list in flaut_data.items():  # flaut_id:1000
                if code in flaut_list:
                    return flaut_id
    return 0000


def charging_num():
    result = get_DeviceInfo('charging_code')
    if result is None:
        save_DeviceInfo("charging_code", 2, "null", 0000)
        charging_code = 0000
    else:
        charging_code = result
    if charging_code == 9999:
        charging_code = 0000
    save_DeviceInfo('charging_code', 2, "null", charging_code + 1)
    return str("{:04}".format(charging_code))


def do_charging_num():
    result = get_DeviceInfo('do_charging_code')
    if result is None:
        save_DeviceInfo("do_charging_code", 2, "null", 00)
        do_charging_code = 00
    else:
        do_charging_code = result
    if do_charging_code == 99:
        do_charging_code = 00
    save_DeviceInfo('do_charging_code', 2, "null", do_charging_code + 1)
    return str("{:02}".format(do_charging_code))


def get_before_last_dot(s):
    last_dot_index = s.rfind('.')
    if last_dot_index == -1:
        return s
    else:
        return [s[:last_dot_index], s[last_dot_index:]]


def get_stop_type(chargeMode):
    if chargeMode == 10:
        return 0x00
    if chargeMode == 11:
        return 0x02
    if chargeMode == 12:
        return 0x01
    if chargeMode == 13:
        return 0x04
    if chargeMode == 14:
        return 0x03


def get_stop_condition(chargeMode, limitData):
    if chargeMode == 10:
        return 0
    if chargeMode == 11:
        return limitData * 1000
    if chargeMode == 12:
        return limitData * 1000
    if chargeMode == 13:
        return limitData
    if chargeMode == 14:
        return limitData * 60


def get_start_source(startType):
    if startType == 10:
        return 0x01
    if startType == 11:
        return 0x07
    if startType == 12:
        return 0x3F
    if startType == 13:
        return 0x01
    if startType == 14:
        return 0x0A
    if startType == 15:
        return 0x03


def dec_str_to_bcd_compressed(number_str):
    number_str = number_str.lstrip('0')
    bcd_compressed = ''
    for digit in number_str:
        bcd = format(int(digit), '04b')
        bcd_compressed += bcd
    return bcd_compressed


def date_to_time(date_str):
    current_year = datetime.now().year
    full_date_str = f"{current_year} {date_str}"
    date_obj = datetime.strptime(full_date_str, '%Y %b %d %H:%M:%S')
    timestamp = date_obj.timestamp()
    return timestamp


def get_current_time_hhmm():
    current_time = datetime.now()
    hhmm_format = current_time.strftime('%H%M')
    return hhmm_format


def datadb_init():
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS VerInfoEvt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER,
            device_type INTEGER,
            hard_version TEXT,
            soft_version TEXT,
            ota_version TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS DeviceInfo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_id TEXT,
            data_type INTEGER,
            data_str TEXT,
            data_int INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS FeeModel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            SegFlag INTEGER,
            TimeNum INTEGER,
            TimeSeg TEXT,
            chargeFee INTEGER,
            serviceFee INTEGER
        )
    ''')
    cur.execute('''
            CREATE TABLE IF NOT EXISTS dcOutMeterIty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gunNo INTEGER,
                acqTime TEXT,
                mailAddr TEXT,
                meterNo TEXT,
                assetId TEXT,
                sumMeter INTEGER,
                elec INTEGER,
                lastTrade TEXT
            )
        ''')
    cur.execute('''
            CREATE TABLE IF NOT EXISTS dcBmsRunIty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gunNo INTEGER,
                preTradeNo TEXT,
                tradeNo TEXT,
                socVal INTEGER,
                BMSVer INTEGER,
                BMSMaxVol INTEGER,
                batType INTEGER,
                batRatedCap INTEGER,
                batRatedTotalVol INTEGER,
                singlBatMaxAllowVol INTEGER,
                maxAllowCur INTEGER,
                battotalEnergy INTEGER,
                maxVol INTEGER,
                maxTemp INTEGER,
                batCurVol INTEGER,
                get_time INTEGER
            )
        ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS DeviceOrder (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gunNo INTEGER,
            preTradeNo TEXT,
            tradeNo TEXT,
            vinCode TEXT,
            timeDivType INTEGER,
            chargeStartTime INTEGER,
            chargeEndTime INTEGER,
            startSoc INTEGER,
            endSoc INTEGER,
            reason INTEGER,
            eleModelId TEXT,
            serModelId TEXT,
            sumStart INTEGER,
            sumEnd INTEGER,
            totalElect INTEGER,
            sharpElect INTEGER,
            peakElect INTEGER,
            flatElect INTEGER,
            valleyElect INTEGER,
            totalPowerCost INTEGER,
            totalServCost INTEGER,
            sharpPowerCost INTEGER,
            peakPowerCost INTEGER,
            flatPowerCost INTEGER,
            valleyPowerCost INTEGER,
            sharpServCost INTEGER,
            peakServCost INTEGER,
            flatServCost INTEGER,
            valleyServCost INTEGER,
            device_session_id TEXT
        )
    ''')

    conn.commit()
    conn.close()


def save_DeviceInfo(data_id, data_type, data_str, data_int):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    if get_DeviceInfo(data_id) is None:
        cur.execute('''INSERT INTO DeviceInfo (data_id, data_type, data_str, data_int) VALUES (?, ?, ?, ?)''',
                    (data_id, data_type, data_str, data_int))
    else:
        cur.execute('''UPDATE DeviceInfo SET data_type = ?, data_str = ?, data_int = ? WHERE data_id = ?''',
                    (data_type, data_str, data_int, data_id))
    conn.commit()
    conn.close()


def get_DeviceInfo(data_id):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM DeviceInfo WHERE data_id = ?', (data_id,))
    result = cur.fetchone()
    conn.commit()
    conn.close()
    if not result:
        return None
    else:
        if result[2] == 1:
            return result[3]
        if result[2] == 2:
            return result[4]


def save_VerInfoEvt(device_id, device_type, hard_version, soft_version, dtu_ota_version):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    if get_VerInfoEvt(device_type)[0] is None:
        cur.execute(
            '''INSERT INTO VerInfoEvt (device_id, device_type, hard_version, soft_version, ota_version) VALUES (?, ?, ?, ?, ?)''',
            (device_id, device_type, hard_version, soft_version, dtu_ota_version))
    else:
        cur.execute(
            '''UPDATE VerInfoEvt SET device_id = ?, hard_version = ?, soft_version = ?, ota_version = ? WHERE device_type = ?''',
            (device_id, hard_version, soft_version, dtu_ota_version, device_type))
    conn.commit()
    conn.close()


def get_VerInfoEvt(device_type):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM VerInfoEvt WHERE device_type = ?', (device_type,))
    result = cur.fetchone()
    conn.commit()
    conn.close()
    if not result:
        return None, None
    else:
        return result[4] + result[5], result[3]


def save_FeeModel(dict_info):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    TimeNum = dict_info.get("TimeNum")
    SegFlag = dict_info.get("SegFlag")
    TimeSeg = dict_info.get("TimeSeg")
    chargeFee = dict_info.get("chargeFee")
    serviceFee = dict_info.get("serviceFee")
    cur.execute('DELETE FROM FeeModel')
    for i in range(0, TimeNum):
        cur.execute(
            '''INSERT INTO FeeModel (SegFlag, TimeNum, TimeSeg, chargeFee, serviceFee) VALUES (?, ?, ?, ?, ?)''',
            (SegFlag[i], TimeNum, TimeSeg[i], chargeFee[SegFlag[i] - 10], serviceFee[SegFlag[i] - 10]))
    conn.commit()
    conn.close()


def get_FeeModel():
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM FeeModel')
    result = cur.fetchone()
    conn.commit()
    conn.close()
    return result


def save_DeviceOrder(dict_order: dict):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    if get_DeviceOrder(dict_order.get("device_session_id")) is None:
        cur.execute(
            '''INSERT INTO DeviceOrder (gunNo, preTradeNo, tradeNo, vinCode, timeDivType, chargeStartTime, 
            chargeEndTime, startSoc, endSoc, reason, eleModelId, serModelId, sumStart, sumEnd, totalElect, sharpElect, 
            peakElect, flatElect, valleyElect, totalPowerCost, totalServCost, sharpPowerCost, peakPowerCost, flatPowerCost, 
            valleyPowerCost, sharpServCost, peakServCost, flatServCost, valleyServCost, device_session_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (dict_order.get("gunNo"), dict_order.get("preTradeNo"), dict_order.get("tradeNo"),
             dict_order.get("vinCode"), dict_order.get("timeDivType"), dict_order.get("chargeStartTime"),
             dict_order.get("chargeEndTime"), dict_order.get("startSoc"), dict_order.get("endSoc"),
             dict_order.get("reason"), dict_order.get("eleModelId"), dict_order.get("serModelId"),
             dict_order.get("sumStart"), dict_order.get("sumEnd"), dict_order.get("totalElect"),
             dict_order.get("sharpElect"), dict_order.get("peakElect"), dict_order.get("flatElect"),
             dict_order.get("valleyElect"), dict_order.get("totalPowerCost"), dict_order.get("totalServCost"),
             dict_order.get("sharpPowerCost"), dict_order.get("peakPowerCost"), dict_order.get("flatPowerCost"),
             dict_order.get("valleyPowerCost"), dict_order.get("sharpServCost"), dict_order.get("peakServCost"),
             dict_order.get("flatServCost"), dict_order.get("valleyServCost"), dict_order.get("device_session_id")))
    else:
        cur.execute(
            '''UPDATE DeviceOrder SET gunNo = ?, preTradeNo = ?, tradeNo = ?, vinCode = ?, timeDivType = ?, 
            chargeStartTime = ?, chargeEndTime = ?, startSoc = ?, endSoc = ?, reason = ?, eleModelId = ?, 
            serModelId = ?, sumStart = ?, sumEnd = ?, totalElect = ?, sharpElect = ?, peakElect = ?, flatElect = ?, 
            valleyElect = ?, totalPowerCost = ?, totalServCost = ?, sharpPowerCost = ?, peakPowerCost = ?, 
            flatPowerCost = ?, valleyPowerCost = ?, sharpServCost = ?, peakServCost = ?, flatServCost = ?, 
            valleyServCost = ? WHERE device_session_id = ? ''',
            (dict_order.get("gunNo"), dict_order.get("preTradeNo"), dict_order.get("tradeNo"),
             dict_order.get("vinCode"), dict_order.get("timeDivType"), dict_order.get("chargeStartTime"),
             dict_order.get("chargeEndTime"), dict_order.get("startSoc"), dict_order.get("endSoc"),
             dict_order.get("reason"), dict_order.get("eleModelId"), dict_order.get("serModelId"),
             dict_order.get("sumStart"), dict_order.get("sumEnd"), dict_order.get("totalElect"),
             dict_order.get("sharpElect"), dict_order.get("peakElect"), dict_order.get("flatElect"),
             dict_order.get("valleyElect"), dict_order.get("totalPowerCost"), dict_order.get("totalServCost"),
             dict_order.get("sharpPowerCost"), dict_order.get("peakPowerCost"), dict_order.get("flatPowerCost"),
             dict_order.get("valleyPowerCost"), dict_order.get("sharpServCost"), dict_order.get("peakServCost"),
             dict_order.get("flatServCost"), dict_order.get("valleyServCost"), dict_order.get("device_session_id")
             ))
    conn.commit()
    conn.close()


def get_DeviceOrder(device_session_id):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM DeviceOrder WHERE device_session_id = ?', (device_session_id,))
    result = cur.fetchone()
    conn.commit()
    conn.close()
    return result


def get_DeviceOrder_tradeNo(tradeNo):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM DeviceOrder WHERE tradeNo = ?', (tradeNo,))
    result = cur.fetchone()
    conn.commit()
    conn.close()
    if result is None:
        return ""
    else:
        return result[30]


def get_DeviceOrder_preTradeNo(preTradeNo):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM DeviceOrder WHERE preTradeNo = ?', (preTradeNo,))
    result = cur.fetchone()
    conn.commit()
    conn.close()
    if result is None:
        return ""
    else:
        return result[30]


def get_last_DeviceOrder():
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM DeviceOrder ORDER BY id DESC LIMIT 1')
    result = cur.fetchone()
    conn.commit()
    conn.close()
    return result[2]


def get_log_DeviceOrder(startDate, stopDate):
    DeviceOrder = []
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM DeviceOrder')
    result = cur.fetchall()
    for info in result:
        if int(info[6]) >= int(startDate) or int(info[7]) <= int(stopDate):
            DeviceOrder.append(info)
    conn.commit()
    conn.close()
    return DeviceOrder


def save_dcOutMeterIty(dict_info: dict):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    gunNo = dict_info.get("gunNo")
    acqTime = dict_info.get("acqTime")
    mailAddr = dict_info.get("mailAddr")
    meterNo = dict_info.get("meterNo")
    assetId = dict_info.get("assetId")
    sumMeter = dict_info.get("sumMeter")
    lastTrade = dict_info.get("lastTrade")
    elec = dict_info.get("elec")
    cur.execute(
        '''INSERT INTO dcOutMeterIty (gunNo, acqTime, mailAddr, meterNo, assetId, sumMeter, elec, lastTrade) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (gunNo, acqTime, mailAddr, meterNo, assetId, sumMeter, elec, lastTrade))
    conn.commit()
    conn.close()


def get_log_dcOutMeterIty(startDate, stopDate):
    dcOutMeterIty = []
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM dcOutMeterIty')
    result = cur.fetchall()
    for info in result:
        if int(startDate) <= int(datetime.strptime(info[2], '%Y%m%d%H%M%S').timestamp()) <= int(stopDate):
            dcOutMeterIty.append(info)
    conn.commit()
    conn.close()
    return dcOutMeterIty


def save_dcBmsRunIty(dict_info: dict):
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    get_time = int(time.time())
    gunNo = dict_info.get("gunNo")
    preTradeNo = dict_info.get("preTradeNo")
    tradeNo = dict_info.get("tradeNo")
    socVal = dict_info.get("socVal")
    BMSVer = dict_info.get("BMSVer")
    BMSMaxVol = dict_info.get("BMSMaxVol")
    batType = dict_info.get("batType")
    batRatedCap = dict_info.get("batRatedCap")
    batRatedTotalVol = dict_info.get("batRatedTotalVol")
    singlBatMaxAllowVol = dict_info.get("singlBatMaxAllowVol")
    maxAllowCur = dict_info.get("maxAllowCur")
    battotalEnergy = dict_info.get("battotalEnergy")
    maxVol = dict_info.get("maxVol")
    maxTemp = dict_info.get("maxTemp")
    batCurVol = dict_info.get("batCurVol")
    cur.execute(
        '''INSERT INTO dcBmsRunIty (gunNo, preTradeNo, tradeNo, socVal, BMSVer, BMSMaxVol, batType, batRatedCap, batRatedTotalVol, 
         singlBatMaxAllowVol, maxAllowCur, battotalEnergy, maxVol, maxTemp, batCurVol, get_time) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (gunNo, preTradeNo, tradeNo, socVal, BMSVer, BMSMaxVol, batType, batRatedCap, batRatedTotalVol,
         singlBatMaxAllowVol, maxAllowCur, battotalEnergy, maxVol, maxTemp, batCurVol, get_time))
    conn.commit()
    conn.close()


def get_log_dcBmsRunIty(startDate, stopDate):
    dcBmsRunIty = []
    conn = sqlite3.connect(data_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM dcBmsRunIty')
    result = cur.fetchall()
    for info in result:
        if int(startDate) <= int(info[16]) <= int(stopDate):
            dcBmsRunIty.append(info)
    conn.commit()
    conn.close()
    return dcBmsRunIty
