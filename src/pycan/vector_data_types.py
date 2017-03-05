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

class can(Structure):
    _fields_ = [("bitRate", c_uint),
                ("sjw", c_ubyte),
                ("tseg1", c_ubyte),
                ("tseg2", c_ubyte),
                ("sam", c_ubyte),
                ("outputMode", c_ubyte)]

class most(Structure):
    _fields_ = [("activeSpeedGrade", c_uint),
                ("compatibleSpeedGrade", c_uint)]

class flexray(Structure):
    _fields_ = [("status", c_uint),
                ("cfgMode", c_uint),
                ("baudrate", c_uint)]

class data(Union):
    _fields_ = [("can", can),
                ("most", most),
                ("flexray", flexray),
                ("raw", c_ubyte*32)]

class busParams(Structure):
    _fields_ = [("busType", c_uint),
                ("data", data)]

class channelConfig(Structure):
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
                ("busParams", busParams),
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

class driverConfig(Structure):
    _fields_ = [("dllVersion", c_uint),
                ("channelCount", c_uint),
                ("reserved", c_uint*10),
                ("channel", channelConfig*64)]

class licenseInfo(Structure):
    _fields_ = [("bAvailable", c_ubyte),
                ("licName", c_char*65)]

class syncPulse(Structure):
    _pack_ = 1
    _fields_ = [("pulseCode", c_ubyte),
                ("time", c_ulonglong)]

class canMsg(Structure):
    _fields_ = [("id", c_ulong),
                ("flags", c_ushort),
                ("dlc", c_ushort),
                ("res1", c_ulonglong),
                ("data", c_ubyte*8),
                ("res2", c_ulonglong)]

class daioData(Structure):
    _fields_ = [("flags", c_ushort),
                ("timestamp_correction", c_uint),
                ("mask_digital", c_ubyte),
                ("reserved0", c_ubyte),
                ("value_analog", c_ushort*4),
                ("pwm_frequency", c_uint),
                ("reserved1", c_uint),
                ("reserved2", c_uint)]

class digitalData(Structure):
    _fields_ = [("digitalInputData", c_uint)]

class analogData(Structure):
    _fields_ = [("measuredAnalogData0", c_uint),
                ("measuredAnalogData1", c_uint),
                ("measuredAnalogData2", c_uint),
                ("measuredAnalogData3", c_uint)]

class pigU(Union):
    _fields_ = [("digital", digitalData),
                ("analog", analogData)]

class daioPiggyData(Structure):
    _fields_ = [("daioEvtTag", c_uint),
                ("triggerType", c_uint),
                ("pigU", pigU)]

class chipState(Structure):
    _fields_ = [("busStatus", c_ubyte),
                ("txErrorCounter", c_ubyte),
                ("rxErrorCounter", c_ubyte)]

class transceiver(Structure):
    _fields_ = [("event_reason", c_ubyte),
                ("is_present", c_ubyte)]

class linMsg(Structure):
    _fields_ = [("id", c_ubyte),
                ("dlc", c_ubyte),
                ("flags", c_ushort),
                ("data", c_ubyte*8),
                ("crc", c_ubyte)]

class linNoAns(Structure):
    _fields_ = [("id", c_ubyte)]

class linWakeUp(Structure):
    _fields_ = [("flag", c_ubyte)]

class linSleep(Structure):
    _fields_ = [("flag", c_ubyte)]

class linCRCinfo(Structure):
    _fields_ = [("id", c_ubyte),
                ("flags", c_ubyte)]

class linMsgApi(Union):
    _fields_ = [("linMsg", linMsg),
                ("linNoAns", linNoAns),
                ("linWakeUp", linWakeUp),
                ("linSleep", linSleep),
                ("linCRCinfo", linCRCinfo)]

class tagData(Union):
    _fields_ = [("msg", canMsg),
                ("chipState", chipState),
                ("linMsgApi", linMsgApi),
                ("syncPulse", syncPulse),
                ("daioData", daioData),
                ("transceiver", transceiver),
                ("daioPiggyData", daioPiggyData)]

class event(Structure):
    _fields_ = [("tag", c_ubyte),
                ("chanIndex", c_ubyte),
                ("transId", c_ushort),
                ("portHandle", c_ushort),
                ("flags", c_ubyte),
                ("reserved", c_ubyte),
                ("timeStamp", c_ulonglong),
                ("tagData", tagData)]

class events(Structure):
    _fields_ = [("event", event*5)]
