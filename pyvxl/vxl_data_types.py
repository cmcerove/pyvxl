from ctypes import *
"""
An example of a C struct that was replicated below
struct s_xl_event {
    unsigned char       tag;
    unsigned char       chanIndex;
    unsigned short      transId;
    unsigned short      portHandle;
    unsigned char       flags;
    unsigned char       reserved;
    XLuint64            timeStamp;
    union s_xl_tag_data tagData;
    };
"""

class vxl_can_type(Structure):
    _fields_ = [("bitRate", c_uint),
                ("sjw", c_ubyte),
                ("tseg1", c_ubyte),
                ("tseg2", c_ubyte),
                ("sam", c_ubyte),
                ("outputMode", c_ubyte)]

class vxl_most_type(Structure):
    _fields_ = [("activeSpeedGrade", c_uint),
                ("compatibleSpeedGrade", c_uint)]

class vxl_flexray_type(Structure):
    _fields_ = [("status", c_uint),
                ("cfgMode", c_uint),
                ("baudrate", c_uint)]

class vxl_data_type(Union):
    _fields_ = [("can", vxl_can_type),
                ("most", vxl_most_type),
                ("flexray", vxl_flexray_type),
                ("raw", c_ubyte*32)]

class vxl_bus_params_type(Structure):
    _fields_ = [("busType", c_uint),
                ("data", vxl_data_type)]

class vxl_channel_config_type(Structure):
    _pack_ = 1
    _fields_ = [("name", c_char*32),
                ("hwType", c_ubyte),
                ("hwIndex", c_ubyte),
                ("hwChannel", c_ubyte),
                ("transceiverType", c_ushort),
                ("transceiverState", c_ushort),
                ("configError", c_ushort),
                ("channelIndex", c_ubyte),
                ("channelMask", c_ulonglong),
                ("channelCapabilities", c_uint),
                ("channelBusCapabilities", c_uint),
                ("isOnBus", c_ubyte),
                ("connectedBusType", c_uint),
                ("busParams", vxl_bus_params_type),
                ("driverVersion", c_uint),
                ("interfaceVersion", c_uint),
                ("raw_data", c_uint*10),
                ("serialNumber", c_uint),
                ("articleNumber", c_uint),
                ("transceiverName", c_char*32),
                ("specialCabFlags", c_uint),
                ("dominantTimeout", c_uint),
                ("dominantRecessiveDelay", c_ubyte),
                ("recessiveDominantDelay", c_ubyte),
                ("connectionInfo", c_ubyte),
                ("currentlyAvailableTimestamps", c_ubyte),
                ("minimalSupplyVoltage", c_ushort),
                ("maximalSupplyVoltage", c_ushort),
                ("maximalBaudrate", c_uint),
                ("fpgaCoreCapabilities", c_ubyte),
                ("specialDeviceStatus", c_ubyte),
                ("channelBusActiveCapabilities", c_ushort),
                ("breakOffset", c_ushort),
                ("delimiterOffset", c_ushort),
                ("reserved", c_uint*3)]

class vxl_driver_config_type(Structure):
    _fields_ = [("dllVersion", c_uint),
                ("channelCount", c_uint),
                ("reserved", c_uint*10),
                ("channel", vxl_channel_config_type*64)]

class vxl_license_info_type(Structure):
    _fields_ = [("bAvailable", c_ubyte),
                ("licName", c_char*65)]

class vxl_sync_pulse_type(Structure):
    _pack_ = 1
    _fields_ = [("pulseCode", c_ubyte),
                ("time", c_ulonglong)]

class vxl_can_msg_type(Structure):
    _fields_ = [("id", c_ulong),
                ("flags", c_ushort),
                ("dlc", c_ushort),
                ("res1", c_ulonglong),
                ("data", c_ubyte*8),
                ("res2", c_ulonglong)]

class vxl_daio_data_type(Structure):
    _fields_ = [("flags", c_ushort),
                ("timestamp_correction", c_uint),
                ("mask_digital", c_ubyte),
                ("reserved0", c_ubyte),
                ("value_analog", c_ushort*4),
                ("pwm_frequency", c_uint),
                ("reserved1", c_uint),
                ("reserved2", c_uint)]

class vxl_digital_data_type(Structure):
    _fields_ = [("digitalInputData", c_uint)]

class vxl_analog_data_type(Structure):
    _fields_ = [("measuredAnalogData0", c_uint),
                ("measuredAnalogData1", c_uint),
                ("measuredAnalogData2", c_uint),
                ("measuredAnalogData3", c_uint)]

class vxl_pig_u_type(Union):
    _fields_ = [("digital", vxl_digital_data_type),
                ("analog", vxl_analog_data_type)]

class vxl_daio_piggy_data_type(Structure):
    _fields_ = [("daioEvtTag", c_uint),
                ("triggerType", c_uint),
                ("pigU", vxl_pig_u_type)]

class vxl_chip_state_type(Structure):
    _fields_ = [("busStatus", c_ubyte),
                ("txErrorCounter", c_ubyte),
                ("rxErrorCounter", c_ubyte)]

class vxl_transceiver_type(Structure):
    _fields_ = [("event_reason", c_ubyte),
                ("is_present", c_ubyte)]

class vxl_lin_msg_type(Structure):
    _fields_ = [("id", c_ubyte),
                ("dlc", c_ubyte),
                ("flags", c_ushort),
                ("data", c_ubyte*8),
                ("crc", c_ubyte)]

class vxl_lin_no_ans_type(Structure):
    _fields_ = [("id", c_ubyte)]

class vxl_lin_wake_up_type(Structure):
    _fields_ = [("flag", c_ubyte)]

class vxl_lin_sleep_type(Structure):
    _fields_ = [("flag", c_ubyte)]

class vxl_lin_crc_info_type(Structure):
    _fields_ = [("id", c_ubyte),
                ("flags", c_ubyte)]

class linMsgApi(Union):
    _fields_ = [("linMsg", vxl_lin_msg_type),
                ("linNoAns", vxl_lin_msg_type),
                ("linWakeUp", vxl_lin_wake_up_type),
                ("linSleep", vxl_lin_sleep_type),
                ("linCRCinfo", vxl_lin_crc_info_type)]

class vxl_tag_data_type(Union):
    _fields_ = [("msg", vxl_can_msg_type),
                ("chipState", vxl_chip_state_type),
                ("linMsgApi", linMsgApi),
                ("syncPulse", vxl_sync_pulse_type),
                ("daioData", vxl_daio_data_type),
                ("transceiver", vxl_transceiver_type),
                ("daioPiggyData", vxl_daio_piggy_data_type)]

class vxl_event_type(Structure):
    _fields_ = [("tag", c_ubyte),
                ("chanIndex", c_ubyte),
                ("transId", c_ushort),
                ("portHandle", c_ushort),
                ("flags", c_ubyte),
                ("reserved", c_ubyte),
                ("timeStamp", c_ulonglong),
                ("tagData", vxl_tag_data_type)]

class vxl_events_type(Structure):
    _fields_ = [("event", vxl_event_type*5)]
