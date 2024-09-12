import json
import sqlite3
from datetime import *

cdef extern from r"output/release/include/infra_types.h":
    ctypedef unsigned short uint16_t
    ctypedef unsigned int uint32_t
    ctypedef unsigned char uint8_t
    ctypedef unsigned int uintptr_t

cdef extern from "string.h":
    char* strncpy(char *dest, const char *src, size_t n)
    size_t strlen(const char *_Str)

cdef extern from r"output/release/include/protocol_data_def.h":
    ctypedef struct evs_device_meta:
        char product_key[20 + 1]			#设备品类标识字符串
        char product_secret[64 + 1]	        #设备品类密钥
        char device_name[32 + 1]			#某台设备的标识字符串:未注册前为设备出厂编号（16位长度），注册后为设备在物联管理平台的资产码（24位长度）
        char device_secret[64 + 1]		    #某台设备的设备密钥
        char device_reg_code[64 + 1]        #某台设备的设备注册码
        char device_uid[16 + 1]		        #某台设备的出厂编号

    ctypedef enum evs_cmd_event_enum:
        EVS_CMD_EVENT_FIREWARE_INFO = 0
        EVS_CMD_EVENT_ASK_FEEMODEL
        EVS_CMD_EVENT_STARTCHARGE
        EVS_CMD_EVENT_STARTRESULT
        EVS_CMD_EVENT_STOPCHARGE
        EVS_CMD_EVENT_TRADEINFO
        EVS_CMD_EVENT_ALARM
        EVS_CMD_EVENT_ACPILE_CHANGE
        EVS_CMD_EVENT_DCPILE_CHANGE
        EVS_CMD_EVENT_GROUNDLOCK_CHANGE
        EVS_CMD_EVENT_GATELOCK_CHANGE
        EVS_CMD_EVENT_ASK_DEV_CONFIG
        EVS_CMD_EVENT_CAR_INFO
        EVS_CMD_EVENT_VER_INFO
        EVS_CMD_EVENT_LOGQUERY_RESULT

    ctypedef enum evs_cmd_property_enum:
        EVS_CMD_PROPERTY_DCPILE = 0
        EVS_CMD_PROPERTY_ACPILE
        EVS_CMD_PROPERTY_AC_WORK
        EVS_CMD_PROPERTY_AC_NONWORK
        EVS_CMD_PROPERTY_DC_WORK
        EVS_CMD_PROPERTY_DC_NONWORK
        EVS_CMD_PROPERTY_DC_OUTMETER
        EVS_CMD_PROPERTY_AC_OUTMETER
        EVS_CMD_PROPERTY_BMS
        EVS_CMD_PROPERTY_DC_INPUT_METER

    #固件信息上报事件参数
    ctypedef struct evs_event_fireware_info:
        char simNo[24]							# 1		SIM卡号
        char eleModelId[16 + 1]				    # 2		电费计费模型编号
        char serModelId[16 + 1]					# 3		服务费模型编号
        char stakeModel[20]				        # 4		充电桩型号
        uint32_t vendorCode				        # 5		生产厂商编码
        char devSn[16 + 1]						# 6		出厂编号#字符串
        uint8_t devType				            # 7		桩类型
        uint8_t portNum				            # 8		充电接口数量
        char simMac[32 + 1]						# 9		网络MAC地址#字符串
        uint32_t longitude				        # 10		经度
        uint32_t latitude				        # 11		纬度
        uint32_t height					        # 12		高度
        uint32_t gridType				        # 13		坐标类型
        char btMac[32 + 1]						# 14		系统时钟字符串
        uint8_t meaType				            # 15		蓝牙MAC地址
        uint32_t otRate					        # 16		计量方式
        uint32_t otMinVol				        # 17		额定功率
        uint32_t otMaxVol				        # 18		输出最大电压
        uint32_t otCur					        # 19		输出最大电流
        char inMeter[0][8]                     # 20		交流输入电表地址#压缩BCD
        char outMeter[24][8]	                # 21		计量用电能表地址#压缩BCD
        uint32_t CT						        # 22		电流互感器系数 默认值1
        uint8_t isGateLock			            # 23		是否有智能门锁
        uint8_t isGroundLock			        # 24		是否有地锁

    #设备版本信息
    ctypedef struct evs_event_ver_info:
        uint8_t devRegMethod		            # 1		设备注册方式
        char pileSoftwareVer[255 + 1]           # 2		充电桩软件版本号
        char pileHardwareVer[255 + 1]           # 3		充电桩硬件版本号
        char sdkVer[255 + 1]			        # 4		SDK版本号
    
    #设备配置数据
    ctypedef struct evs_data_dev_config:
        uint32_t equipParamFreq					# 1		充电设备实时监测属性上报频率
        uint32_t gunElecFreq					# 2		充电枪充电中实时监测属性上报频率
        uint32_t nonElecFreq					# 2		充电枪非充电中实时监测属性上报频率
        uint32_t faultWarnings					# 3		故障告警全信息上传频率
        uint32_t acMeterFreq					# 4		充电设备交流电表底值监测属性上报频率
        uint32_t dcMeterFreq					# 5		直流输出电表底值监测属性上报频率
        uint32_t offlinChaLen					# 6		离线后可充电时长
        uint32_t grndLock						# 7		地锁监测上送频率
        uint32_t doorLock						# 8		网门锁监测上送频率
        uint32_t encodeCon						# 9		报文加密
        char qrCode[24][256]                     # 10	二维码数据
     
    #设备日志查询服务下发参数
    ctypedef struct evs_service_query_log:
        uint8_t gunNo				# 枪号	gunNo
        uint32_t startDate			# 查询起始时间戳	startDate
        uint32_t stopDate			# 查询终止时间戳	stopDate
        uint8_t askType			    # 查询类型	askType
        char logQueryNo[38 + 1]     # 查询流水号
     
    #日志查询服务回复参数
    ctypedef struct evs_service_feedback_query_log:
        uint8_t gunNo				# 1	枪号
        uint32_t startDate			# 2	查询起始时间
        uint32_t stopDate			# 3	查询终止时间
        uint8_t askType			    # 4	查询类型
        uint8_t result			    # 5	响应结果
        char logQueryNo[38 + 1]     # 6	查询流水号
     
    #设备维护指令服务下发参数
    ctypedef struct evs_service_dev_maintain:
        uint8_t ctrlType          # 控制类型
     
    #设备维护指令服务回复参数
    ctypedef struct evs_service_feedback_dev_maintain:
        uint8_t ctrlType          # 1	当前控制类型
        uint32_t reason	          # 2	失败原因
     
    #设备维护状态查询服务回复参数
    ctypedef struct evs_service_feedback_maintain_query:  
        uint8_t ctrlType        # 1		当前类型
        uint8_t result	        # 2		查询结果
     
    # 充电枪电子锁控制服务下发参数
    ctypedef struct evs_service_lockCtrl:
        uint8_t gunNo	        # 1	充电枪编号
        uint8_t lockParam       # 2	控制
     
    #充电枪电子锁控制服务回复参数
    ctypedef struct evs_service_feedback_lockCtrl:
        uint8_t gunNo	        # 1	充电枪编号
        uint8_t lockStatus      # 2	电子锁状态
        uint32_t resCode	    # 3	结果
     
    # 计费模型请求事件
    ctypedef struct evs_event_ask_feeModel:
        uint8_t gunNo			            # 1	充电枪编号
        char eleModelId[16 + 1]             # 2	电费计费模型编号
        char serModelId[16 + 1]             # 2	服务费模型编号
     
    #计费模型更新服务下发参数
    ctypedef struct evs_service_issue_feeModel:
        char eleModelId[16 + 1]             # 1		电费计费模型编号
        char serModelId[16 + 1]             # 2		服务费模型编号
        uint8_t TimeNum		                # 3		电费模型时段数N 取值范围：1—14
        char TimeSeg[48][5]                 # 4		电费模型时段开始时间点
        uint32_t SegFlag[48]                # 5		电费模型时段标志
        uint32_t chargeFee[4]		        # 6		电费模型
        uint32_t serviceFee[4]	            # 7 	服务费费模型
     
    #计费模型更新结果设备回复参数
    ctypedef struct evs_service_feedback_feeModel:
        char eleModelId[16 + 1]         # 1		电费计费模型编号
        char serModelId[16 + 1]         # 2		服务费模型编号
        uint8_t result	                # 3		失败原因
     
    #远程启动充电服务下发参数
    ctypedef struct evs_service_startCharge:
        uint8_t gunNo				            # 1	充电枪编号
        char preTradeNo[40 + 1]                 # 2	平台交易流水号
        char tradeNo[40 + 1]	                # 3	设备交易流水号
        uint8_t startType			            # 4	启动方式
        uint8_t chargeMode		                # 5	充电模式
        uint32_t limitData			            # 6	限制值
        uint32_t stopCode			            # 7	停机码
        uint8_t startMode			            # 8	启动模式
        uint32_t insertGunTime		            # 10插枪事件时间戳
     
    #启动充电服务设备回复参数
    ctypedef struct evs_service_feedback_startCharge:
        uint8_t gunNo				            # 1	充电枪编号
        char preTradeNo[40 + 1]                 # 2	平台交易流水号
        char tradeNo[40 + 1]	                # 3	设备交易流水号
     
    #启动充电结果事件参数
    ctypedef struct evs_event_startResult:
        uint8_t gunNo				            # 1	充电枪编号
        char preTradeNo[40 + 1]                 # 2	平台交易流水号
        char tradeNo[40 + 1]	                # 3	设备交易流水号
        uint8_t startResult		                # 4	启动结果
        uint32_t faultCode			            # 5	故障代码
        char vinCode[17 + 1]	                # 6	vin码
     
    #启动充电鉴权事件参数
    ctypedef struct evs_event_startCharge:
        uint8_t gunNo				            # 1	充电枪编号
        char preTradeNo[40 + 1]                 # 2	平台交易流水号
        char tradeNo[40 + 1]	                # 3	设备交易流水号
        uint8_t startType			            # 4	启动方式
        char authCode[17 + 1]                   # 5	鉴权码 若启动方式为反向扫码，填入二维码信息；若为即插即充则为VIN码。
        uint8_t batterySOC		                # 6	电池SOC
        uint32_t batteryCap			            # 7	电车容量
        uint32_t chargeTimes		            # 8	已充电次数
        uint32_t batteryVol			            # 9	当前电池电压
     
    #鉴权充电服务下发参数
    ctypedef struct evs_service_authCharge:
        uint8_t gunNo				# 1	充电枪编号
        char preTradeNo[40 + 1]     # 2	平台交易流水号
        char tradeNo[40 + 1]	    # 3	设备交易流水号
        char vinCode[17 + 1]	    # 4	填VIN信息。
        char oppoCode[256]	        # 5	若启动方式为反向扫码，填入二维码信息；若无则为空。
        uint8_t result			    # 6	鉴权结果
        uint8_t chargeMode		    # 7	充电模式
        uint32_t limitData			# 8	限制值
        uint32_t stopCode			# 9	停机码
        uint8_t startMode			# 10	启动模式
        uint32_t insertGunTime		# 11	插枪事件时间戳
     
    #鉴权启动充电服务设备回复参数
    ctypedef struct evs_service_feedback_authCharge:
        uint8_t gunNo				            # 1	充电枪编号
        char preTradeNo[40 + 1]                 # 2	平台交易流水号
        char tradeNo[40 + 1]	                # 3	设备交易流水号
     
    #远程停止充电服务下发参数
    ctypedef struct evs_service_stopCharge:
        uint8_t gunNo				            # 1	充电枪编号
        char preTradeNo[40 + 1]                 # 2	平台交易流水号
        char tradeNo[40 + 1]	                # 3	设备交易流水号
        uint8_t stopReason		                # 4	停止原因
     
    #远程停止充电服务设备回复参数
    ctypedef struct evs_service_feedback_stopCharge:
        uint8_t gunNo				            # 1	充电枪编号
        char preTradeNo[40 + 1]                 # 2	平台交易流水号
        char tradeNo[40 + 1]	                # 3	设备交易流水号
     
    #停止充电结果事件上传参数
    ctypedef struct evs_event_stopCharge:
        uint8_t gunNo				            # 1	充电枪编号
        char preTradeNo[40 + 1]                 # 2	平台交易流水号
        char tradeNo[40 + 1]	                # 3	设备交易流水号
        uint8_t stopResult		                # 4	停止结果
        uint32_t resultCode			            # 5	停止原因
        uint8_t stopFailReson		            # 6	停止失败原因
     
    #交易记录事件上传参数
    ctypedef struct evs_event_tradeInfo:
        uint8_t gunNo				    # 1	充电枪编号
        char preTradeNo[40 + 1]	        # 2	平台交易流水号
        char tradeNo[40 + 1]	        # 3	设备交易流水号
        char vinCode[17 + 1]	        # 4	VIN
        uint8_t timeDivType			    # 5	计量计费类型
        uint32_t chargeStartTime		# 6	开始充电时间
        uint32_t chargeEndTime			# 7	结束充电时间
        uint8_t startSoc				# 8	启动时SOC
        uint8_t endSoc				    # 9	停止时SOC
        uint32_t reason				    # 10	停止充电原因
        char eleModelId[16 + 1]         # 11	计量计费模型编号
        char serModelId[16 + 1]         # 11	计量计费模型编号
        uint32_t sumStart				# 12	电表总起示值
        uint32_t sumEnd				    # 13	电表总止示值
        uint32_t totalElect			    # 14	总电量
        uint32_t sharpElect			    # 15	尖电量
        uint32_t peakElect				# 16	峰电量
        uint32_t flatElect				# 17	平电量
        uint32_t valleyElect			# 18	谷电量
        uint32_t totalPowerCost		    # 19	总电费
        uint32_t totalServCost			# 20	总服务费
        uint32_t sharpPowerCost		    # 21	尖电费
        uint32_t peakPowerCost			# 22	峰电费
        uint32_t flatPowerCost			# 23	平电费
        uint32_t valleyPowerCost		# 24	谷电费
        uint32_t sharpServCost			# 25	尖服务费
        uint32_t peakServCost			# 26	峰服务费
        uint32_t flatServCost			# 27	平服务费
        uint32_t valleyServCost		    # 28	谷服务费
     
    #交易记录确认服务下发参数
    ctypedef struct evs_service_confirmTrade:
        uint8_t gunNo				# 1	充电枪编号
        char preTradeNo[40 + 1]     # 2	平台交易流水号
        char tradeNo[40 + 1]	    # 3	设备交易流水号
        uint8_t errcode			    # 4	交易记录上传结果
     
    #故障告警事件上传参数
    ctypedef struct evs_event_alarm:
        uint8_t gunNo			    # 1	枪编号
        uint16_t faultSum			# 2	故障总
        uint16_t warnSum			# 3	告警总
        uint16_t faultValue[50]      # 4	故障点数据
        uint16_t warnValue[50]       # 5	告警点数据
     
    #预约充电服务下发参数
    ctypedef struct evs_service_rsvCharge:
        uint8_t gunNo	        # 1	充电枪编号
        uint8_t appomathod      # 2	预约方式 10：立即预约 11：取消预约
        uint16_t appoDelay      # 3	预约等候时长  分钟数，大于0，且不大于1440
     
    #预约充电服务设备回复参数
    ctypedef struct evs_service_feedback_rsvCharge:
        uint8_t gunNo	        # 1	充电枪编号
        uint8_t appomathod      # 2	预约方式
        uint8_t ret		        # 3	预约结果
        uint8_t reason	        # 4	失败原因
      
    #地锁控制服务下发参数
    ctypedef struct evs_service_groundLock_ctrl:
        uint8_t gunNo	        # 1	充电枪编号
        uint8_t ctrlFlag        # 2	控制指令
     
    #地锁控制服务回复参数
    ctypedef struct evs_service_feedback_groundLock_ctrl:
        uint8_t gunNo         # 1	充电枪编号
        uint8_t result        # 2	控制结果
        uint8_t reason        # 3	失败原因
     
    #地锁状态变化事件上传参数
    ctypedef struct evs_event_groundLock_change:
        uint8_t gunNo		    # 1	充电枪编号
        uint8_t lockState	    # 2	地锁状态
        uint8_t powerType	    # 3	供电方式
        uint8_t cellState	    # 4	电池状态
        uint8_t lockerState	    # 5	锁舌状态
        uint8_t lockerForced    # 6	锁舌受外力强制动作
        uint8_t lowPower		# 7	电池低电量报警
        uint8_t soc			    # 8	电池SOC
        uint32_t openCnt		# 9	开闭次数
     
    #智能门锁控制服务下发参数
    ctypedef struct evs_service_gateLock_ctrl:
        uint8_t lockNo	        # 1	门锁编号
        uint8_t ctrlFlag        # 2	控制指令
     
    #智能门锁控制服务回复参数
    ctypedef struct evs_service_feedback_gateLock_ctrl:
        uint8_t lockNo          # 1	充电枪编号
        uint8_t result          # 2	控制结果
     
    #智能门锁状态变化事件上传参数
    ctypedef struct evs_event_gateLock_change:
        uint8_t lockNo	        # 1	充电枪编号
        uint8_t lockState       # 2	智能门锁状态
     
    #有序充电策略服务下发参数
    ctypedef struct evs_service_orderCharge:
        char preTradeNo[40 + 1]		# 1	订单流水号
        uint8_t num			        # 2	策略配置时间段数量
        uint8_t validTime[24][5]    # 3	策略生效时间#字符串数组。时间格式采用HHMM，24小时制。策略范围24小时内最多五段 例如 ：[time1,time2,time3…]。
        uint16_t kw[24]		        # 4	策略配置功率#整型数组。功率精确到0.1KW[kw1,kw2,kw3…]

    #有序充电策略服务设备回复参数
    ctypedef struct evs_service_feedback_orderCharge:
        char preTradeNo[40 + 1]     # 1	订单流水号
        uint8_t result				# 2	返回结果
        uint8_t reason				# 3	失败原因
     
    #交直流充电设备枪状态变化事件上传参数
    ctypedef struct evs_event_pile_stutus_change:
        uint8_t gunNo		        # 1	充电枪编号
        uint32_t yxOccurTime	    # 2	发生时刻
        uint8_t connCheckStatus     # 3	变位点数据
     
    #交直流充电设备充电前车辆信息上报事件上传参数
    ctypedef struct evs_event_car_info:
        uint8_t gunNo			    # 1	充电枪编号
        uint8_t batterySOC	        # 2	电池SOC
        uint32_t batteryCap		    # 3	电车容量
        char vinCode[17 + 1]        # 4	vin码
        uint8_t state			    # 5	获取车辆信息状态
     
 #/*********************************************交流业务相关************************************************************/
    
    #交流设备属性上报参数
    ctypedef struct evs_property_acPile:
        uint8_t netType			        # 1	网络类型
        uint8_t sigVal			        # 2	网络信号等级
        uint8_t netId				    # 3	网络运营商
        uint32_t acVolA				    # 4	A相采集电压
        uint32_t acCurA				    # 5	A相采集电流
        uint32_t acVolB				    # 6	B相采集电压
        uint32_t acCurB				    # 7	B相采集电流
        uint32_t acVolC				    # 8	C相采集电压
        uint32_t acCurC				    # 9	C相采集电流
        uint16_t caseTemp			    # 10 桩内温度
        char eleModelId[16 + 1]         # 11 电费计费模型编号
        char serModelId[16 + 1]         # 12 服务费模型编号
     
    #交流充电枪充电中实时监测属性
    ctypedef struct evs_property_ac_work:
        uint8_t gunNo				    # 1	充电枪编号
        uint8_t workStatus			    # 3	工作状态
        uint8_t conStatus			    # 4	连接确认开关状态
        uint8_t outRelayStatus		    # 5	输出继电器状态
        uint8_t eLockStatus			    # 6	充电接口电子锁状态
        uint16_t gunTemp				# 7	充电枪头温度
        uint32_t acVolA				    # 8	充电设备A相输出电压
        uint32_t acCurA				    # 9	充电设备A相输出电流
        uint32_t acVolB				    # 10	充电设备B相输出电压
        uint32_t acCurB				    # 11	充电设备B相输出电流
        uint32_t acVolC				    # 12	充电设备C相输出电压
        uint32_t acCurC				    # 13	充电设备C相输出电流
        char preTradeNo[40 + 1]         # 14	平台交易流水号
        char tradeNo[40 + 1]	        # 15	设备交易流水号
        uint32_t realPower				# 16	充电实际功率
        uint32_t chgTime				# 17	累计充电时间
        uint32_t totalElect			    # 18	总电量
        uint32_t sharpElect			    # 19	尖电量
        uint32_t peakElect				# 20	峰电量
        uint32_t flatElect				# 21	平电量
        uint32_t valleyElect			# 22	谷电量
        uint32_t totalCost				# 23	总金额
        uint32_t totalPowerCost		    # 24	总电费
        uint32_t totalServCost			# 25	总服务费
        uint32_t PwmDutyRadio			# 26	PWM占空比
     
    #交流充电枪非充电中实时监测属性
    ctypedef struct evs_property_ac_nonWork:
        uint8_t gunNo		        # 1	充电枪编号
        uint8_t workStatus	        # 3	工作状态
        uint8_t conStatus	        # 4	连接确认开关状态
        uint8_t outRelayStatus      # 5	输出继电器状态
        uint8_t eLockStatus	        # 6	充电接口电子锁状态
        uint16_t gunTemp		    # 7	充电枪头温度
        uint32_t acVolA		        # 8	充电设备A相输出电压
        uint32_t acCurA		        # 9	充电设备A相输出电流
        uint32_t acVolB		        # 10	充电设备B相输出电压
        uint32_t acCurB		        # 11	充电设备B相输出电流
        uint32_t acVolC		        # 12	充电设备C相输出电压
        uint32_t acCurC		        # 13	充电设备C相输出电流
     
#/*********************************************直流业务相关************************************************************/

    #直流设备属性上报参数
    ctypedef struct evs_property_dcPile:
        uint8_t netType				    # 1	网络类型
        uint8_t sigVal				    # 2	网络信号等级
        uint8_t netId				    # 3	网络运营商
        uint32_t acVolA				    # 4	A相采集电压
        uint32_t acCurA				    # 5	A相采集电流
        uint32_t acVolB				    # 6	B相采集电压
        uint32_t acCurB				    # 7	B相采集电流
        uint32_t acVolC				    # 8	C相采集电压
        uint32_t acCurC				    # 9	C相采集电流
        uint16_t caseTemp			    # 10 设备内温度
        uint16_t inletTemp			    # 11 设备入风口温度
        uint16_t outletTemp			    # 12 设备出风口温度
        char eleModelId[16 + 1]         # 13 电费模型编号
        char serModelId[16 + 1]         # 14 服务费模型编号
     
    #直流充电枪BMS监测属性
    ctypedef struct evs_property_BMS:
        uint8_t gunNo				    # 1	充电枪编号
        char preTradeNo[40 + 1]         # 2	平台交易流水号
        char tradeNo[40 + 1]	        # 3	设备交易流水号
        uint8_t socVal				    # 4	SOC
        uint8_t BMSVer				    # 5	BMS通信协议版本号
        uint16_t BMSMaxVol			    # 6	最高允许充电总电压
        uint8_t batType				    # 7	电池类型
        uint16_t batRatedCap		    # 8	整车动力蓄电池额定容量
        uint16_t batRatedTotalVol	    # 9	整车动力蓄电池额定总电压
        uint16_t singlBatMaxAllowVol    # 10	单体动力蓄电池最高允许充电电压
        uint16_t maxAllowCur			# 11	最高允许充电电流
        uint16_t battotalEnergy		    # 12	整车动力蓄电池标称总能量
        uint16_t maxVol				    # 13	最高允许充电总电压
        uint16_t maxTemp				# 14	最高允许温度
        uint16_t batCurVol			    # 15	整车动力蓄电池当前电池电压
     
    #直流充电枪充电中实时监测属性
    ctypedef struct evs_property_dc_work:
        uint8_t gunNo				    # 充电枪编号
        uint8_t workStatus			    # 工作状态
        uint8_t gunStatus			    # 充电枪连接状态
        uint8_t eLockStatus			    # 充电枪电子锁状态
        uint8_t DCK1Status			    # 直流输出接触器K1状态
        uint8_t DCK2Status			    # 直流输出接触器K2状态
        uint8_t DCPlusFuseStatus		# DC+熔断器状态
        uint8_t DCMinusFuseStatus	    # DC-熔断器状态
        uint16_t conTemp1			    # 充电接口DC+温度
        uint16_t conTemp2			    # 充电接口DC-温度
        uint32_t dcVol					# 输出电压
        uint32_t dcCur					# 输出电流
        char preTradeNo[40 + 1]         # 平台交易流水号
        char tradeNo[40 + 1]	        # 设备交易流水号
        uint8_t chgType				    # 充电类型
        uint32_t realPower				# 充电设备输出功率
        uint32_t chgTime				# 累计充电时间
        uint8_t socVal				    # SOC
        uint16_t needVol				# 充电需求电压
        uint16_t needCur				# 充电需求电流
        uint8_t chargeMode			    # 充电模式
        uint16_t bmsVol				    # BMS充电电压测量值
        uint16_t bmsCur				    # BMS充电电流测量值
        uint16_t SingleMHV			    # 最高单体动力蓄电池电压
        uint16_t remainT				# 估算充满剩余充电时间
        uint16_t MHTemp				    # 最高动力蓄电池温度
        uint16_t MLTemp				    # 最低动力蓄电池温度
        uint32_t totalElect			    # 总电量
        uint32_t sharpElect			    # 尖电量
        uint32_t peakElect				# 峰电量
        uint32_t flatElect				# 平电量
        uint32_t valleyElect			# 谷电量
        uint32_t totalCost				# 总金额
        uint32_t totalPowerCost		    # 总电费
        uint32_t totalServCost			# 总服务费
     
    #直流充电枪非充电中实时监测属性
    ctypedef struct evs_property_dc_nonWork:
        uint8_t gunNo			        # 充电枪编号
        uint8_t workStatus		        # 工作状态
        uint8_t gunStatus		        # 充电枪连接状态
        uint8_t eLockStatus		        # 充电枪电子锁状态
        uint8_t DCK1Status		        # 直流输出接触器K1状态
        uint8_t DCK2Status		        # 直流输出接触器K2状态
        uint8_t DCPlusFuseStatus	    # DC+熔断器状态
        uint8_t DCMinusFuseStatus       # DC-熔断器状态
        uint16_t conTemp1		        # 充电接口DC+温度
        uint16_t conTemp2		        # 充电接口DC-温度
        uint32_t dcVol				    # 输出电压
        uint32_t dcCur				    # 输出电流
     
    #直流输入电表底值监测属性
    ctypedef struct evs_property_dc_input_meter:
        uint8_t gunNo				# 充电枪编号
        char acqTime[15 + 1]		# 采集时间
        uint8_t mailAddr[8]         # 通信地址 压缩BCD
        uint8_t meterNo[8]	        # 电表表号 压缩BCD
        char assetId[32 + 1]		# 电表资产编码
        uint32_t sumMeter			# 电表底值
        uint32_t ApElect			# A相正向总电量
        uint32_t BpElect			# B相正向总电量
        uint32_t CpElect			# C相正向总电量
     
#/******************************************公共属性区*************************************************/

    #交直流输出电表底值监测属性
    ctypedef struct evs_property_meter:
        uint8_t gunNo				# 1	充电枪编号
        char acqTime[15 + 1]		# 2	采集时间
        uint8_t mailAddr[8]        # 3	通信地址 压缩BCD
        uint8_t meterNo[8]	        # 4	表号 压缩BCD
        char assetId[32 + 1]		# 5	电表资产编码
        uint32_t sumMeter			# 6	电表底值
        char lastTrade[40 + 1]		# 7	最后交易流水
        uint32_t elec				# 8	充电中订单的已充电量
     
    #设备日志查询结果上报事件
    ctypedef union u_logData:
        char rawData[255 + 1]
        evs_event_tradeInfo tradeInfo
        evs_property_meter meterData
        evs_property_BMS BMSData
 
    ctypedef struct evs_event_logQuery_Result:
        uint8_t gunNo				        # 1	充电枪编号
        uint32_t startDate				    # 2	查询起始时间戳	startDate
        uint32_t stopDate				    # 3	查询终止时间戳	stopDate
        uint8_t askType				        # 4	查询类型
        uint8_t result				        # 5	响应结果
        char logQueryNo[38 + 1]             # 6	查询流水号
        uint8_t retType				        # 7	响应类型
        uint32_t logQueryEvtSum		        # 8	日志结果上报事件总帧数
        uint32_t logQueryEvtNo			    # 9	日志结果上报帧序号
        u_logData dataArea					# 10 响应数据区
     
#/******************************************需用户实现的回调函数*************************************************/
    # EVS_STATE_EVERYTHING
    # EVS_CONNECT_SUCC
    # EVS_DISCONNECTED
    # EVS_REPORT_REPLY
    # EVS_TRIGGER_EVENT_REPLY
    # EVS_CERT_GET
    # EVS_CERT_SET
    # EVS_DEVICE_REG_CODE_GET
    # EVS_DEVICE_UID_GET

cdef extern from r"output/release/include/protocol.h":
    cdef int set_firmwareVersion(char *version)
    cdef int get_firmwareprogress(int progress)
    cdef int evs_linkkit_new(const int evs_is_ready, const int is_device_uid)
    cdef int evs_linkkit_time_sync()
    cdef int evs_linkkit_fota(uint8_t *buffer, int buffer_length)
    cdef int evs_linkkit_free()
    cdef int evs_mainloop()
    cdef int evs_send_event(evs_cmd_event_enum event_type, void *param)
    cdef void evs_send_property(evs_cmd_property_enum property_type, void *param)

cdef extern from r"output/release/include/interface.h":
    ctypedef enum evs_service_type_t:
        #/*服务回调*/
        EVS_CONF_GET_SRV         #配置获取服务0
        EVS_CONF_UPDATE_SRV      #配置更新服务1
        EVS_QUE_DATA_SRV         #设备日志查询2
        EVS_DEV_MAINTAIN_SRV     #设备维护服务3
        EVS_CTRL_LOCK_SRV        #电子锁控制服务4
        EVS_FEE_MODEL_UPDATA_SRV #计量计费模型更新服务5
        EVS_START_CHARGE_SRV     #平台远程启动服务6
        EVS_AUTH_RESULT_SRV      #启动充电鉴权结果7
        EVS_STOP_CHARGE_SRV      #平台停止充电8
        EVS_ORDER_CHECK_SRV      #交易记录确认服务9
        EVS_RSV_CHARGE_SRV       #预约充电服务10
        EVS_GROUND_LOCK_SRV      #地锁控制服务11
        EVS_GATE_LOCK_SRV        #智能门锁控制服务12
        EVS_ORDERLY_CHARGE_SRV   #有序充电策略下发13
        EVS_MAINTAIN_RESULT_SRV  #维护状态查询结果14
        # EVS_POWER_CTRL_SRV       #直流控制服务

        #/*系统回调*/
        EVS_STATE_EVERYTHING    #sdk状态变化回调15
        EVS_CONNECT_SUCC        #连接回调16
        EVS_DISCONNECTED        #断开连接回调17
        EVS_REPORT_REPLY        #属性上报回复回调18
        EVS_TRIGGER_EVENT_REPLY #事件上报回复回调19
        EVS_CERT_GET            #证书获取回调20
        EVS_CERT_SET            #证书设置回调21
        EVS_DEVICE_REG_CODE_GET #注册码获取回调22
        EVS_DEVICE_UID_GET      #设备唯一编码获取回调23
        EVS_TIME_SYNC           #时钟同步24
        EVS_OTA_UPDATE          #ota升级25

    cdef int EVS_RegisterCallback(evs_service_type_t service, void *cb)

cdef evs_device_meta device_meta
cdef evs_cmd_event_enum cmd_event_enum
cdef evs_cmd_property_enum cmd_property_enum
cdef evs_event_fireware_info event_fireware_info
cdef evs_event_ver_info event_ver_info
cdef evs_data_dev_config data_dev_config
cdef evs_service_query_log service_query_log
cdef evs_service_feedback_query_log service_feedback_query_log
cdef evs_service_dev_maintain service_dev_maintain
cdef evs_service_feedback_dev_maintain service_feedback_dev_maintain
cdef evs_service_feedback_maintain_query service_feedback_maintain_query
cdef evs_service_lockCtrl service_lockCtrl
cdef evs_service_feedback_lockCtrl service_feedback_lockCtrl
cdef evs_event_ask_feeModel event_ask_feeModel
cdef evs_service_issue_feeModel service_issue_feeModel
cdef evs_service_feedback_feeModel service_feedback_feeModel
cdef evs_service_startCharge service_startCharge
cdef evs_service_feedback_startCharge service_feedback_startCharge
cdef evs_event_startResult event_startResult
cdef evs_event_startCharge event_startCharge
cdef evs_service_authCharge service_authCharge
cdef evs_service_feedback_authCharge service_feedback_authCharge
cdef evs_service_stopCharge service_stopCharge
cdef evs_service_feedback_stopCharge service_feedback_stopCharge
cdef evs_event_stopCharge event_stopCharge
cdef evs_event_tradeInfo event_tradeInfo
cdef evs_service_confirmTrade service_confirmTrade
cdef evs_event_alarm event_alarm
cdef evs_service_rsvCharge service_rsvCharge
cdef evs_service_feedback_rsvCharge service_feedback_rsvCharge
cdef evs_service_groundLock_ctrl service_groundLock_ctrl
cdef evs_service_feedback_groundLock_ctrl service_feedback_groundLock_ctrl
cdef evs_event_groundLock_change event_groundLock_change
cdef evs_service_gateLock_ctrl service_gateLock_ctrl
cdef evs_service_feedback_gateLock_ctrl service_feedback_gateLock_ctrl
cdef evs_event_gateLock_change event_gateLock_change
cdef evs_service_orderCharge service_orderCharge
cdef evs_service_feedback_orderCharge service_feedback_orderCharge
cdef evs_event_pile_stutus_change event_pile_stutus_change
cdef evs_event_car_info event_car_info
cdef evs_property_acPile property_acPile
cdef evs_property_ac_work property_ac_work
cdef evs_property_ac_nonWork property_ac_nonWork
cdef evs_property_dcPile property_dcPile
cdef evs_property_BMS property_BMS
cdef evs_property_dc_work property_dc_work
cdef evs_property_dc_nonWork property_dc_nonWork
cdef evs_property_dc_input_meter property_dc_input_meter
cdef evs_property_meter property_meter
cdef evs_event_logQuery_Result event_logQuery_Result
cdef evs_service_type_t service_type_t

cdef struct dev_config:
    char dev[16 + 1]

cdef dev_config event_dev_config
cdef file_location = None
cdef palform_time = None

cdef inline char* str_to_char(pystr:str):
    return pystr.encode('utf-8')

cdef inline str char_to_str(pychar:char):
    return pychar.decode('utf-8')

cdef inline remove_escape_characters(byte_data):
    return bytes([b for b in byte_data if 32 <= b <= 126])

cdef inline save_DeviceInfo(data_id, data_type, data_str, data_int):
    conn = sqlite3.connect("/opt/hhd/Platform.db")
    cur = conn.cursor()
    if get_DeviceInfo(data_id) is None:
        cur.execute('''INSERT INTO DeviceInfo (data_id, data_type, data_str, data_int) VALUES (?, ?, ?, ?)''',
                    (data_id, data_type, data_str, data_int))
    else:
        cur.execute('''UPDATE DeviceInfo SET data_type = ?, data_str = ?, data_int = ? WHERE data_id = ?''',
                    (data_type, data_str, data_int, data_id))
    conn.commit()
    conn.close()

cdef inline get_DeviceInfo(data_id):
    conn = sqlite3.connect("/opt/hhd/Platform.db")
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

cdef inline timestamp_to_datetime(timestamp:int):
    try:
        dt_object = datetime.fromtimestamp(timestamp)
        time_data = {
            "info_id": EVS_TIME_SYNC,
            "time": timestamp,
            "year": dt_object.year,
            "month": dt_object.month,
            "day": dt_object.day,
            "hour": dt_object.hour,
            "minute": dt_object.minute,
            "second": dt_object.second
        }
        time_json = json.dumps(time_data)
        return time_json
        # return dt_object.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"\033[91m{e}\033[0m")
        print(f"data_input---dict_data: {timestamp}")
        print(f"data_output---dict_data: {time_json}")
        return ""

cdef inline save_buffer_to_file(buffer, filename):
    with open(filename, 'wb') as f:
        f.write(buffer)



