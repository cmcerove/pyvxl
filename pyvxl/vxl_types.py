#!/usr/bin/env python

"""vxlAPI.dll C types."""

from ctypes import Structure, Union, c_ubyte, c_char, c_ushort, c_uint
from ctypes import c_ulong, c_ulonglong

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


class vxl_can_type(Structure):  # noqa
    _fields_ = [('bitRate', c_uint),
                ('sjw', c_ubyte),
                ('tseg1', c_ubyte),
                ('tseg2', c_ubyte),
                ('sam', c_ubyte),
                ('outputMode', c_ubyte)]


class vxl_most_type(Structure):  # noqa
    _fields_ = [('activeSpeedGrade', c_uint),
                ('compatibleSpeedGrade', c_uint)]


class vxl_flexray_type(Structure):  # noqa
    _fields_ = [('status', c_uint),
                ('cfgMode', c_uint),
                ('baudrate', c_uint)]


class vxl_data_type(Union):  # noqa
    _fields_ = [('can', vxl_can_type),
                ('most', vxl_most_type),
                ('flexray', vxl_flexray_type),
                ('raw', c_ubyte * 32)]


class vxl_bus_params_type(Structure):  # noqa
    _fields_ = [('busType', c_uint),
                ('data', vxl_data_type)]


class vxl_channel_config_type(Structure):  # noqa
    _pack_ = 1
    _fields_ = [('name', c_char * 32),
                ('hwType', c_ubyte),
                ('hwIndex', c_ubyte),
                ('hwChannel', c_ubyte),
                ('transceiverType', c_ushort),
                ('transceiverState', c_ushort),
                ('configError', c_ushort),
                ('channelIndex', c_ubyte),
                ('channelMask', c_ulonglong),
                ('channelCapabilities', c_uint),
                ('channelBusCapabilities', c_uint),
                ('isOnBus', c_ubyte),
                ('connectedBusType', c_uint),
                ('busParams', vxl_bus_params_type),
                ('driverVersion', c_uint),
                ('interfaceVersion', c_uint),
                ('raw_data', c_uint * 10),
                ('serialNumber', c_uint),
                ('articleNumber', c_uint),
                ('transceiverName', c_char * 32),
                ('specialCabFlags', c_uint),
                ('dominantTimeout', c_uint),
                ('dominantRecessiveDelay', c_ubyte),
                ('recessiveDominantDelay', c_ubyte),
                ('connectionInfo', c_ubyte),
                ('currentlyAvailableTimestamps', c_ubyte),
                ('minimalSupplyVoltage', c_ushort),
                ('maximalSupplyVoltage', c_ushort),
                ('maximalBaudrate', c_uint),
                ('fpgaCoreCapabilities', c_ubyte),
                ('specialDeviceStatus', c_ubyte),
                ('channelBusActiveCapabilities', c_ushort),
                ('breakOffset', c_ushort),
                ('delimiterOffset', c_ushort),
                ('reserved', c_uint * 3)]


class vxl_driver_config_type(Structure):  # noqa
    _fields_ = [('dllVersion', c_uint),
                ('channelCount', c_uint),
                ('reserved', c_uint * 10),
                ('channel', vxl_channel_config_type * 64)]


class vxl_license_info_type(Structure):  # noqa
    _fields_ = [('bAvailable', c_ubyte),
                ('licName', c_char * 65)]


# vxl_sync_pulse_type (XL_SYNC_PULSE_EV) is equivalent to XL_CAN_EV_SYNC_PULSE
class vxl_sync_pulse_type(Structure):  # noqa
    _pack_ = 1
    _fields_ = [('pulseCode', c_ubyte),
                ('time', c_ulonglong)]


class vxl_can_msg_type(Structure):  # noqa
    _fields_ = [('id', c_ulong),
                ('flags', c_ushort),
                ('dlc', c_ushort),
                ('res1', c_ulonglong),
                ('data', c_ubyte * 8),
                ('res2', c_ulonglong)]


class vxl_daio_data_type(Structure):  # noqa
    _fields_ = [('flags', c_ushort),
                ('timestamp_correction', c_uint),
                ('mask_digital', c_ubyte),
                ('reserved0', c_ubyte),
                ('value_analog', c_ushort * 4),
                ('pwm_frequency', c_uint),
                ('reserved1', c_uint),
                ('reserved2', c_uint)]


class vxl_digital_data_type(Structure):  # noqa
    _fields_ = [('digitalInputData', c_uint)]


class vxl_analog_data_type(Structure):  # noqa
    _fields_ = [('measuredAnalogData0', c_uint),
                ('measuredAnalogData1', c_uint),
                ('measuredAnalogData2', c_uint),
                ('measuredAnalogData3', c_uint)]


class vxl_pig_u_type(Union):  # noqa
    _fields_ = [('digital', vxl_digital_data_type),
                ('analog', vxl_analog_data_type)]


class vxl_daio_piggy_data_type(Structure):  # noqa
    _fields_ = [('daioEvtTag', c_uint),
                ('triggerType', c_uint),
                ('pigU', vxl_pig_u_type)]


class vxl_chip_state_type(Structure):  # noqa
    _fields_ = [('busStatus', c_ubyte),
                ('txErrorCounter', c_ubyte),
                ('rxErrorCounter', c_ubyte)]


class vxl_transceiver_type(Structure):  # noqa
    _fields_ = [('event_reason', c_ubyte),
                ('is_present', c_ubyte)]


class vxl_lin_msg_type(Structure):  # noqa
    _fields_ = [('id', c_ubyte),
                ('dlc', c_ubyte),
                ('flags', c_ushort),
                ('data', c_ubyte * 8),
                ('crc', c_ubyte)]


class vxl_lin_no_ans_type(Structure):  # noqa
    _fields_ = [('id', c_ubyte)]


class vxl_lin_wake_up_type(Structure):  # noqa
    _fields_ = [('flag', c_ubyte)]


class vxl_lin_sleep_type(Structure):  # noqa
    _fields_ = [('flag', c_ubyte)]


class vxl_lin_crc_info_type(Structure):  # noqa
    _fields_ = [('id', c_ubyte),
                ('flags', c_ubyte)]


class linMsgApi(Union):  # noqa
    _fields_ = [('linMsg', vxl_lin_msg_type),
                ('linNoAns', vxl_lin_msg_type),
                ('linWakeUp', vxl_lin_wake_up_type),
                ('linSleep', vxl_lin_sleep_type),
                ('linCRCinfo', vxl_lin_crc_info_type)]


class vxl_tag_data_type(Union):  # noqa
    _fields_ = [('msg', vxl_can_msg_type),
                ('chipState', vxl_chip_state_type),
                ('linMsgApi', linMsgApi),
                ('syncPulse', vxl_sync_pulse_type),
                ('daioData', vxl_daio_data_type),
                ('transceiver', vxl_transceiver_type),
                ('daioPiggyData', vxl_daio_piggy_data_type)]


class vxl_event_type(Structure):  # noqa
    _fields_ = [('tag', c_ubyte),
                ('chanIndex', c_ubyte),
                ('transId', c_ushort),
                ('portHandle', c_ushort),
                ('flags', c_ubyte),
                ('reserved', c_ubyte),
                ('timeStamp', c_ulonglong),
                ('tagData', vxl_tag_data_type)]


class vxl_events_type(Structure):  # noqa
    _fields_ = [('event', vxl_event_type * 5)]


class vxl_can_tx_msg(Structure):  # noqa
    _fields_ = [('canId', c_uint),
                ('msgFlags', c_uint),
                ('dlc', c_ubyte),
                ('reserved', c_ubyte * 7),
                ('data', c_ubyte * 64)]


class vxl_tag_data_tx_fd_type(Union):  # noqa
    _fields_ = [('canMsg', vxl_can_tx_msg)]


class vxl_can_tx_event(Structure):  # noqa
    _fields_ = [('tag', c_ushort),
                ('transId', c_ushort),
                ('channelIndex', c_ubyte),
                ('reserved', c_ubyte * 3),
                ('tagData', vxl_tag_data_tx_fd_type)]


class vxl_can_ev_rx_msg(Structure):  # noqa
    _fields_ = [('canId', c_uint),
                ('msgFlags', c_uint),
                ('crc', c_uint),
                ('reserved1', c_ubyte * 12),
                ('totalBitCnt', c_ushort),
                ('dlc', c_ubyte),
                ('reserved', c_ubyte * 5),
                ('data', c_ubyte * 64)]


class vxl_can_ev_tx_request(Structure):  # noqa
    _fields_ = [('canId', c_uint),
                ('msgFlags', c_uint),
                ('dlc', c_ubyte),
                ('reserved1', c_ubyte),
                ('reserved', c_ushort),
                ('data', c_ubyte * 64)]


class vxl_can_ev_chip_state(Structure):  # noqa
    _fields_ = [('busStatus', c_ubyte),
                ('txErrorCounter', c_ubyte),
                ('rxErrorCounter', c_ubyte),
                ('reserved', c_ubyte),
                ('reserved0', c_uint)]


class vxl_can_ev_error(Structure):  # noqa
    _fields_ = [('errorCode', c_ubyte),
                ('reserved', c_ubyte * 95)]


class vxl_tag_data_rx_fd_type(Union):  # noqa
    _fields_ = [('raw', c_ubyte * 96),
                ('canRxOkMsg', vxl_can_ev_rx_msg),
                ('canTxOkMsg', vxl_can_ev_rx_msg),
                ('canTxRequest', vxl_can_ev_tx_request),
                ('canError', vxl_can_ev_error),
                ('canChipState', vxl_can_ev_chip_state),
                ('canSyncPulse', vxl_sync_pulse_type)]


class vxl_can_rx_event(Structure):  # noqa
    _fields_ = [('size', c_uint),
                ('tag', c_ushort),
                ('channelIndex', c_ushort),
                ('userHandle', c_uint),
                ('flagsChip', c_ushort),
                ('reserved0', c_ushort),
                ('reserved1', c_ulonglong),
                ('timeStampSync', c_ulonglong),
                ('tagData', vxl_tag_data_rx_fd_type)]


class vxl_can_fd_conf(Structure):  # noqa
    _fields_ = [('arbitrationBitRate', c_uint),
                ('sjwAbr', c_uint),
                ('tseg1Abr', c_uint),
                ('tseg2Abr', c_uint),
                ('dataBitRate', c_uint),
                ('sjwDbr', c_uint),
                ('tseg1Dbr', c_uint),
                ('tseg2Dbr', c_uint),
                ('reserved', c_ubyte),
                ('options', c_ubyte),
                ('reserved1', c_ubyte * 2),
                ('reserved2', c_uint)]
