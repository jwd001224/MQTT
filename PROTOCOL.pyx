# cython: profile=False
import io
import json

from cpython cimport PyUnicode_AsUTF8String
from cpython.bytes cimport PyBytes_AS_STRING

import HSyslog
from PROTOCOL cimport *

from time import sleep
from HSyslog import *
from tools import *

cdef str red_char = "\033[91m"
cdef str green_char = "\033[92m"
cdef str init_char = "\033[0m"

cdef int onlink_status = 0
cdef int charger_status = 0
cdef object set_lock = threading.Lock()

cdef str productKey = ""
cdef str deviceSecret = ""
cdef str deviceName = ""

cdef object callback_query_log = None
cdef object callback_dev_maintain = None
cdef object callback_lockCtrl = None
cdef object callback_issue_feeModel = None
cdef object callback_startCharge = None
cdef object callback_authCharge = None
cdef object callback_stopCharge = None
cdef object callback_rsvCharge = None
cdef object callback_confirmTrade = None
cdef object callback_groundLock_ctrl = None
cdef object callback_gateLock_ctrl = None
cdef object callback_orderCharge = None
cdef object callback_get_config = None
cdef object callback_update_config = None
cdef object callback_ota_update = None
cdef object callback_time_sync = None
cdef object callback_state_ever = None
cdef object callback_connectSucc = None
cdef object callback_disConnected = None
cdef object callback_reportReply = None
cdef object callback_trigEvevtReply = None
cdef object callback_certGet = None
cdef object callback_certSet = None
cdef object callback_deregCodeGet = None
cdef object callback_uidGet = None
cdef object callback_mainres = None

cdef iot_linkkit_new(evs_is_ready, is_device_uid):
    cdef int result = evs_linkkit_new(evs_is_ready, is_device_uid)
    if result == 0:
        print(green_char + f"The Device Create Successfully" + init_char)
        HSyslog.log_info("The Device Create Successfully")
        return 0
    if result == -1:
        print(green_char + f"The Device Not Ready" + init_char)
        HSyslog.log_info("The Device Not Ready")
        return -1
    if result == -2:
        print(green_char + f"Failed To Get Device Registration Code" + init_char)
        HSyslog.log_info("Failed To Get Device Registration Code")
        return -2
    if result == -3:
        print(green_char + f"Failed To Set Device Certificate" + init_char)
        HSyslog.log_info("Failed To Set Device Certificate")
        return -3

cdef iot_linkkit_time_sync():
    cdef int result = evs_linkkit_time_sync()
    if result == 0:
        print(green_char + f"Time Sync Successfully" + init_char)
        HSyslog.log_info("Time Sync Successfully")
        return True
    elif result < 0:
        print(green_char + f"Time Sync Failed" + init_char)
        HSyslog.log_info("Time Sync Failed")
        return False

def iot_linkkit_fota(buffer, buffer_len):
    cdef int result
    try:
        result = evs_linkkit_fota(buffer, buffer_len)
        if result == 0:
            print(green_char + f"OTA Get Successfully" + init_char)
            HSyslog.log_info("OTA Get Successfully")
            try:
                if not os.path.exists("/opt/hhd/dtu20.tar.gz"):
                    with open("/opt/hhd/dtu20.tar.gz", 'wb') as file:
                        file.seek((8 * 1024 * 1024) - 1)
                        file.write(b'\0')

                with open("/opt/hhd/dtu20.tar.gz", 'wb') as file:
                    file.write(buffer)
                callback_ota_update("suss")
                return 0
            except Exception as e:
                print(green_char + f"OTA Write Failed .{e}" + init_char)
                HSyslog.log_info(f"OTA Write Failed .{e}")
                return -1
        elif result < 0:
            print(green_char + f"OTA Get Failed" + init_char)
            HSyslog.log_info("OTA Get Failed")
            return -1
    except Exception as e:
        print(green_char + f"iot_linkkit_fota" + init_char)
        HSyslog.log_info("iot_linkkit_fota")
        return -1

def iot_linkkit_free():
    cdef int result = evs_linkkit_free()
    if result == 0:
        print(green_char + f"Free Successfully" + init_char)
        HSyslog.log_info("Free Successfully")
        return True
    elif result < 0:
        print(red_char + f"Free Failed" + init_char)
        HSyslog.log_info("Free Failed")

def iot_mainloop():
    cdef int result = evs_mainloop()
    if result == 0:
        # print(green_char + f"Device Linkkit Successful" + init_char)
        return 0
    if result == -1:
        print(red_char + f"Device Linkkit Failed To Open" + init_char)
        HSyslog.log_info("Device Linkkit Failed To Open")
        return -1
    if result == -2:
        print(red_char + f"Device Linkkit Turn On Retry Wait" + init_char)
        HSyslog.log_info("Device Linkkit Turn On Retry Wait")
        return -2
    if result == -3:
        print(red_char + f"Device Linkkit Connection Failed" + init_char)
        HSyslog.log_info("Device Linkkit Connection Failed")
        return -3
    if result == -4:
        print(red_char + f"Device Linkkit Connection Retry Waits" + init_char)
        HSyslog.log_info("Device Linkkit Connection Retry Waits")
        return -4

def iot_linkkit_init(info_json: str):
    set_device_meta(info_json)
    return 0

def iot_link_connect(evs_is_ready: int, is_device_uid: int):
    iot_evs_registercallback()
    cdef result = iot_linkkit_new(evs_is_ready, is_device_uid)
    if result < 0:
        return -1
    return 0

def set_version(version:str):
    cdef int result
    try:
        new_version = str_to_char(version)
        result = set_firmwareVersion(new_version)
        if result == 0:
            HSyslog.log_info(f"ota update version successful: {version}")
    except Exception as e:
        print(red_char + f"ota update version Failed .{e}" + init_char)
        HSyslog.log_info("ota update version Failed")
        return -1

def get_otaprogress(progress:int):
    cdef int result
    try:
        result = get_firmwareprogress(progress)
        if result == 1:
            HSyslog.log_info(f"ota update progress : {progress}")
    except Exception as e:
        print(red_char + f"ota update progress error .{e}" + init_char)
        HSyslog.log_info("ota update progress error")
        return -1

def iot_send_event(event_type: int, event_struct: str):
    try:
        if event_type == 0:
            set_event_fireware_info(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_fireware_info: {event_fireware_info}")
            res = evs_send_event(EVS_CMD_EVENT_FIREWARE_INFO, &event_fireware_info)  # 固件信息上报
            return res
        if event_type == 1:
            set_event_ask_feeModel(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_ask_feeModel: {event_ask_feeModel}")
            res = evs_send_event(EVS_CMD_EVENT_ASK_FEEMODEL, &event_ask_feeModel)  # 费率请求
            return res
        if event_type == 2:
            set_event_startCharge(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_startCharge: {event_startCharge}")
            res = evs_send_event(EVS_CMD_EVENT_STARTCHARGE, &event_startCharge)  # 充电启动鉴权
            return res
        if event_type == 3:
            set_event_startResult(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_startResult: {event_startResult}")
            res = evs_send_event(EVS_CMD_EVENT_STARTRESULT, &event_startResult)  # 充电启动结果
            return res
        if event_type == 4:
            set_event_stopCharge(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_stopCharge: {event_stopCharge}")
            res = evs_send_event(EVS_CMD_EVENT_STOPCHARGE, &event_stopCharge)  # 停止充电结果
            return res
        if event_type == 5:
            set_event_tradeInfo(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_tradeInfo: {event_tradeInfo}")
            res = evs_send_event(EVS_CMD_EVENT_TRADEINFO, &event_tradeInfo)  # 交易记录
            return res
        if event_type == 6:
            set_event_alarm(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_alarm: {event_alarm}")
            res = evs_send_event(EVS_CMD_EVENT_ALARM, &event_alarm)  # 故障告警信息
            return res
        if event_type == 7:
            set_event_pile_stutus_change(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_pile_stutus_change: {event_pile_stutus_change}")
            res = evs_send_event(EVS_CMD_EVENT_ACPILE_CHANGE, &event_pile_stutus_change)  # 枪状态信息(AC)
            return res
        if event_type == 8:
            set_event_pile_stutus_change(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_pile_stutus_change: {event_pile_stutus_change}")
            res = evs_send_event(EVS_CMD_EVENT_DCPILE_CHANGE, &event_pile_stutus_change)  # 枪状态信息
            return res
        if event_type == 9:
            set_event_groundLock_change(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_groundLock_change: {event_groundLock_change}")
            res = evs_send_event(EVS_CMD_EVENT_GROUNDLOCK_CHANGE, &event_groundLock_change)  # 地锁状态
            return res
        if event_type == 10:
            set_event_gateLock_change(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_gateLock_change: {event_gateLock_change}")
            res = evs_send_event(EVS_CMD_EVENT_GATELOCK_CHANGE, &event_gateLock_change)  # 门锁状态
            return res
        if event_type == 11:
            set_event_dev_config(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_dev_config: {event_dev_config}")
            res = evs_send_event(EVS_CMD_EVENT_ASK_DEV_CONFIG, &event_dev_config)  # 固件信息
            return res
        if event_type == 12:
            set_event_car_info(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_car_info: {event_car_info}")
            res = evs_send_event(EVS_CMD_EVENT_CAR_INFO, &event_car_info)  # 车辆信息(AC)
            return res
        if event_type == 13:
            set_event_ver_info(event_struct)
            HSyslog.log_info(f"Send_Event_to_Platform_ver_info: {event_ver_info}")
            res = evs_send_event(EVS_CMD_EVENT_VER_INFO, &event_ver_info)  # 版本信息上传
            return res
        if event_type == 14:
            set_event_logQuery_Result(event_struct)
            res = evs_send_event(EVS_CMD_EVENT_LOGQUERY_RESULT, &event_logQuery_Result)  # 日志查询结果
            return res

    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"data_input_id: {event_type}, data_input---dict_data: {event_struct}" + init_char)
        HSyslog.log_info(red_char + f"Send_Event_to_Platform_Failed: {event_struct} ... {e}" + init_char)
        return -1

def iot_send_property(event_type: int, event_struct: str):
    if event_type == 15:
        set_property_dcPile(event_struct)
        evs_send_property(EVS_CMD_PROPERTY_DCPILE, &property_dcPile)
        HSyslog.log_info(f"Send_Property_to_Platform_dcPile: {property_dcPile}")
    if event_type == 16:
        set_property_dc_work(event_struct)
        evs_send_property(EVS_CMD_PROPERTY_DC_WORK, &property_dc_work)
        HSyslog.log_info(f"Send_Property_to_Platform_dc_work: {property_dc_work}")
    if event_type == 17:
        set_property_dc_nonWork(event_struct)
        evs_send_property(EVS_CMD_PROPERTY_DC_NONWORK, &property_dc_nonWork)
        HSyslog.log_info(f"Send_Property_to_Platform_dc_nonWork: {property_dc_nonWork}")
    if event_type == 18:
        set_property_meter(event_struct)
        evs_send_property(EVS_CMD_PROPERTY_DC_OUTMETER, &property_meter)
        HSyslog.log_info(f"Send_Property_to_Platform_meter: {property_meter}")
    if event_type == 19:
        set_property_BMS(event_struct)
        evs_send_property(EVS_CMD_PROPERTY_BMS, &property_BMS)
        HSyslog.log_info(f"Send_Property_to_Platform_BMS: {property_BMS}")
    if event_type == 20:
        set_property_dc_input_meter(event_struct)
        evs_send_property(EVS_CMD_PROPERTY_DC_INPUT_METER, &property_dc_input_meter)
        HSyslog.log_info(f"Send_Property_to_Platform_dc_input_meter: {property_dc_input_meter}")

def server_callback(server:int, func):
    if server == 2:
        global callback_query_log
        callback_query_log = func
    if server == 3:
        global callback_dev_maintain
        callback_dev_maintain = func
    if server == 4:
        global callback_lockCtrl
        callback_lockCtrl = func
    if server == 5:
        global callback_issue_feeModel
        callback_issue_feeModel = func
    if server == 6:
        global callback_startCharge
        callback_startCharge = func
    if server == 7:
        global callback_authCharge
        callback_authCharge = func
    if server == 8:
        global callback_stopCharge
        callback_stopCharge = func
    if server == 10:
        global callback_rsvCharge
        callback_rsvCharge = func
    if server == 9:
        global callback_confirmTrade
        callback_confirmTrade = func
    if server == 11:
        global callback_groundLock_ctrl
        callback_groundLock_ctrl = func
    if server == 12:
        global callback_gateLock_ctrl
        callback_gateLock_ctrl = func
    if server == 13:
        global callback_orderCharge
        callback_orderCharge = func
    if server == 0:
        global callback_get_config
        callback_get_config = func
    if server == 1:
        global callback_update_config
        callback_update_config = func
    if server == 25:
        global callback_ota_update
        callback_ota_update = func
    if server == 24:
        global callback_time_sync
        callback_time_sync = func
    if server == 15:
        global callback_state_ever
        callback_state_ever = func
    if server == 16:
        global callback_connectSucc
        callback_connectSucc = func
    if server == 17:
        global callback_disConnected
        callback_disConnected = func
    if server == 18:
        global callback_reportReply
        callback_reportReply = func
    if server == 19:
        global callback_trigEvevtReply
        callback_trigEvevtReply = func
    if server == 20:
        global callback_certGet
        callback_certGet = func
    if server == 21:
        global callback_certSet
        callback_certSet = func
    if server == 22:
        global callback_deregCodeGet
        callback_deregCodeGet = func
    if server == 23:
        global callback_uidGet
        callback_uidGet = func
    if server == 14:
        global callback_mainres
        callback_mainres = func

def iot_evs_registercallback():
    EVS_RegisterCallback(EVS_QUE_DATA_SRV, &callback_service_query_log)
    EVS_RegisterCallback(EVS_DEV_MAINTAIN_SRV, &callback_service_dev_maintain)
    EVS_RegisterCallback(EVS_CTRL_LOCK_SRV, &callback_service_lockCtrl)
    EVS_RegisterCallback(EVS_FEE_MODEL_UPDATA_SRV, &callback_service_issue_feeModel)
    EVS_RegisterCallback(EVS_START_CHARGE_SRV, &callback_service_startCharge)
    EVS_RegisterCallback(EVS_AUTH_RESULT_SRV, &callback_service_authCharge)
    EVS_RegisterCallback(EVS_STOP_CHARGE_SRV, &callback_service_stopCharge)
    EVS_RegisterCallback(EVS_RSV_CHARGE_SRV, &callback_service_rsvCharge)
    EVS_RegisterCallback(EVS_ORDER_CHECK_SRV, &callback_service_confirmTrade)
    EVS_RegisterCallback(EVS_GROUND_LOCK_SRV, &callback_service_groundLock_ctrl)
    EVS_RegisterCallback(EVS_GATE_LOCK_SRV, &callback_service_gateLock_ctrl)
    EVS_RegisterCallback(EVS_ORDERLY_CHARGE_SRV, &callback_service_orderCharge)
    EVS_RegisterCallback(EVS_CONF_GET_SRV, &callback_service_get_config)
    EVS_RegisterCallback(EVS_CONF_UPDATE_SRV, &callback_service_update_config)
    EVS_RegisterCallback(EVS_OTA_UPDATE, &callback_service_ota_update)
    EVS_RegisterCallback(EVS_TIME_SYNC, &callback_service_time_sync)
    EVS_RegisterCallback(EVS_STATE_EVERYTHING, &callback_service_state_ever)
    EVS_RegisterCallback(EVS_CONNECT_SUCC, &callback_service_connectSucc)
    EVS_RegisterCallback(EVS_DISCONNECTED, &callback_service_disConnected)
    EVS_RegisterCallback(EVS_REPORT_REPLY, &callback_service_reportReply)
    EVS_RegisterCallback(EVS_TRIGGER_EVENT_REPLY, &callback_service_trigEvevtReply)
    EVS_RegisterCallback(EVS_CERT_GET, &callback_service_certGet)
    EVS_RegisterCallback(EVS_CERT_SET, &callback_service_certSet)
    EVS_RegisterCallback(EVS_DEVICE_REG_CODE_GET, &callback_service_deregCodeGet)
    EVS_RegisterCallback(EVS_DEVICE_UID_GET, &callback_service_uidGet)
    EVS_RegisterCallback(EVS_MAINTAIN_RESULT_SRV, &callback_service_mainres)

# [EVS_QUE_DATA_SRV]
cdef int callback_service_query_log(evs_service_query_log *param, evs_service_feedback_query_log *result):
    post_data = {
        "info_id": EVS_QUE_DATA_SRV,
        "gunNo": param.gunNo,
        "startDate": param.startDate,
        "stopDate": param.stopDate,
        "askType": param.askType,
        "logQueryNo": char_to_str(param.logQueryNo)
    }

    try: # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_query_log(json_str)
        if back_data == "":
            print(red_char + f"callback_query_log error" + init_char)
            HSyslog.log_info(f"callback_query_log error")
            return -1
        try:
            if set_service_feedback_query_log(back_data) == -1:
                print(red_char + f"set_service_feedback_query_log error" + init_char)
                HSyslog.log_info(f"set_service_feedback_query_log error")
                return -1
            result.gunNo = service_feedback_query_log.gunNo  # 1	枪号
            result.startDate = service_feedback_query_log.startDate  # 2	查询起始时间
            result.stopDate = service_feedback_query_log.stopDate  # 3	查询终止时间
            result.askType = service_feedback_query_log.askType  # 4	查询类型
            result.result = service_feedback_query_log.result  # 5	响应结果
            result.logQueryNo = service_feedback_query_log.logQueryNo  # 6	查询流水号

            HSyslog.log_info(f"Reply_to_Platform service_query_log: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_query_log: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_query_log: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_query_log: {json_str}" + init_char)
        HSyslog.log_info(f"callback_query_log: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_DEV_MAINTAIN_SRV]
cdef int callback_service_dev_maintain(evs_service_dev_maintain *param, evs_service_feedback_dev_maintain *result):
    post_data = {
        "into_id": EVS_DEV_MAINTAIN_SRV,
        "ctrlType": param.ctrlType
    }

    try: # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_dev_maintain(json_str)
        if back_data == "":
            print(red_char + f"callback_dev_maintain error" + init_char)
            HSyslog.log_info(f"callback_dev_maintain error")
            return -1
        try:
            if set_service_feedback_dev_maintain(back_data) == -1:
                print(red_char + f"set_service_feedback_dev_maintain error" + init_char)
                HSyslog.log_info(f"set_service_feedback_dev_maintain error")
                return -1
            result.ctrlType = service_feedback_dev_maintain.ctrlType  # 1	当前控制类型
            result.reason = service_feedback_dev_maintain.reason  # 2	失败原因

            HSyslog.log_info(f"Reply_to_Platform service_dev_maintain: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_dev_maintain: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_dev_maintain: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_dev_maintain: {json_str}" + init_char)
        HSyslog.log_info(f"callback_dev_maintain: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_CTRL_LOCK_SRV]
cdef int callback_service_lockCtrl(evs_service_lockCtrl *param, evs_service_feedback_lockCtrl *result):
    post_data = {
        "info_id": EVS_CTRL_LOCK_SRV,
        "gunNo": param.gunNo,
        "lockParam": param.lockParam
    }

    try: # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_lockCtrl(json_str)
        if back_data == "":
            print(red_char + f"callback_lockCtrl error" + init_char)
            HSyslog.log_info(f"callback_lockCtrl error")
            return -1
        try:
            if set_service_feedback_lockCtrl(back_data) == -1:
                print(red_char + f"set_service_feedback_lockCtrl error" + init_char)
                HSyslog.log_info(f"set_service_feedback_lockCtrl error")
                return -1
            result.gunNo = service_feedback_lockCtrl.gunNo  # 1	充电枪编号
            result.lockStatus = service_feedback_lockCtrl.lockStatus  # 2	电子锁状态
            result.resCode = service_feedback_lockCtrl.resCode  # 3	结果

            HSyslog.log_info(f"Reply_to_Platform service_lockCtrl: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_lockCtrl: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_lockCtrl: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_lockCtrl: {json_str}" + init_char)
        HSyslog.log_info(f"callback_lockCtrl: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_FEE_MODEL_UPDATA_SRV]
cdef int callback_service_issue_feeModel(evs_service_issue_feeModel *param, evs_service_feedback_feeModel *result):
    post_data_TimeSeg = []
    for i in range(0, param.TimeNum):
        post_data_TimeSeg.append(char_to_str(param.TimeSeg[i]))
    post_data = {
        "info_id": EVS_FEE_MODEL_UPDATA_SRV,
        "eleModelId": char_to_str(param.eleModelId),
        "serModelId": char_to_str(param.serModelId),
        "SegFlag": param.SegFlag,
        "TimeNum": param.TimeNum,
        "chargeFee": param.chargeFee,
        "serviceFee": param.serviceFee,
        "TimeSeg": post_data_TimeSeg,
    }

    try: # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_issue_feeModel(json_str)
        if back_data == "":
            print(red_char + f"callback_issue_feeModel error" + init_char)
            HSyslog.log_info(f"callback_issue_feeModel error")
            return -1
        try:
            if set_service_feedback_feeModel(back_data) == -1:
                print(red_char + f"set_service_feedback_feeModel error" + init_char)
                HSyslog.log_info(f"set_service_feedback_feeModel error")
                return -1
            result.eleModelId = service_feedback_feeModel.eleModelId  # 1		电费计费模型编号
            result.serModelId = service_feedback_feeModel.serModelId  # 2		服务费模型编号
            result.result = service_feedback_feeModel.result  # 3		失败原因

            HSyslog.log_info(f"Reply_to_Platform service_issue_feeModel: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_feeModel: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_feeModel: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"data_input_data: {json_str}" + init_char)
        HSyslog.log_info(f"callback_issue_feeModel: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_START_CHARGE_SRV]
cdef int callback_service_startCharge(evs_service_startCharge *param, evs_service_feedback_startCharge *result):
    post_data = {
        "info_id": EVS_START_CHARGE_SRV,
        "gunNo": param.gunNo,
        "preTradeNo": char_to_str(param.preTradeNo),
        "tradeNo": char_to_str(param.tradeNo),
        "startType": param.startType,
        "chargeMode": param.chargeMode,
        "limitData": param.limitData,
        "stopCode": param.stopCode,
        "startMode": param.startMode,
        "insertGunTime": param.insertGunTime
    }

    try: # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_startCharge(json_str)
        if back_data == "":
            print(red_char + f"callback_startCharge error" + init_char)
            HSyslog.log_info(f"callback_startCharge error")
            return -1
        try:
            if set_service_feedback_startCharge(back_data) == -1:
                print(red_char + f"set_service_feedback_startCharge error" + init_char)
                HSyslog.log_info(f"set_service_feedback_startCharge error")
                return -1
            result.gunNo = service_feedback_startCharge.gunNo  # 1 充电枪编号
            result.preTradeNo = service_feedback_startCharge.preTradeNo  # 2 平台交易流水号
            result.tradeNo = service_feedback_startCharge.tradeNo  # 3 设备交易流水号

            HSyslog.log_info(f"Reply_to_Platform service_startCharge: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_startCharge: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_startCharge: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_startCharge: {json_str}" + init_char)
        HSyslog.log_info(f"callback_startCharge: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_AUTH_RESULT_SRV]
cdef int callback_service_authCharge(evs_service_authCharge *param, evs_service_feedback_authCharge *result):
    post_data = {
        "info_id": EVS_AUTH_RESULT_SRV,
        "gunNo": param.gunNo,
        "preTradeNo": char_to_str(param.preTradeNo),
        "tradeNo": char_to_str(param.tradeNo),
        "vinCode": char_to_str(param.vinCode),
        "oppoCode": char_to_str(param.oppoCode),
        "result": param.result,
        "chargeMode": param.chargeMode,
        "limitData": param.limitData,
        "stopCode": param.stopCode,
        "startMode": param.startMode,
        "insertGunTime": param.insertGunTime
    }

    try:  # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_authCharge(json_str)
        if back_data == "":
            print(red_char + f"callback_authCharge error" + init_char)
            HSyslog.log_info("callback_authCharge error")
            return -1
        try:
            if set_service_feedback_authCharge(back_data) == -1:
                print(red_char + f"set_service_feedback_authCharge error" + init_char)
                HSyslog.log_info("set_service_feedback_authCharge error")
                return -1
            result.gunNo = service_feedback_authCharge.gunNo  # 1	充电枪编号
            result.preTradeNo = service_feedback_authCharge.preTradeNo  # 2	平台交易流水号
            result.tradeNo = service_feedback_authCharge.tradeNo  # 3	设备交易流水号

            HSyslog.log_info(f"Reply_to_Platform service_authCharge: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_authCharge: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_authCharge: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"data_input_data: {json_str}" + init_char)
        HSyslog.log_info(f"callback_authCharge: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_STOP_CHARGE_SRV]
cdef int callback_service_stopCharge(evs_service_stopCharge *param, evs_service_feedback_stopCharge *result):
    post_data = {
        "info_id": EVS_STOP_CHARGE_SRV,
        "gunNo": param.gunNo,
        "preTradeNo": char_to_str(param.preTradeNo),
        "tradeNo": char_to_str(param.tradeNo),
        "stopReason": param.stopReason
    }

    try: # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_stopCharge(json_str)
        if back_data == "":
            print(red_char + f"callback_stopCharge error" + init_char)
            HSyslog.log_info("callback_stopCharge error")
            return -1
        try:
            if set_service_feedback_stopCharge(back_data) == -1:
                print(red_char + f"set_service_feedback_stopCharge error" + init_char)
                HSyslog.log_info("set_service_feedback_stopCharge error")
                return -1
            result.gunNo = service_feedback_stopCharge.gunNo  # 1	充电枪编号
            result.preTradeNo = service_feedback_stopCharge.preTradeNo  # 2	平台交易流水号
            result.tradeNo = service_feedback_stopCharge.tradeNo  # 3	设备交易流水号

            HSyslog.log_info(f"Reply_to_Platform service_stopCharge: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_stopCharge: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_stopCharge: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_stopCharge: {json_str}" + init_char)
        HSyslog.log_info(f"callback_stopCharge: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_RSV_CHARGE_SRV]
cdef int callback_service_rsvCharge(evs_service_rsvCharge *param, evs_service_feedback_rsvCharge *result):
    post_data = {
        "info_id": EVS_RSV_CHARGE_SRV,
        "gunNo": param.gunNo,
        "appomathod": param.appomathod,
        "appoDelay": param.appoDelay
    }

    try:  # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_rsvCharge(json_str)
        if back_data == "":
            print(red_char + f"callback_rsvCharge error" + init_char)
            HSyslog.log_info(f"callback_rsvCharge error")
            return -1
        try:
            if set_service_feedback_rsvCharge(back_data) == -1:
                print(red_char + f"set_service_feedback_rsvCharge error" + init_char)
                HSyslog.log_info(f"set_service_feedback_rsvCharge error")
                return -1
            result.gunNo = service_feedback_rsvCharge.gunNo  # 1	充电枪编号
            result.appomathod = service_feedback_rsvCharge.appomathod  # 2	预约方式 10：立即预约 11：取消预约
            result.ret = service_feedback_rsvCharge.ret  # 3	预约结果
            result.reason = service_feedback_rsvCharge.reason  # 4	失败原因

            HSyslog.log_info(f"Reply_to_Platform service_rsvCharge: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_rsvCharge: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_rsvCharge: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_rsvCharge: {json_str}" + init_char)
        HSyslog.log_info(f"callback_rsvCharge: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_ORDER_CHECK_SRV]
cdef int callback_service_confirmTrade(evs_service_confirmTrade *param, void *result):
    post_data = {
        "info_id": EVS_ORDER_CHECK_SRV,
        "gunNo": param.gunNo,
        "preTradeNo": char_to_str(param.preTradeNo),
        "tradeNo": char_to_str(param.tradeNo),
        "errcode": param.errcode
    }

    try:  # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        callback_confirmTrade(json_str)
        return 0
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"data_input_data: {json_str}" + init_char)
        HSyslog.log_info(f"callback_confirmTrade: {json_str}. {e}")
        return -1


# [EVS_GROUND_LOCK_SRV]
cdef int callback_service_groundLock_ctrl(evs_service_groundLock_ctrl *param,
                                          evs_service_feedback_groundLock_ctrl *result):
    post_data = {
        "info_id": EVS_GROUND_LOCK_SRV,
        "gunNo": param.gunNo,
        "ctrlFlag": param.ctrlFlag
    }

    try:  # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_groundLock_ctrl(json_str)
        if back_data == "":
            print(red_char + f"callback_groundLock_ctrl error" + init_char)
            HSyslog.log_info(f"callback_groundLock_ctrl error")
            return -1
        try:
            if set_service_feedback_groundLock_ctrl(back_data) == -1:
                print(red_char + f"set_service_feedback_groundLock_ctrl error" + init_char)
                HSyslog.log_info(f"set_service_feedback_groundLock_ctrl error")
                return -1
            result.gunNo = service_feedback_groundLock_ctrl.gunNo  # 1	充电枪编号
            result.result = service_feedback_groundLock_ctrl.result  # 2	控制结果
            result.reason = service_feedback_groundLock_ctrl.reason  # 3	失败原因

            HSyslog.log_info(f"Reply_to_Platform service_groundLock_ctrl: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_groundLock_ctrl: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_groundLock_ctrl: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_groundLock_ctrl: {json_str}" + init_char)
        HSyslog.log_info(f"callback_groundLock_ctrl: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_GATE_LOCK_SRV]
cdef int callback_service_gateLock_ctrl(evs_service_gateLock_ctrl *param, evs_service_feedback_gateLock_ctrl *result):
    post_data = {
        "info_id": EVS_GATE_LOCK_SRV,
        "lockNo": param.lockNo,
        "ctrlFlag": param.ctrlFlag
    }

    try:  # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_gateLock_ctrl(json_str)
        if back_data == "":
            print(red_char + f"callback_gateLock_ctrl error" + init_char)
            HSyslog.log_info(f"callback_gateLock_ctrl error")
            return -1
        try:
            if set_service_feedback_gateLock_ctrl(back_data) == -1:
                print(red_char + f"set_service_feedback_gateLock_ctrl error" + init_char)
                HSyslog.log_info(f"set_service_feedback_gateLock_ctrl error")
                return -1
            result.lockNo = service_feedback_gateLock_ctrl.lockNo  # 1	充电枪编号
            result.result = service_feedback_gateLock_ctrl.result  # 2	控制结果

            HSyslog.log_info(f"Reply_to_Platform service_gateLock_ctrl: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_gateLock_ctrl: {back_data}" + init_char)
            HSyslog.log_info(f"mset_service_feedback_gateLock_ctrl: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_gateLock_ctrl: {json_str}" + init_char)
        HSyslog.log_info(f"callback_gateLock_ctrl: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_ORDERLY_CHARGE_SRV]
cdef int callback_service_orderCharge(evs_service_orderCharge *param, evs_service_feedback_orderCharge *result):
    post_data = {
        "info_id": EVS_ORDERLY_CHARGE_SRV,
        "preTradeNo": char_to_str(param.preTradeNo),
        "num": param.num,
        "validTime": char_to_str(param.validTime),
        "kw": char_to_str(param.kw)
    }

    try:  # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_orderCharge(json_str)
        if back_data == "":
            print(red_char + f"callback_orderCharge error" + init_char)
            HSyslog.log_info("callback_orderCharge error")
            return -1
        try:
            if set_service_feedback_orderCharge(back_data) == -1:
                print(red_char + f"set_service_feedback_orderCharge error" + init_char)
                HSyslog.log_info("set_service_feedback_orderCharge error")
                return -1
            result.preTradeNo = service_feedback_orderCharge.preTradeNo  # 1	订单流水号
            result.result = service_feedback_orderCharge.result  # 2	返回结果
            result.reason = service_feedback_orderCharge.reason  # 3	失败原因

            HSyslog.log_info(f"Reply_to_Platform service_orderCharge: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_orderCharge: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_orderCharge: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_orderCharge: {json_str}" + init_char)
        HSyslog.log_info(f"callback_orderCharge: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_CONF_GET_SRV]
cdef int callback_service_get_config(evs_data_dev_config *result):
    post_data = {
        "info_id": EVS_CONF_GET_SRV,
    }
    try:
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_get_config(json_str)
        if back_data == -1:
            print(red_char + f"callback_update_config error" + init_char)
            HSyslog.log_info(f"callback_update_config error")
            return -1
        HSyslog.log_info(f"Received_from_Platform service_get_config: {json_str}")
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(f"service_get_config: {post_data}")
        HSyslog.log_info(f"service_get_config: {post_data}")
        return -1

    try:
        dict_info = json.loads(back_data)

        result.equipParamFreq = dict_info.get("equipParamFreq")  # 1		充电设备实时监测属性上报频率
        result.gunElecFreq = dict_info.get("gunElecFreq")  # 2		充电枪充电中实时监测属性上报频率
        result.nonElecFreq = dict_info.get("nonElecFreq")  # 3		充电枪非充电中实时监测属性上报频率
        result.faultWarnings = dict_info.get("faultWarnings")  # 4		故障告警全信息上传频率
        result.acMeterFreq = dict_info.get("acMeterFreq")  # 5		充电设备交流电表底值监测属性上报频率
        result.dcMeterFreq = dict_info.get("dcMeterFreq")  # 6		直流输出电表底值监测属性上报频率
        result.offlinChaLen = dict_info.get("offlinChaLen")  # 7		离线后可充电时长
        result.grndLock = dict_info.get("grndLock")  # 8		地锁监测上送频率
        result.doorLock = dict_info.get("doorLock")  # 9		网门锁监测上送频率
        result.encodeCon = dict_info.get("encodeCon")  # 10	报文加密
        result.qrCode[0] = str_to_char(dict_info.get("qrCode")[0])  # 11	二维码数据
        result.qrCode[1] = str_to_char(dict_info.get("qrCode")[1])  # 11	二维码数据
        HSyslog.log_info(f"Reply_to_Platform service_get_config: {data_dev_config}")
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(f"service_get_config: {back_data}")
        HSyslog.log_info(f"service_get_config: {back_data}")
        return -1

    return 0

# [EVS_CONF_UPDATE_SRV]
cdef int callback_service_update_config(evs_data_dev_config *param, int *result):
    post_data = {
        "equipParamFreq": param.equipParamFreq,
        "gunElecFreq": param.gunElecFreq,
        "nonElecFreq": param.nonElecFreq,
        "faultWarnings": param.faultWarnings,
        "acMeterFreq": param.acMeterFreq,
        "dcMeterFreq": param.dcMeterFreq,
        "offlinChaLen": param.offlinChaLen,
        "grndLock": param.grndLock,
        "doorLock": param.doorLock,
        "encodeCon": param.encodeCon,
        "qrCode": [char_to_str(param.qrCode[0]), char_to_str(param.qrCode[1])]
    }

    try:  # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_update_config(json_str)
        if back_data == -1:
            print(red_char + f"callback_update_config error" + init_char)
            HSyslog.log_info(f"callback_update_config error")
            return -1
        result[0] = back_data
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_update_config: {json_str}" + init_char)
        HSyslog.log_info(f"callback_update_config: {json_str}. {e}")
        return -1

    if result == NULL:
        return -1
    else:
        return 0

# [EVS_OTA_UPDATE]
cdef int callback_service_ota_update(const char *version):
    new_version = char_to_str(version)
    try:
        back_data = callback_ota_update(new_version)
        if back_data[0] == -4:
            print("ota update failed")
            return -1
        else:
            return iot_linkkit_fota(back_data[0], back_data[1])
    except Exception as e:
        print(red_char + f"callback_ota_update" + init_char)
        HSyslog.log_info(f"callback_ota_update. {e}")


# [EVS_TIME_SYNC]
cdef int callback_service_time_sync(const uint32_t timestamp):
    palform_time = timestamp_to_datetime(timestamp)
    if palform_time is "":
        return -1
    # iot_linkkit_time_sync()
    HSyslog.log_info(f"Received_from_Platform service_time_sync: {palform_time}")
    try:  # 传到设备并接收
        back_data = callback_time_sync(palform_time)
        if back_data == "":
            print(red_char + f"callback_time_sync error" + init_char)
            HSyslog.log_info(f"Reply_to_Platform service_time_sync: {back_data}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_time_sync: {palform_time}" + init_char)
        HSyslog.log_info(f"callback_time_sync: {back_data}. {e}")
        return -1
    return 0

#[EVS_STATE_EVERYTHING]
cdef int callback_service_state_ever(int ev, const char *msg):
    post_data = {
        "info_id": EVS_STATE_EVERYTHING,
        "ev": ev,
        "msg": char_to_str(msg)
    }
    try:
        json_str = json.dumps(post_data)  # 改为json格式
        # print("received state event -- ", "-0x{:04X}".format(ev), char_to_str(msg))
        try:  # 传到设备并接收
            if callback_state_ever is not None:
                callback_state_ever(json_str)
            return 0
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"data_input_data: {json_str}" + init_char)
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        return -1



#[EVS_CONNECT_SUCC]
cdef int callback_service_connectSucc():
    global onlink_status
    onlink_status = 1
    iot_linkkit_time_sync()
    post_data = {
        "info_id": EVS_CONNECT_SUCC,
        "onlink_status": onlink_status
    }
    try:
        json_str = json.dumps(post_data)  # 改为json格式
        HSyslog.log_info(f"Received_from_Platform service_connectSucc: {json_str}")
        try:  # 传到设备并接收
            back_data = callback_connectSucc(json_str)
            if back_data == -1:
                print(red_char + f"callback_connectSucc error" + init_char)
                HSyslog.log_info(f"Reply_to_Platform service_connectSucc: {back_data}")
                return -1
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"data_input_data: {json_str}" + init_char)
            return -1
        print(f"MQTT Connect Success: {onlink_status}")
        # send_property.start_all_sendproperty()
        return 0
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        return -1

#[EVS_DISCONNECTED]
cdef int callback_service_disConnected():
    global onlink_status
    onlink_status = 0
    post_data = {
        "info_id": EVS_DISCONNECTED,
        "onlink_status": onlink_status
    }
    try:
        json_str = json.dumps(post_data)  # 改为json格式
        HSyslog.log_info(f"Received_from_Platform service_disConnected: {json_str}")
        try:  # 传到设备并接收
            back_data = callback_disConnected(json_str)
            if back_data == -1:
                print(red_char + f"callback_disConnected error" + init_char)
                HSyslog.log_info(f"Reply_to_Platform service_disConnected: {back_data}")
                return -1
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"data_input_data: {json_str}" + init_char)
            return -1
        print(f"MQTT DisConnected: {onlink_status}")
        return 0
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        return -1

#[EVS_REPORT_REPLY]
cdef int callback_service_reportReply(  #const int devid,
        const int msgid,
        const int code,
        const char *reply,
        const int reply_len):
    # print(green_char)
    # print(
    #     f"Property Message Post Reply Received, Message ID: {msgid}, Message Code: {code}, Message Reply: {char_to_str(reply)}")
    # print(init_char)
    # HSyslog.log_info(f"Property Message Post Reply Received, Message ID: {msgid}, Message Code: {code}, Message Reply: {char_to_str(reply)}")
    return 0

#[EVS_TRIGGER_EVENT_REPLY]
cdef int callback_service_trigEvevtReply(  #const int devid,
        const int msgid,
        const int code,
        const char *eventid,
        const int eventid_len,
        const char *message,
        const int message_len):

    # print(green_char)
    # print(
    #     f"Event Post Reply Received, Message ID: {msgid}, Message Code: {code}, EventID: {char_to_str(eventid)}, Message: {char_to_str(message)}")
    # print(init_char)
    # HSyslog.log_info(f"Event Post Reply Received, Message ID: {msgid}, Message Code: {code}, EventID: {char_to_str(eventid)}, Message: {char_to_str(message)}")
    post_data = {
        "info_id": EVS_TRIGGER_EVENT_REPLY,
        "msgid": msgid,
        "code": code,
        "eventid": char_to_str(eventid),
        "message": char_to_str(message),
    }
    try:
        json_str = json.dumps(post_data)  # 改为json格式
        # print("received state event -- ", "-0x{:04X}".format(ev), char_to_str(msg))
        try:  # 传到设备并接收
            if callback_trigEvevtReply is not None:
                callback_trigEvevtReply(json_str)
            return 0
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"data_input_data: {json_str}" + init_char)
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        return -1

#[EVS_CERT_GET]
cdef int callback_service_certGet(evs_device_meta *meta):
    try:
        product_key = get_DeviceInfo("productKey")
        if product_key is None:
            product_key = ""
        device_name = get_DeviceInfo("deviceName")
        if device_name is None:
            device_name = ""
        device_secret = get_DeviceInfo("deviceSecret")
        if device_secret is None:
            device_secret = ""

        meta.product_key = str_to_char(product_key)  #设备品类标识字符串
        meta.device_name = str_to_char(device_name)  #某台设备的标识字符串:未注册前为设备出厂编号（16位长度），注册后为设备在物联管理平台的资产码（24位长度）
        meta.device_secret = str_to_char(device_secret)  #某台设备的设备密钥
        meta.device_reg_code = device_meta.device_reg_code  #某台设备的设备注册码
        meta.device_uid = device_meta.device_uid
        return 0
    except Exception as e:
        print(f"callback_service_certGet: {e}")


#[EVS_CERT_SET]
cdef int callback_service_certSet(evs_device_meta meta):
    try:
        product_key = remove_escape_characters(meta.product_key)
        device_name = remove_escape_characters(meta.device_name)
        device_secret = remove_escape_characters(meta.device_secret)
    except Exception as e:
        print(f"callback_service_certSet: {e}")

    try:
        save_DeviceInfo("Vendor_Code", 1, "1031", 0)
        save_DeviceInfo("device_type", 1, "01", 0)
        save_DeviceInfo("productKey", 1, char_to_str(product_key), 0)
        save_DeviceInfo("deviceName", 1, char_to_str(device_name), 0)
        save_DeviceInfo("deviceSecret", 1, char_to_str(device_secret), 0)
    except Exception as e:
        print(f"save_DeviceInfo: {e}")

#[EVS_DEVICE_REG_CODE_GET]
cdef int callback_service_deregCodeGet(char *device_reg_code):
    for i in range(0, len(char_to_str(device_meta.device_reg_code)) + 1):
        device_reg_code[i] = device_meta.device_reg_code[i]
    return len(char_to_str(device_meta.device_reg_code))

# [EVS_DEVICE_UID_GET]
cdef int callback_service_uidGet(char *device_uid):
    for i in range(0, len(char_to_str(device_meta.device_uid)) + 1):
        device_uid[i] = device_meta.device_uid[i]
    return len(char_to_str(device_meta.device_uid))


# [EVS_MAINTAIN_RESULT_SRV]
cdef int callback_service_mainres(evs_service_feedback_maintain_query *result):
    post_data = {
        "info_id": EVS_MAINTAIN_RESULT_SRV
    }

    try:  # 传到设备并接收
        json_str = json.dumps(post_data)  # 改为json格式
        back_data = callback_mainres(json_str)
        if back_data == "":
            print(red_char + f"callback_mainres error" + init_char)
            HSyslog.log_info(f"callback_mainres error")
            return -1
        try:
            if set_service_feedback_maintain_query(back_data) == -1:
                print(red_char + f"set_service_feedback_maintain_query error" + init_char)
                HSyslog.log_info(f"set_service_feedback_maintain_query error")
                return -1
            result.ctrlType = service_feedback_maintain_query.ctrlType
            result.result = service_feedback_maintain_query.result

            HSyslog.log_info(f"Reply_to_Platform service_mainres: {back_data}")
        except Exception as e:
            print(red_char + f"{e}" + init_char)
            print(red_char + f"set_service_feedback_maintain_query: {back_data}" + init_char)
            HSyslog.log_info(f"set_service_feedback_maintain_query: {back_data}. {e}")
            return -1
    except Exception as e:
        print(red_char + f"{e}" + init_char)
        print(red_char + f"callback_mainres: {json_str}" + init_char)
        HSyslog.log_info(f"callback_mainres: {json_str}. {e}")
        return -1

    return 0

#-----------------------------------------------------设置系统参数------------------------------------------------------#


def set_device_meta(json_str):
    try:
        info_dict = json.loads(json_str)
        device_meta.device_reg_code = str_to_char(info_dict.get("device_reg_code", ""))
        device_meta.product_key = str_to_char(info_dict.get("product_key", ""))
        device_meta.product_secret = str_to_char(info_dict.get("product_secret", ""))
        device_meta.device_name = str_to_char(info_dict.get("device_name", ""))
        device_meta.device_secret = str_to_char(info_dict.get("device_secret", ""))
        device_meta.device_uid = str_to_char(info_dict.get("device_uid", ""))
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_fireware_info(json_str: str):
    try:
        info_dict = json.loads(json_str)
        event_fireware_info.simNo = str_to_char(info_dict.get("simNo", ""))
        event_fireware_info.eleModelId = str_to_char(info_dict.get("eleModelId", ""))
        event_fireware_info.serModelId = str_to_char(info_dict.get("serModelId", ""))
        event_fireware_info.stakeModel = str_to_char(info_dict.get("stakeModel", ""))
        event_fireware_info.vendorCode = info_dict.get("vendorCode", 0)
        event_fireware_info.devSn = str_to_char(info_dict.get("devSn", ""))
        event_fireware_info.devType = info_dict.get("devType", 0)
        event_fireware_info.portNum = info_dict.get("portNum", 0)
        event_fireware_info.simMac = str_to_char(info_dict.get("simMac", ""))
        event_fireware_info.longitude = info_dict.get("longitude", 0)
        event_fireware_info.latitude = info_dict.get("latitude", 0)
        event_fireware_info.height = info_dict.get("height", 0)
        event_fireware_info.gridType = info_dict.get("gridType", 0)
        event_fireware_info.btMac = str_to_char(info_dict.get("btMac", ""))
        event_fireware_info.meaType = info_dict.get("meaType", 0)
        event_fireware_info.otRate = info_dict.get("otRate", 0)
        event_fireware_info.otMinVol = info_dict.get("otMinVol", 0)
        event_fireware_info.otMaxVol = info_dict.get("otMaxVol", 0)
        event_fireware_info.otCur = info_dict.get("otCur", 0)
        #event_fireware_info.inMeter = info_dict.get("inMeter", "")

        event_fireware_info.outMeter[0] = str_to_char(info_dict.get("outMeter", "")[0])
        event_fireware_info.outMeter[1] = str_to_char(info_dict.get("outMeter", "")[1])

        event_fireware_info.CT = info_dict.get("CT", 0)
        event_fireware_info.isGateLock = info_dict.get("isGateLock", 0)
        event_fireware_info.isGroundLock = info_dict.get("isGroundLock", 0)

        # print(f"event_fireware_info: {event_fireware_info}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_ver_info(json_str):
    try:
        info_dict = json.loads(json_str)
        event_ver_info.devRegMethod = info_dict.get("devRegMethod", 0)
        event_ver_info.pileSoftwareVer = str_to_char(info_dict.get("pileSoftwareVer", ""))
        event_ver_info.pileHardwareVer = str_to_char(info_dict.get("pileHardwareVer", ""))
        event_ver_info.sdkVer = str_to_char(info_dict.get("sdkVer", ""))
        # print(f"event_ver_info: {event_ver_info}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_data_dev_config(json_str):
    try:
        info_dict = json.loads(json_str)
        data_dev_config.equipParamFreq = info_dict.get("equipParamFreq", 600)
        data_dev_config.gunElecFreq = info_dict.get("gunElecFreq", 90)
        data_dev_config.nonElecFreq = info_dict.get("nonElecFreq", 180)
        data_dev_config.faultWarnings = info_dict.get("faultWarnings", 360)
        data_dev_config.acMeterFreq = info_dict.get("acMeterFreq", 60)
        data_dev_config.dcMeterFreq = info_dict.get("dcMeterFreq", 60)
        data_dev_config.offlinChaLen = info_dict.get("offlinChaLen", 5)
        data_dev_config.grndLock = info_dict.get("grndLock", 60)
        data_dev_config.doorLock = info_dict.get("doorLock", 60)
        data_dev_config.encodeCon = info_dict.get("encodeCon", 0)
        data_dev_config.qrCode[0] = str_to_char(info_dict.get("qrCode", "")[0])
        data_dev_config.qrCode[1] = str_to_char(info_dict.get("qrCode", "")[1])
        # print(f"data_dev_config: {data_dev_config}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_query_log(json_str):
    try:
        info_dict = json.loads(json_str)
        service_query_log.gunNo = info_dict.get("gunNo")
        service_query_log.startDate = info_dict.get("startDate")
        service_query_log.stopDate = info_dict.get("stopDate")
        service_query_log.askType = info_dict.get("askType")
        service_query_log.logQueryNo = str_to_char(info_dict.get("logQueryNo"))
        # print(f"service_query_log: {service_query_log}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_query_log(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_query_log.gunNo = info_dict.get("gunNo")
        service_feedback_query_log.startDate = info_dict.get("startDate")
        service_feedback_query_log.stopDate = info_dict.get("stopDate")
        service_feedback_query_log.askType = info_dict.get("askType")
        service_feedback_query_log.result = info_dict.get("result")
        service_feedback_query_log.logQueryNo = str_to_char(info_dict.get("logQueryNo"))
        # print(f"service_feedback_query_log: {service_feedback_query_log}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_dev_maintain(json_str):
    try:
        info_dict = json.loads(json_str)
        service_dev_maintain.ctrlType = info_dict.get("ctrlType")
        # print(f"service_dev_maintain: {service_dev_maintain}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_dev_maintain(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_dev_maintain.ctrlType = info_dict.get("ctrlType")
        service_feedback_dev_maintain.reason = info_dict.get("reason")
        # print(f"service_feedback_dev_maintain: {service_feedback_dev_maintain}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_lockCtrl(json_str):
    try:
        info_dict = json.loads(json_str)
        service_lockCtrl.gunNo = info_dict.get("gunNo")
        service_lockCtrl.lockParam = info_dict.get("lockParam")
        # print(f"service_lockCtrl: {service_lockCtrl}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_lockCtrl(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_lockCtrl.gunNo = info_dict.get("gunNo")
        service_feedback_lockCtrl.lockStatus = info_dict.get("lockStatus")
        service_feedback_lockCtrl.resCode = info_dict.get("resCode")
        # print(f"service_feedback_lockCtrl: {service_feedback_lockCtrl}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_issue_feeModel(json_str):
    try:
        info_dict = json.loads(json_str)
        service_issue_feeModel.eleModelId = str_to_char(info_dict.get("eleModelId"))
        service_issue_feeModel.serModelId = str_to_char(info_dict.get("serModelId"))
        service_issue_feeModel.TimeNum = info_dict.get("TimeNum")
        service_issue_feeModel.SegFlag = info_dict.get("SegFlag")
        service_issue_feeModel.chargeFee = info_dict.get("chargeFee")
        service_issue_feeModel.serviceFee = info_dict.get("serviceFee")
        for i in range(0, info_dict.get("TimeNum")):
            service_issue_feeModel.TimeSeg[i] = str_to_char(info_dict.get("TimeSeg")[i])
        # print(f"service_issue_feeModel: {service_issue_feeModel}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_feeModel(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_feeModel.eleModelId = str_to_char(info_dict.get("eleModelId"))
        service_feedback_feeModel.serModelId = str_to_char(info_dict.get("serModelId"))
        service_feedback_feeModel.result = info_dict.get("result")
        # print(f"service_feedback_feeModel: {service_feedback_feeModel}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_startCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_startCharge.gunNo = info_dict.get("gunNo")
        service_startCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        service_startCharge.tradeNo = str_to_char(info_dict.get("tradeNo"))
        service_startCharge.startType = info_dict.get("startType")
        service_startCharge.chargeMode = info_dict.get("chargeMode")
        service_startCharge.limitData = info_dict.get("limitData")
        service_startCharge.stopCode = info_dict.get("stopCode")
        service_startCharge.startMode = info_dict.get("startMode")
        service_startCharge.insertGunTime = info_dict.get("insertGunTime")
        # print(f"service_startCharge: {service_startCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_startCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_startCharge.gunNo = info_dict.get("gunNo")
        service_feedback_startCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        service_feedback_startCharge.tradeNo = str_to_char(info_dict.get("tradeNo"))
        # print(f"service_feedback_startCharge: {service_feedback_startCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_startResult(json_str):
    try:
        info_dict = json.loads(json_str)
        event_startResult.gunNo = info_dict.get("gunNo")
        event_startResult.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        event_startResult.tradeNo = str_to_char(info_dict.get("tradeNo"))
        event_startResult.startResult = info_dict.get("startResult")
        event_startResult.faultCode = info_dict.get("faultCode")
        event_startResult.vinCode = str_to_char(info_dict.get("vinCode"))
        # print(f"event_startResult: {event_startResult}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_startCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        event_startCharge.gunNo = info_dict.get("gunNo")
        event_startCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        event_startCharge.tradeNo = str_to_char(info_dict.get("tradeNo"))
        event_startCharge.startType = info_dict.get("startType")
        event_startCharge.authCode = str_to_char(info_dict.get("authCode"))
        event_startCharge.batterySOC = info_dict.get("batterySOC")
        event_startCharge.batteryCap = info_dict.get("batteryCap")
        event_startCharge.chargeTimes = info_dict.get("chargeTimes")
        event_startCharge.batteryVol = info_dict.get("batteryVol")
        # print(f"event_startCharge: {event_startCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_authCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_authCharge.gunNo = info_dict.get("gunNo")
        service_authCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        service_authCharge.tradeNo = str_to_char(info_dict.get("tradeNo"))
        service_authCharge.vinCode = str_to_char(info_dict.get("vinCode"))
        service_authCharge.oppoCode = str_to_char(info_dict.get("oppoCode"))
        service_authCharge.result = info_dict.get("result")
        service_authCharge.chargeMode = info_dict.get("chargeMode")
        service_authCharge.limitData = info_dict.get("limitData")
        service_authCharge.stopCode = info_dict.get("stopCode")
        service_authCharge.startMode = info_dict.get("startMode")
        service_authCharge.insertGunTime = info_dict.get("insertGunTime")
        # print(f"service_authCharge: {service_authCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_authCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_authCharge.gunNo = info_dict.get("gunNo")
        service_feedback_authCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        service_feedback_authCharge.tradeNo = str_to_char(info_dict.get("tradeNo"))
        # print(f"service_feedback_authCharge: {service_feedback_authCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_stopCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_stopCharge.gunNo = info_dict.get("gunNo")
        service_stopCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        service_stopCharge.tradeNo = str_to_char(info_dict.get("tradeNo"))
        service_stopCharge.stopReason = info_dict.get("stopReason")
        # print(f"service_stopCharge: {service_stopCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_stopCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_stopCharge.gunNo = info_dict.get("gunNo")
        service_feedback_stopCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        service_feedback_stopCharge.tradeNo = str_to_char(info_dict.get("tradeNo"))
        # print(f"service_feedback_stopCharge: {service_feedback_stopCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_stopCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        event_stopCharge.gunNo = info_dict.get("gunNo")
        event_stopCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        event_stopCharge.tradeNo = str_to_char(info_dict.get("tradeNo"))
        event_stopCharge.stopResult = info_dict.get("stopResult")
        event_stopCharge.resultCode = info_dict.get("resultCode")
        event_stopCharge.stopFailReson = info_dict.get("stopFailReson")
        # print(f"event_stopCharge: {event_stopCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_tradeInfo(json_str):
    try:
        info_dict = json.loads(json_str)
        event_tradeInfo.gunNo = info_dict.get("gunNo")
        event_tradeInfo.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        event_tradeInfo.tradeNo = str_to_char(info_dict.get("tradeNo"))
        event_tradeInfo.vinCode = str_to_char(info_dict.get("vinCode"))
        event_tradeInfo.timeDivType = info_dict.get("timeDivType")
        event_tradeInfo.chargeStartTime = info_dict.get("chargeStartTime")
        event_tradeInfo.chargeEndTime = info_dict.get("chargeEndTime")
        event_tradeInfo.startSoc = info_dict.get("startSoc")
        event_tradeInfo.endSoc = info_dict.get("endSoc")
        event_tradeInfo.reason = info_dict.get("reason")
        event_tradeInfo.eleModelId = str_to_char(info_dict.get("eleModelId"))
        event_tradeInfo.serModelId = str_to_char(info_dict.get("serModelId"))
        event_tradeInfo.sumStart = info_dict.get("sumStart")
        event_tradeInfo.sumEnd = info_dict.get("sumEnd")
        event_tradeInfo.totalElect = info_dict.get("totalElect")
        event_tradeInfo.sharpElect = info_dict.get("sharpElect")
        event_tradeInfo.peakElect = info_dict.get("peakElect")
        event_tradeInfo.flatElect = info_dict.get("flatElect")
        event_tradeInfo.valleyElect = info_dict.get("valleyElect")
        event_tradeInfo.totalPowerCost = info_dict.get("totalPowerCost")
        event_tradeInfo.totalServCost = info_dict.get("totalServCost")
        event_tradeInfo.sharpPowerCost = info_dict.get("sharpPowerCost")
        event_tradeInfo.peakPowerCost = info_dict.get("peakPowerCost")
        event_tradeInfo.flatPowerCost = info_dict.get("flatPowerCost")
        event_tradeInfo.valleyPowerCost = info_dict.get("valleyPowerCost")
        event_tradeInfo.sharpServCost = info_dict.get("sharpServCost")
        event_tradeInfo.peakServCost = info_dict.get("peakServCost")
        event_tradeInfo.flatServCost = info_dict.get("flatServCost")
        event_tradeInfo.valleyServCost = info_dict.get("valleyServCost")
        # print(f"event_tradeInfo: {event_tradeInfo}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_confirmTrade(json_str):
    try:
        info_dict = json.loads(json_str)
        service_confirmTrade.gunNo = info_dict.get("gunNo")
        service_confirmTrade.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        service_confirmTrade.tradeNo = str_to_char(info_dict.get("tradeNo"))
        service_confirmTrade.errcode = info_dict.get("errcode")
        # print(f"service_confirmTrade: {service_confirmTrade}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_alarm(json_str):
    try:
        for i in range(0, 50):  # 初始化
            event_alarm.faultValue[i] = 0
            event_alarm.warnValue[i] = 0

        info_dict = json.loads(json_str)
        event_alarm.gunNo = info_dict.get("gunNo")
        event_alarm.faultSum = info_dict.get("faultSum")
        event_alarm.warnSum = info_dict.get("warnSum")
        for i in range(0, event_alarm.faultSum):
            event_alarm.faultValue[i] = info_dict.get("faultValue")[i]
        for i in range(0, event_alarm.warnSum):
            event_alarm.warnValue[i] = info_dict.get("warnValue")[i]
        # print(f"event_alarm: {event_alarm}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_rsvCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_rsvCharge.gunNo = info_dict.get("gunNo")
        service_rsvCharge.appomathod = info_dict.get("appomathod")
        service_rsvCharge.appoDelay = info_dict.get("appoDelay")
        # print(f"service_rsvCharge: {service_rsvCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_rsvCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_rsvCharge.gunNo = info_dict.get("gunNo")
        service_feedback_rsvCharge.appomathod = info_dict.get("appomathod")
        service_feedback_rsvCharge.ret = info_dict.get("ret")
        service_feedback_rsvCharge.reason = info_dict.get("reason")
        # print(f"service_feedback_rsvCharge: {service_feedback_rsvCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_groundLock_ctrl(json_str):
    try:
        info_dict = json.loads(json_str)
        service_groundLock_ctrl.gunNo = info_dict.get("gunNo")
        service_groundLock_ctrl.ctrlFlag = info_dict.get("ctrlFlag")
        # print(f"service_groundLock_ctrl: {service_groundLock_ctrl}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_groundLock_ctrl(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_groundLock_ctrl.gunNo = info_dict.get("gunNo")
        service_feedback_groundLock_ctrl.reason = info_dict.get("reason")
        service_feedback_groundLock_ctrl.result = info_dict.get("result")
        # print(f"service_feedback_groundLock_ctrl: {service_feedback_groundLock_ctrl}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_groundLock_change(json_str):
    try:
        info_dict = json.loads(json_str)
        event_groundLock_change.gunNo = info_dict.get("gunNo")
        event_groundLock_change.lockState = info_dict.get("lockState")
        event_groundLock_change.powerType = info_dict.get("powerType")
        event_groundLock_change.cellState = info_dict.get("cellState")
        event_groundLock_change.lockerState = info_dict.get("lockerState")
        event_groundLock_change.lockerForced = info_dict.get("lockerForced")
        event_groundLock_change.lowPower = info_dict.get("lowPower")
        event_groundLock_change.soc = info_dict.get("soc")
        event_groundLock_change.openCnt = info_dict.get("openCnt")
        # print(f"event_groundLock_change: {event_groundLock_change}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_gateLock_ctrl(json_str):
    try:
        info_dict = json.loads(json_str)
        service_gateLock_ctrl.lockNo = info_dict.get("lockNo")
        service_gateLock_ctrl.ctrlFlag = info_dict.get("ctrlFlag")
        # print(f"service_gateLock_ctrl: {service_gateLock_ctrl}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_gateLock_ctrl(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_gateLock_ctrl.lockNo = info_dict.get("lockNo")
        service_feedback_gateLock_ctrl.result = info_dict.get("result")
        # print(f"service_feedback_gateLock_ctrl: {service_feedback_gateLock_ctrl}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_gateLock_change(json_str):
    try:
        info_dict = json.loads(json_str)
        event_gateLock_change.lockNo = info_dict.get("lockNo")
        event_gateLock_change.lockState = info_dict.get("lockState")
        # print(f"event_gateLock_change: {event_gateLock_change}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_orderCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_orderCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        service_orderCharge.num = info_dict.get("num")
        service_orderCharge.validTime = info_dict.get("validTime")
        service_orderCharge.kw = str_to_char(info_dict.get("kw"))
        # print(f"service_orderCharge: {service_orderCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_orderCharge(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_orderCharge.preTradeNo = str_to_char(info_dict.get("preTradeNo"))
        service_feedback_orderCharge.result = info_dict.get("result")
        service_feedback_orderCharge.reason = info_dict.get("reason")
        # print(f"service_feedback_orderCharge: {service_feedback_orderCharge}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_pile_stutus_change(json_str):
    try:
        info_dict = json.loads(json_str)
        event_pile_stutus_change.gunNo = info_dict.get("gunNo")
        event_pile_stutus_change.yxOccurTime = info_dict.get("yxOccurTime")
        event_pile_stutus_change.connCheckStatus = info_dict.get("connCheckStatus")
        # print(f"event_pile_stutus_change: {event_pile_stutus_change}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_car_info(json_str):
    try:
        info_dict = json.loads(json_str)
        event_car_info.gunNo = info_dict.get("gunNo")
        event_car_info.vinCode = str_to_char(info_dict.get("vinCode"))
        event_car_info.batterySOC = info_dict.get("batterySOC")
        event_car_info.batteryCap = info_dict.get("batteryCap")
        event_car_info.state = info_dict.get("state")
        # print(f"event_car_info: {event_car_info}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_property_dcPile(json_str):
    try:
        info_dict = json.loads(json_str)
        property_dcPile.netType = info_dict.get("netType", 0)
        property_dcPile.sigVal = info_dict.get("sigVal", 0)
        property_dcPile.netId = info_dict.get("netId", 0)
        property_dcPile.acVolA = info_dict.get("acVolA", 0)
        property_dcPile.acCurA = info_dict.get("acCurA", 0)
        property_dcPile.acVolB = info_dict.get("acVolB", 0)
        property_dcPile.acCurB = info_dict.get("acCurB", 0)
        property_dcPile.acVolC = info_dict.get("acVolC", 0)
        property_dcPile.acCurC = info_dict.get("acCurC", 0)
        property_dcPile.caseTemp = info_dict.get("caseTemp", 0)
        property_dcPile.inletTemp = info_dict.get("inletTemp", 0)
        property_dcPile.outletTemp = info_dict.get("outletTemp", 0)
        property_dcPile.eleModelId = str_to_char(info_dict.get("eleModelId", ""))
        property_dcPile.serModelId = str_to_char(info_dict.get("serModelId", ""))
        # print(f"property_dcPile: {property_dcPile}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"set_property_dcPile---json_data: {json_str}. {e}")
        return -1

def set_property_BMS(json_str):
    try:
        info_dict = json.loads(json_str)
        property_BMS.gunNo = info_dict.get("gunNo", 1)
        property_BMS.preTradeNo = str_to_char(info_dict.get("preTradeNo", ""))
        property_BMS.tradeNo = str_to_char(info_dict.get("tradeNo", ""))
        property_BMS.socVal = info_dict.get("socVal", 0)
        property_BMS.BMSVer = info_dict.get("BMSVer", 0)
        property_BMS.BMSMaxVol = info_dict.get("BMSMaxVol", 0)
        property_BMS.batType = info_dict.get("batType", 0)
        property_BMS.batRatedCap = info_dict.get("batRatedCap", 0)
        property_BMS.batRatedTotalVol = info_dict.get("batRatedTotalVol", 0)
        property_BMS.singlBatMaxAllowVol = info_dict.get("singlBatMaxAllowVol", 0)
        property_BMS.maxAllowCur = info_dict.get("maxAllowCur", 0)
        property_BMS.battotalEnergy = info_dict.get("battotalEnergy", 0)
        property_BMS.maxVol = info_dict.get("maxVol", 0)
        property_BMS.maxTemp = info_dict.get("maxTemp", 0)
        property_BMS.batCurVol = info_dict.get("batCurVol", 0)
        # print(f"property_BMS: {property_BMS}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"set_property_BMS---json_data: {json_str}. {e}")
        return -1

def set_property_dc_work(json_str):
    try:
        info_dict = json.loads(json_str)
        property_dc_work.gunNo = info_dict.get("gunNo", 1)
        property_dc_work.workStatus = info_dict.get("workStatus", 0)
        property_dc_work.gunStatus = info_dict.get("gunStatus", 0)
        property_dc_work.eLockStatus = info_dict.get("eLockStatus", 0)
        property_dc_work.DCK1Status = info_dict.get("DCK1Status", 0)
        property_dc_work.DCK2Status = info_dict.get("DCK2Status", 0)
        property_dc_work.DCPlusFuseStatus = info_dict.get("DCPlusFuseStatus", 0)
        property_dc_work.DCMinusFuseStatus = info_dict.get("DCMinusFuseStatus", 0)
        property_dc_work.conTemp1 = info_dict.get("conTemp1", 0)
        property_dc_work.conTemp2 = info_dict.get("conTemp2", 0)
        property_dc_work.dcVol = info_dict.get("dcVol", 0)
        property_dc_work.dcCur = info_dict.get("dcCur", 0)
        property_dc_work.preTradeNo = str_to_char(info_dict.get("preTradeNo", ""))
        property_dc_work.tradeNo = str_to_char(info_dict.get("tradeNo", ""))
        property_dc_work.chgType = info_dict.get("chgType", 0)
        property_dc_work.realPower = info_dict.get("realPower", 0)
        property_dc_work.chgTime = info_dict.get("chgTime", 0)
        property_dc_work.socVal = info_dict.get("socVal", 0)
        property_dc_work.needVol = info_dict.get("needVol", 0)
        property_dc_work.needCur = info_dict.get("needCur", 0)
        property_dc_work.chargeMode = info_dict.get("chargeMode", 0)
        property_dc_work.bmsVol = info_dict.get("bmsVol", 0)
        property_dc_work.bmsCur = info_dict.get("bmsCur", 0)
        property_dc_work.SingleMHV = info_dict.get("SingleMHV", 0)
        property_dc_work.remainT = info_dict.get("remainT", 0)
        property_dc_work.MHTemp = info_dict.get("MHTemp", 0)
        property_dc_work.MLTemp = info_dict.get("MLTemp", 0)
        property_dc_work.totalElect = info_dict.get("totalElect", 0)
        property_dc_work.sharpElect = info_dict.get("sharpElect", 0)
        property_dc_work.peakElect = info_dict.get("peakElect", 0)
        property_dc_work.flatElect = info_dict.get("flatElect", 0)
        property_dc_work.valleyElect = info_dict.get("valleyElect", 0)
        property_dc_work.totalCost = info_dict.get("totalCost", 0)
        property_dc_work.totalPowerCost = info_dict.get("totalPowerCost", 0)
        property_dc_work.totalServCost = info_dict.get("totalServCost", 0)
        # print(f"property_dc_work: {property_dc_work}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"set_property_dc_work---json_data: {json_str}. {e}")
        return -1

def set_property_dc_nonWork(json_str):
    try:
        info_dict = json.loads(json_str)
        property_dc_nonWork.gunNo = info_dict.get("gunNo", 1)
        property_dc_nonWork.workStatus = info_dict.get("workStatus", 0)
        property_dc_nonWork.gunStatus = info_dict.get("gunStatus", 0)
        property_dc_nonWork.eLockStatus = info_dict.get("eLockStatus", 0)
        property_dc_nonWork.DCK1Status = info_dict.get("DCK1Status", 0)
        property_dc_nonWork.DCK2Status = info_dict.get("DCK2Status", 0)
        property_dc_nonWork.DCPlusFuseStatus = info_dict.get("DCPlusFuseStatus", 0)
        property_dc_nonWork.DCMinusFuseStatus = info_dict.get("DCMinusFuseStatus", 0)
        property_dc_nonWork.conTemp1 = info_dict.get("conTemp1", 0)
        property_dc_nonWork.conTemp2 = info_dict.get("conTemp2", 0)
        property_dc_nonWork.dcVol = info_dict.get("dcVol", 0)
        property_dc_nonWork.dcCur = info_dict.get("dcCur", 0)
        # print(f"property_dc_nonWork: {property_dc_nonWork}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"set_property_dc_nonWork---json_data: {json_str}. {e}")
        return -1

def set_property_dc_input_meter(json_str):
    try:
        info_dict = json.loads(json_str)
        property_dc_input_meter.gunNo = info_dict.get("gunNo", 1)
        property_dc_input_meter.acqTime = str_to_char(info_dict.get("acqTime", ""))
        property_dc_input_meter.mailAddr = str_to_char(info_dict.get("mailAddr", ""))
        property_dc_input_meter.meterNo = str_to_char(info_dict.get("meterNo", ""))
        property_dc_input_meter.assetId = str_to_char(info_dict.get("assetId", ""))
        property_dc_input_meter.sumMeter = info_dict.get("sumMeter", 0)
        property_dc_input_meter.ApElect = info_dict.get("ApElect", 0)
        property_dc_input_meter.BpElect = info_dict.get("BpElect", 0)
        property_dc_input_meter.CpElect = info_dict.get("CpElect", 0)
        # print(f"property_dc_input_meter: {property_dc_input_meter}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"set_property_dc_input_meter---json_data: {json_str}. {e}")
        return -1

def set_property_meter(json_str):
    try:
        info_dict = json.loads(json_str)
        property_meter.gunNo = info_dict.get("gunNo", 1)
        property_meter.acqTime = str_to_char(info_dict.get("acqTime", ""))
        property_meter.assetId = str_to_char(info_dict.get("assetId", ""))
        property_meter.sumMeter = info_dict.get("sumMeter", 0)
        property_meter.lastTrade = str_to_char(info_dict.get("lastTrade", ""))
        property_meter.elec = info_dict.get("elec", 0)
        property_meter.meterNo = str_to_char(info_dict.get("meterNo", ""))
        property_meter.mailAddr = str_to_char(info_dict.get("mailAddr", ""))
        # print(f"property_meter: {property_meter}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"set_property_meter---json_data: {json_str}. {e}")
        return -1


def set_event_logQuery_Result(json_str):
    cdef u_logData logData
    cdef evs_event_tradeInfo tradeInfo
    cdef evs_property_meter meter
    cdef evs_property_BMS BMS
    try:
        info_dict = json.loads(json_str)
        event_logQuery_Result.gunNo = info_dict.get("gunNo")
        event_logQuery_Result.startDate = info_dict.get("startDate")
        event_logQuery_Result.stopDate = info_dict.get("stopDate")
        event_logQuery_Result.askType = info_dict.get("askType")
        event_logQuery_Result.result = info_dict.get("result")
        event_logQuery_Result.logQueryNo = str_to_char(info_dict.get("logQueryNo"))
        event_logQuery_Result.retType = info_dict.get("retType")
        event_logQuery_Result.logQueryEvtSum = info_dict.get("logQueryEvtSum")
        event_logQuery_Result.logQueryEvtNo = info_dict.get("logQueryEvtNo")
        if info_dict.get("askType") == 12:
            logData.rawData = PyBytes_AS_STRING(PyUnicode_AsUTF8String(info_dict.get("dataArea")))
            event_logQuery_Result.dataArea = logData
        if info_dict.get("askType") == 13:
            logData.rawData = PyBytes_AS_STRING(PyUnicode_AsUTF8String(info_dict.get("dataArea")))
            event_logQuery_Result.dataArea = logData
        if info_dict.get("askType") == 10:
            logData.tradeInfo.gunNo = info_dict.get("dataArea").get("gunNo")
            logData.tradeInfo.preTradeNo = str_to_char(info_dict.get("dataArea").get("preTradeNo"))
            logData.tradeInfo.tradeNo = str_to_char(info_dict.get("dataArea").get("tradeNo"))
            logData.tradeInfo.vinCode = str_to_char(info_dict.get("dataArea").get("vinCode"))
            logData.tradeInfo.timeDivType = info_dict.get("dataArea").get("timeDivType")
            logData.tradeInfo.chargeStartTime = info_dict.get("dataArea").get("chargeStartTime")
            logData.tradeInfo.chargeEndTime = info_dict.get("dataArea").get("chargeEndTime")
            logData.tradeInfo.startSoc = info_dict.get("dataArea").get("startSoc")
            logData.tradeInfo.endSoc = info_dict.get("dataArea").get("endSoc")
            logData.tradeInfo.reason = info_dict.get("dataArea").get("reason")
            logData.tradeInfo.eleModelId = str_to_char(info_dict.get("dataArea").get("eleModelId"))
            logData.tradeInfo.serModelId = str_to_char(info_dict.get("dataArea").get("serModelId"))
            logData.tradeInfo.sumStart = info_dict.get("dataArea").get("sumStart")
            logData.tradeInfo.sumEnd = info_dict.get("dataArea").get("sumEnd")
            logData.tradeInfo.totalElect = info_dict.get("dataArea").get("totalElect")
            logData.tradeInfo.sharpElect = info_dict.get("dataArea").get("sharpElect")
            logData.tradeInfo.peakElect = info_dict.get("dataArea").get("peakElect")
            logData.tradeInfo.flatElect = info_dict.get("dataArea").get("flatElect")
            logData.tradeInfo.valleyElect = info_dict.get("dataArea").get("valleyElect")
            logData.tradeInfo.totalPowerCost = info_dict.get("dataArea").get("totalPowerCost")
            logData.tradeInfo.totalServCost = info_dict.get("dataArea").get("totalServCost")
            logData.tradeInfo.sharpPowerCost = info_dict.get("dataArea").get("sharpPowerCost")
            logData.tradeInfo.peakPowerCost = info_dict.get("dataArea").get("peakPowerCost")
            logData.tradeInfo.flatPowerCost = info_dict.get("dataArea").get("flatPowerCost")
            logData.tradeInfo.valleyPowerCost = info_dict.get("dataArea").get("valleyPowerCost")
            logData.tradeInfo.sharpServCost = info_dict.get("dataArea").get("sharpServCost")
            logData.tradeInfo.peakServCost = info_dict.get("dataArea").get("peakServCost")
            logData.tradeInfo.flatServCost = info_dict.get("dataArea").get("flatServCost")
            logData.tradeInfo.valleyServCost = info_dict.get("dataArea").get("valleyServCost")
            event_logQuery_Result.dataArea = logData
        if info_dict.get("askType") == 11:
            logData.meterData.gunNo = info_dict.get("dataArea").get("gunNo")
            logData.meterData.acqTime = str_to_char(info_dict.get("dataArea").get("acqTime"))
            logData.meterData.mailAddr = str_to_char(info_dict.get("dataArea").get("mailAddr"))
            logData.meterData.meterNo = str_to_char(info_dict.get("dataArea").get("meterNo"))
            logData.meterData.assetId = str_to_char(info_dict.get("dataArea").get("assetId"))
            logData.meterData.sumMeter = info_dict.get("dataArea").get("sumMeter")
            logData.meterData.lastTrade = str_to_char(info_dict.get("dataArea").get("lastTrade"))
            logData.meterData.elec = info_dict.get("dataArea").get("elec")
            event_logQuery_Result.dataArea = logData
        if info_dict.get("askType") == 14:
            logData.BMSData.gunNo = info_dict.get("dataArea").get("gunNo")
            logData.BMSData.preTradeNo = str_to_char(info_dict.get("dataArea").get("preTradeNo"))
            logData.BMSData.tradeNo = str_to_char(info_dict.get("dataArea").get("tradeNo"))
            logData.BMSData.socVal = info_dict.get("dataArea").get("socVal")
            logData.BMSData.BMSVer = info_dict.get("dataArea").get("BMSVer")
            logData.BMSData.BMSMaxVol = info_dict.get("dataArea").get("BMSMaxVol")
            logData.BMSData.batType = info_dict.get("dataArea").get("batType")
            logData.BMSData.batRatedCap = info_dict.get("dataArea").get("batRatedCap")
            logData.BMSData.batRatedTotalVol = info_dict.get("dataArea").get("batRatedTotalVol")
            logData.BMSData.singlBatMaxAllowVol = info_dict.get("dataArea").get("singlBatMaxAllowVol")
            logData.BMSData.maxAllowCur = info_dict.get("dataArea").get("maxAllowCur")
            logData.BMSData.battotalEnergy = info_dict.get("dataArea").get("battotalEnergy")
            logData.BMSData.maxVol = info_dict.get("dataArea").get("maxVol")
            logData.BMSData.maxTemp = info_dict.get("dataArea").get("maxTemp")
            logData.BMSData.batCurVol = info_dict.get("dataArea").get("batCurVol")
            event_logQuery_Result.dataArea = logData
        # print(f"event_logQuery_Result: {event_logQuery_Result}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_dev_config(json_str):
    try:
        info_dict = json.loads(json_str)
        event_dev_config.dev = str_to_char(info_dict.get("dev"))
        # print(f"event_dev_config: {event_dev_config}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_service_feedback_maintain_query(json_str):
    try:
        info_dict = json.loads(json_str)
        service_feedback_maintain_query.ctrlType = info_dict.get("ctrlType")
        service_feedback_maintain_query.result = info_dict.get("result")
        # print(f"service_feedback_maintain_query: {service_feedback_maintain_query}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

def set_event_ask_feeModel(json_str):
    try:
        info_dict = json.loads(json_str)
        event_ask_feeModel.gunNo = info_dict.get("gunNo")
        event_ask_feeModel.eleModelId = str_to_char(info_dict.get("eleModelId", ""))
        event_ask_feeModel.serModelId = str_to_char(info_dict.get("serModelId", ""))
        # print(f"event_ask_feeModel: {event_ask_feeModel}")
        return 0
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---json_data: {json_str}")
        # print(f"data_output---dict_data: {info_dict}")
        HSyslog.log_info(f"data_input---json_data: {json_str}. {e}")
        return -1

#---------------------------------------------------获取系统参数--------------------------------------------------------#


def get_device_meta():
    try:
        data = {
            "product_key": char_to_str(device_meta.product_key),
            "product_secret": char_to_str(device_meta.product_secret),
            "device_name": char_to_str(device_meta.device_name),
            "device_secret": char_to_str(device_meta.device_secret),
            "device_reg_code": char_to_str(device_meta.device_reg_code),
            "device_uid": char_to_str(device_meta.device_uid)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_fireware_info():
    try:
        data = {
            "simNo": char_to_str(event_fireware_info.simNo),
            "eleModelId": char_to_str(event_fireware_info.eleModelId),
            "serModelId": char_to_str(event_fireware_info.serModelId),
            "stakeModel": char_to_str(event_fireware_info.stakeModel),
            "vendorCode": event_fireware_info.vendorCode,
            "devSn": char_to_str(event_fireware_info.devSn),
            "devType": event_fireware_info.devType,
            "portNum": event_fireware_info.portNum,
            "simMac": char_to_str(event_fireware_info.simMac),
            "longitude": event_fireware_info.longitude,
            "latitude": event_fireware_info.latitude,
            "height": event_fireware_info.height,
            "gridType": event_fireware_info.gridType,
            "btMac": char_to_str(event_fireware_info.btMac),
            "meaType": event_fireware_info.meaType,
            "otRate": event_fireware_info.otRate,
            "otMinVol": event_fireware_info.otMinVol,
            "otMaxVol": event_fireware_info.otMaxVol,
            "otCur": event_fireware_info.otCur,
            #"inMeter":char_to_str(event_fireware_info.inMeter),
            #"outMeter":char_to_str(event_fireware_info.outMeter),
            "CT": event_fireware_info.CT,
            "isGateLock": event_fireware_info.isGateLock,
            "isGroundLock": event_fireware_info.isGroundLock
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_ver_info():
    try:
        data = {
            "devRegMethod": event_ver_info.devRegMethod,
            "pileSoftwareVer": char_to_str(event_ver_info.pileSoftwareVer),
            "pileHardwareVer": char_to_str(event_ver_info.pileHardwareVer),
            "sdkVer": char_to_str(event_ver_info.sdkVer)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_data_dev_config():
    try:
        data = {
            "equipParamFreq": data_dev_config.equipParamFreq,
            "gunElecFreq": data_dev_config.gunElecFreq,
            "nonElecFreq": data_dev_config.nonElecFreq,
            "faultWarnings": data_dev_config.faultWarnings,
            "acMeterFreq": data_dev_config.acMeterFreq,
            "dcMeterFreq": data_dev_config.dcMeterFreq,
            "offlinChaLen": data_dev_config.offlinChaLen,
            "grndLock": data_dev_config.grndLock,
            "doorLock": data_dev_config.doorLock,
            "encodeCon": data_dev_config.encodeCon,
            "qrCode": char_to_str(data_dev_config.qrCode)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_query_log():
    try:
        data = {
            "gunNo": service_query_log.gunNo,
            "startDate": service_query_log.startDate,
            "stopDate": service_query_log.stopDate,
            "askType": service_query_log.askType,
            "logQueryNo": char_to_str(service_query_log.logQueryNo)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_query_log():
    try:
        data = {
            "gunNo": service_feedback_query_log.gunNo,
            "startDate": service_feedback_query_log.startDate,
            "stopDate": service_feedback_query_log.stopDate,
            "askType": service_feedback_query_log.askType,
            "result": service_feedback_query_log.result,
            "logQueryNo": char_to_str(service_feedback_query_log.logQueryNo)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_dev_maintain():
    try:
        data = {"ctrlType": service_dev_maintain.ctrlType}
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_dev_maintain():
    try:
        data = {
            "ctrlType": service_feedback_dev_maintain.ctrlType,
            "reason": service_feedback_dev_maintain.reason
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_lockCtrl():
    try:
        data = {
            "gunNo": service_lockCtrl.gunNo,
            "lockParam": service_lockCtrl.lockParam
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_lockCtrl():
    try:
        data = {
            "gunNo": service_feedback_lockCtrl.gunNo,
            "lockStatus": service_feedback_lockCtrl.lockStatus,
            "resCode": service_feedback_lockCtrl.resCode
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_ask_feeModel():
    try:
        data = {
            "gunNo": event_ask_feeModel.gunNo,
            "eleModelId": char_to_str(event_ask_feeModel.eleModelId),
            "serModelId": char_to_str(event_ask_feeModel.serModelId)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_issue_feeModel():
    try:
        data = {
            "eleModelId": char_to_str(service_issue_feeModel.eleModelId),
            "serModelId": char_to_str(service_issue_feeModel.serModelId),
            "TimeNum": service_issue_feeModel.TimeNum,
            "TimeSeg": char_to_str(service_issue_feeModel.TimeSeg),
            "SegFlag": char_to_str(service_issue_feeModel.SegFlag),
            "chargeFee": char_to_str(service_issue_feeModel.chargeFee),
            "serviceFee": char_to_str(service_issue_feeModel.serviceFee)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_feeModel():
    try:
        data = {
            "eleModelId": char_to_str(service_feedback_feeModel.eleModelId),
            "serModelId": char_to_str(service_feedback_feeModel.serModelId),
            "result": service_feedback_feeModel.result
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_startCharge():
    try:
        data = {
            "gunNo": service_startCharge.gunNo,
            "preTradeNo": char_to_str(service_startCharge.preTradeNo),
            "tradeNo": char_to_str(service_startCharge.tradeNo),
            "startType": service_startCharge.startType,
            "chargeMode": service_startCharge.chargeMode,
            "limitData": service_startCharge.limitData,
            "stopCode": service_startCharge.stopCode,
            "startMode": service_startCharge.startMode,
            "insertGunTime": service_startCharge.insertGunTime
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_startCharge():
    try:
        data = {
            "gunNo": service_feedback_startCharge.gunNo,
            "preTradeNo": char_to_str(service_feedback_startCharge.preTradeNo),
            "tradeNo": char_to_str(service_feedback_startCharge.tradeNo)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_startResult():
    try:
        data = {
            "gunNo": event_startResult.gunNo,
            "preTradeNo": char_to_str(event_startResult.preTradeNo),
            "tradeNo": char_to_str(event_startResult.tradeNo),
            "startResult": event_startResult.startResult,
            "faultCode": event_startResult.faultCode,
            "vinCode": char_to_str(event_startResult.vinCode)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_startCharge():
    try:
        data = {
            "gunNo": event_startCharge.gunNo,
            "preTradeNo": char_to_str(event_startCharge.preTradeNo),
            "tradeNo": char_to_str(event_startCharge.tradeNo),
            "startType": event_startCharge.startType,
            "authCode": char_to_str(event_startCharge.authCode),
            "batterySOC": event_startCharge.batterySOC,
            "batteryCap": event_startCharge.batteryCap,
            "chargeTimes": event_startCharge.chargeTimes,
            "batteryVol": event_startCharge.batteryVol
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_authCharge():
    try:
        data = {
            "gunNo": service_authCharge.gunNo,
            "preTradeNo": char_to_str(service_authCharge.preTradeNo),
            "tradeNo": char_to_str(service_authCharge.tradeNo),
            "vinCode": char_to_str(service_authCharge.vinCode),
            "oppoCode": char_to_str(service_authCharge.oppoCode),
            "result": service_authCharge.result,
            "chargeMode": service_authCharge.chargeMode,
            "limitData": service_authCharge.limitData,
            "stopCode": service_authCharge.stopCode,
            "startMode": service_authCharge.startMode,
            "insertGunTime": service_authCharge.insertGunTime
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_authCharge():
    try:
        data = {
            "gunNo": service_feedback_authCharge.gunNo,
            "preTradeNo": char_to_str(service_feedback_authCharge.preTradeNo),
            "tradeNo": char_to_str(service_feedback_authCharge.tradeNo)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_stopCharge():
    try:
        data = {
            "gunNo": service_stopCharge.gunNo,
            "preTradeNo": char_to_str(service_stopCharge.preTradeNo),
            "tradeNo": char_to_str(service_stopCharge.tradeNo),
            "stopReason": service_stopCharge.stopReason
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_stopCharge():
    try:
        data = {
            "gunNo": service_feedback_stopCharge.gunNo,
            "preTradeNo": char_to_str(service_feedback_stopCharge.preTradeNo),
            "tradeNo": char_to_str(service_feedback_stopCharge.tradeNo)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_stopCharge():
    try:
        data = {
            "gunNo": event_stopCharge.gunNo,
            "preTradeNo": char_to_str(event_stopCharge.preTradeNo),
            "tradeNo": char_to_str(event_stopCharge.tradeNo),
            "stopResult": event_stopCharge.stopResult,
            "resultCode": event_stopCharge.resultCode,
            "stopFailReson": event_stopCharge.stopFailReson
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_tradeInfo():
    try:
        data = {
            "gunNo": event_tradeInfo.gunNo,
            "preTradeNo": char_to_str(event_tradeInfo.preTradeNo),
            "tradeNo": char_to_str(event_tradeInfo.tradeNo),
            "vinCode": char_to_str(event_tradeInfo.vinCode),
            "timeDivType": event_tradeInfo.timeDivType,
            "chargeStartTime": event_tradeInfo.chargeStartTime,
            "chargeEndTime": event_tradeInfo.chargeEndTime,
            "startSoc": event_tradeInfo.startSoc,
            "endSoc": event_tradeInfo.endSoc,
            "reason": event_tradeInfo.reason,
            "eleModelId": char_to_str(event_tradeInfo.eleModelId),
            "serModelId": char_to_str(event_tradeInfo.serModelId),
            "sumStart": event_tradeInfo.sumStart,
            "sumEnd": event_tradeInfo.sumEnd,
            "totalElect": event_tradeInfo.totalElect,
            "sharpElect": event_tradeInfo.sharpElect,
            "peakElect": event_tradeInfo.peakElect,
            "flatElect": event_tradeInfo.flatElect,
            "valleyElect": event_tradeInfo.valleyElect,
            "totalPowerCost": event_tradeInfo.totalPowerCost,
            "totalServCost": event_tradeInfo.totalServCost,
            "sharpPowerCost": event_tradeInfo.sharpPowerCost,
            "peakPowerCost": event_tradeInfo.peakPowerCost,
            "flatPowerCost": event_tradeInfo.flatPowerCost,
            "valleyPowerCost": event_tradeInfo.valleyPowerCost,
            "sharpServCost": event_tradeInfo.sharpServCost,
            "peakServCost": event_tradeInfo.peakServCost,
            "flatServCost": event_tradeInfo.flatServCost,
            "valleyServCost": event_tradeInfo.valleyServCost
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_confirmTrade():
    try:
        data = {
            "gunNo": service_confirmTrade.gunNo,
            "preTradeNo": char_to_str(service_confirmTrade.preTradeNo),
            "tradeNo": char_to_str(service_confirmTrade.tradeNo),
            "errcode": service_confirmTrade.errcode
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_alarm():
    try:
        data = {
            "gunNo": event_alarm.gunNo,
            "faultSum": event_alarm.faultSum,
            "warnSum": event_alarm.warnSum,
            "faultValue": char_to_str(event_alarm.faultValue),
            "warnValue": char_to_str(event_alarm.warnValue)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_server_rsvCharge():
    try:
        data = {
            "gunNo": service_rsvCharge.gunNo,
            "appomathod": service_rsvCharge.appomathod,
            "appoDelay": service_rsvCharge.appoDelay
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_rsvCharge():
    try:
        data = {
            "gunNo": service_feedback_rsvCharge.gunNo,
            "appomathod": service_feedback_rsvCharge.appomathod,
            "ret": service_feedback_rsvCharge.ret,
            "reason": service_feedback_rsvCharge.reason
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_groundLock_ctrl():
    try:
        data = {
            "gunNo": service_groundLock_ctrl.gunNo,
            "ctrlFlag": service_groundLock_ctrl.ctrlFlag
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_groundLock_ctrl():
    try:
        data = {
            "gunNo": service_feedback_groundLock_ctrl.gunNo,
            "reason": service_feedback_groundLock_ctrl.reason,
            "result": service_feedback_groundLock_ctrl.result
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_groundLock_change():
    try:
        data = {
            "gunNo": event_groundLock_change.gunNo,
            "lockState": event_groundLock_change.lockState,
            "powerType": event_groundLock_change.powerType,
            "cellState": event_groundLock_change.cellState,
            "lockerState": event_groundLock_change.lockerState,
            "lockerForced": event_groundLock_change.lockerForced,
            "lowPower": event_groundLock_change.lowPower,
            "soc": event_groundLock_change.soc,
            "openCnt": event_groundLock_change.openCnt
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_gateLock_ctrl():
    try:
        data = {
            "lockNo": service_gateLock_ctrl.lockNo,
            "ctrlFlag": service_gateLock_ctrl.ctrlFlag
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_gateLock_ctrl():
    try:
        data = {
            "lockNo": service_feedback_gateLock_ctrl.lockNo,
            "result": service_feedback_gateLock_ctrl.result
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_gateLock_change():
    try:
        data = {
            "lockNo": event_gateLock_change.lockNo,
            "lockState": event_gateLock_change.lockState
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_orderCharge():
    try:
        data = {
            "preTradeNo": char_to_str(service_orderCharge.preTradeNo),
            "num": service_orderCharge.num,
            "validTime": char_to_str(service_orderCharge.validTime),
            "kw": char_to_str(service_orderCharge.kw)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_orderCharge():
    try:
        data = {
            "preTradeNo": char_to_str(service_feedback_orderCharge.preTradeNo),
            "result": service_feedback_orderCharge.result,
            "reason": service_feedback_orderCharge.reason
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_pile_stutus_change():
    try:
        data = {
            "gunNo": event_pile_stutus_change.gunNo,
            "yxOccurTime": event_pile_stutus_change.yxOccurTime,
            "connCheckStatus": event_pile_stutus_change.connCheckStatus
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_event_car_info():
    try:
        data = {
            "gunNo": event_car_info.gunNo,
            "vinCode": char_to_str(event_car_info.vinCode),
            "batterySOC": event_car_info.batterySOC,
            "batteryCap": event_car_info.batteryCap,
            "state": event_car_info.state
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_property_dcPile():
    try:
        data = {
            "netType": property_dcPile.netType,
            "sigVal": property_dcPile.sigVal,
            "netId": property_dcPile.netId,
            "acVolA": property_dcPile.acVolA,
            "acCurA": property_dcPile.acCurA,
            "acVolB": property_dcPile.acVolB,
            "acCurB": property_dcPile.acCurB,
            "acVolC": property_dcPile.acVolC,
            "acCurC": property_dcPile.acCurC,
            "caseTemp": property_dcPile.caseTemp,
            "inletTemp": property_dcPile.inletTemp,
            "outletTemp": property_dcPile.outletTemp,
            "eleModelId": char_to_str(property_dcPile.eleModelId),
            "serModelId": char_to_str(property_dcPile.serModelId)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_property_BMS():
    try:
        data = {
            "gunNo": property_BMS.gunNo,
            "preTradeNo": char_to_str(property_BMS.preTradeNo),
            "tradeNo": char_to_str(property_BMS.tradeNo),
            "socVal": property_BMS.socVal,
            "BMSVer": property_BMS.BMSVer,
            "BMSMaxVol": property_BMS.BMSMaxVol,
            "batType": property_BMS.batType,
            "batRatedCap": property_BMS.batRatedCap,
            "batRatedTotalVol": property_BMS.batRatedTotalVol,
            "singlBatMaxAllowVol": property_BMS.singlBatMaxAllowVol,
            "maxAllowCur": property_BMS.maxAllowCur,
            "battotalEnergy": property_BMS.battotalEnergy,
            "maxVol": property_BMS.maxVol,
            "maxTemp": property_BMS.maxTemp,
            "batCurVol": property_BMS.batCurVol
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_property_dc_work():
    try:
        data = {
            "gunNo": property_dc_work.gunNo,
            "workStatus": property_dc_work.workStatus,
            "gunStatus": property_dc_work.gunStatus,
            "eLockStatus": property_dc_work.eLockStatus,
            "DCK1Status": property_dc_work.DCK1Status,
            "DCK2Status": property_dc_work.DCK2Status,
            "DCPlusFuseStatus": property_dc_work.DCPlusFuseStatus,
            "DCMinusFuseStatus": property_dc_work.DCMinusFuseStatus,
            "preTradeNo": char_to_str(property_dc_work.preTradeNo),
            "tradeNo": char_to_str(property_dc_work.tradeNo),
            "conTemp1": property_dc_work.conTemp1,
            "conTemp2": property_dc_work.conTemp2,
            "dcVol": property_dc_work.dcVol,
            "dcCur": property_dc_work.dcCur,
            "chgType": property_dc_work.chgType,
            "realPower": property_dc_work.realPower,
            "chgTime": property_dc_work.chgTime,
            "socVal": property_dc_work.socVal,
            "needVol": property_dc_work.needVol,
            "needCur": property_dc_work.needCur,
            "chargeMode": property_dc_work.chargeMode,
            "bmsVol": property_dc_work.bmsVol,
            "bmsCur": property_dc_work.bmsCur,
            "SingleMHV": property_dc_work.SingleMHV,
            "remainT": property_dc_work.remainT,
            "MHTemp": property_dc_work.MHTemp,
            "MLTemp": property_dc_work.MLTemp,
            "totalElect": property_dc_work.totalElect,
            "sharpElect": property_dc_work.sharpElect,
            "peakElect": property_dc_work.peakElect,
            "flatElect": property_dc_work.flatElect,
            "valleyElect": property_dc_work.valleyElect,
            "totalCost": property_dc_work.totalCost,
            "totalPowerCost": property_dc_work.totalPowerCost,
            "totalServCost": property_dc_work.totalServCost
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_property_dc_nonWork():
    try:
        data = {
            "gunNo": property_dc_nonWork.gunNo,
            "workStatus": property_dc_nonWork.workStatus,
            "gunStatus": property_dc_nonWork.gunStatus,
            "eLockStatus": property_dc_nonWork.eLockStatus,
            "DCK1Status": property_dc_nonWork.DCK1Status,
            "DCK2Status": property_dc_nonWork.DCK2Status,
            "DCPlusFuseStatus": property_dc_nonWork.DCPlusFuseStatus,
            "DCMinusFuseStatus": property_dc_nonWork.DCMinusFuseStatus,
            "conTemp1": property_dc_nonWork.conTemp1,
            "conTemp2": property_dc_nonWork.conTemp2,
            "dcVol": property_dc_nonWork.dcVol,
            "dcCur": property_dc_nonWork.dcCur
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_property_dc_input_meter():
    try:
        data = {
            "gunNo": property_dc_input_meter.gunNo,
            "acqTime": char_to_str(property_dc_input_meter.acqTime),
            "mailAddr": char_to_str(property_dc_input_meter.mailAddr),
            "meterNo": char_to_str(property_dc_input_meter.meterNo),
            "assetId": char_to_str(property_dc_input_meter.assetId),
            "sumMeter": property_dc_input_meter.sumMeter,
            "ApElect": property_dc_input_meter.ApElect,
            "BpElect": property_dc_input_meter.BpElect,
            "CpElect": property_dc_input_meter.CpElect
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_property_meter():
    try:
        data = {
            "gunNo": property_meter.gunNo,
            "acqTime": char_to_str(property_meter.acqTime),
            "mailAddr": char_to_str(property_meter.mailAddr),
            "meterNo": char_to_str(property_meter.meterNo),
            "assetId": char_to_str(property_meter.assetId),
            "sumMeter": property_meter.sumMeter,
            "lastTrade": char_to_str(property_meter.lastTrade),
            "elec": property_meter.elec
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""


def get_event_logQuery_Result():
    try:
        data = {
            "gunNo": event_logQuery_Result.gunNo,
            "startDate": event_logQuery_Result.startDate,
            "stopDate": event_logQuery_Result.stopDate,
            "askType": event_logQuery_Result.askType,
            "result": event_logQuery_Result.result,
            "logQueryNo": char_to_str(event_logQuery_Result.logQueryNo),
            "retType": event_logQuery_Result.retType,
            "logQueryEvtSum": event_logQuery_Result.logQueryEvtSum,
            "logQueryEvtNo": event_logQuery_Result.logQueryEvtNo,
            "dataArea": event_logQuery_Result.dataArea
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_device_code():
    try:
        data = {
            "device_code": char_to_str(device_meta.device_reg_code)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_device_uid():
    try:
        data = {
            "device_uid": char_to_str(device_meta.device_uid)
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

def get_service_feedback_maintain_query():
    try:
        data = {
            "ctrlType": service_feedback_maintain_query.ctrlType,
            "result": service_feedback_maintain_query.result
        }
        data_json = json.dumps(data)
        # print(data_json)
        return data_json
    except Exception as e:
        # print(red_char + f"{e}" + init_char)
        # print(f"data_input---dict_data: {dev_meta_info_t}")
        # print(f"data_output---dict_data: {data_json}")
        HSyslog.log_info(f"data_input---json_data: {data_json}. {e}")
        return ""

