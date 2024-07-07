import HDevice
import HPlatform

from concurrent.futures import ThreadPoolExecutor, TimeoutError


def Htool_send_totalFaultEvt(info):
    HPlatform.send_totalFaultEvt(info)


def Htool_send_dcStChEvt(info):
    HPlatform.send_dcStChEvt(info)


def Htool_send_startChaResEvt(data):
    HPlatform.send_startChaResEvt(data)


def Htool_send_stopChaResEvt(data):
    HPlatform.send_stopChaResEvt(data)


def Htool_orderUpdateEvt(info):
    HPlatform.send_orderUpdateEvt(info)


def Htool_send_askFeeModelEvt(info):
    HPlatform.send_askFeeModelEvt(info)


def Htool_app_set_parameters(info):
    HDevice.app_set_parameters(info)


def Htool_app_charge_rate_sync_message(info_dict):
    HDevice.app_charge_rate_sync_message(info_dict)


def Htool_app_charge_control(info_dict):
    HDevice.app_charge_control(info_dict)


def Htool_app_charge_record_response(info_dict):
    HDevice.app_charge_record_response(info_dict)


def Htool_app_QR_code_update(info_qrCode):
    HDevice.app_QR_code_update(info_qrCode)


def Htool_app_upgrade_control(info):
    HDevice.app_upgrade_control(info)


def Htool_app_time_sync(info_dict):
    HDevice.app_time_sync(info_dict)


def Htool_send_startChargeAuthEvt(info):
    HPlatform.send_startChargeAuthEvt(info)


def Htool_plamform_event(info_id, info):
    HPlatform.plamform_event(info_id, info)


def Htool_plamform_property(info_id, info):
    HPlatform.plamform_property(info_id, info)


def Htool_app_set_parameter_response():
    return HDevice.app_set_parameter_response


def Htool_app_charge_rate_sync_response():
    return HDevice.app_charge_rate_sync_response


def Htool_app_QR_code_update_response():
    return HDevice.app_QR_code_update_response


def Htool_app_fetch_parameter(get_data):
    HDevice.app_fetch_parameter(get_data)


def Htool_app_read_version_number(get_data):
    HDevice.app_read_version_number(get_data)


def Htool_app_charge_rate_request_response(result):
    HDevice.app_charge_rate_request_response(result)
