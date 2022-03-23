#!/usr/bin/env python

"""Implements UDS requests based on ISO 14229-1:2013."""

import logging
import re
from time import sleep
from copy import deepcopy


class UDS:
    """Sends/receives UDS requests compliant with ISO 14229-1:2013."""

    def __init__(self, can):  # noqa
        self.last_nrc = 0
        self.can = can
        self.__tx_msg = None
        self.__rx_msg = None
        self.__max_dlc = 8
        self.__p2_server = None
        self.__p2_star_server = None
        self.__tester_msg = None
        self.__dlc_opt_enabled = False
        # From ISO 15765-2: "If not specified differently, the value [0xCC]
        # should be used for padding as default, to minimize the stuff-bit
        # insertions and bit alterations on the wire."
        self.__padding_value = 0xCC

    @property
    def tx_msg(self):
        """The message id used to transmit requests."""
        if self.__tx_msg is None:
            raise AssertionError('tx_msg not set')
        return self.__tx_msg

    @tx_msg.setter
    def tx_msg(self, tx_name_or_id):
        """Set she message id used to transmit requests."""
        # pyvxl.CAN is meant to keep a single instance of a message. When
        # tester present is being sent, that instance of the tx_msg will
        # have data for requesting tester present. This copy prevents
        # overwriting the data in tester present with other non-periodic
        # requests.
        msg = deepcopy(self.can.db.get_message(tx_name_or_id))
        if msg.dlc <= 8:
            self.__max_dlc = 8
            msg.dlc = 8
        else:
            self.__max_dlc = msg.dlc
        # UDS does not care about the signals defined for this message and
        # needs to be able to use the entire DLC.
        msg.signals = []
        self.__tx_msg = msg

    @property
    def rx_msg(self):
        """The message id expected for responses."""
        if self.__rx_msg is None:
            raise AssertionError('rx_msg not set')
        return self.__rx_msg

    @rx_msg.setter
    def rx_msg(self, tx_name_or_id):
        """Set the message id expected for responses."""
        self.__rx_msg = self.can.db.get_message(tx_name_or_id)

    @property
    def p2_server(self):
        """The timeout used for the first response in a multi-frame request."""
        if self.__p2_server is None:
            raise AssertionError('p2_server not set')
        return self.__p2_server

    @p2_server.setter
    def p2_server(self, timeout):
        """Set the p2_server timeout in milliseconds."""
        if not isinstance(timeout, int) or isinstance(timeout, bool):
            raise TypeError(f'Expected int but got {type(timeout)}')
        self.__p2_server = timeout

    @property
    def p2_star_server(self):
        """The timeout used for additional responses after p2_server."""
        if self.__p2_star_server is None:
            raise AssertionError('p2_star_server not set')
        return self.__p2_star_server

    @p2_star_server.setter
    def p2_star_server(self, timeout):
        """Set the p2_star_server timeout in milliseconds."""
        if not isinstance(timeout, int) or isinstance(timeout, bool):
            raise TypeError(f'Expected int but got {type(timeout)}')
        self.__p2_star_server = timeout

    @property
    def padding_byte_value(self):
        """The value used to pad diagnostic requests to valid DLCs."""
        return self.__padding_value

    @padding_byte_value.setter
    def padding_byte_value(self, padding):
        """Set the value used to pad diagnostic requests to valid DLCs."""
        if not isinstance(padding, (int, str)) or isinstance(padding, bool):
            raise TypeError(f'Expected int but got {type(padding)}')
        if isinstance(padding, int):
            num = padding
        elif padding.isdecimal():
            num = int(padding)
        else:
            pat = re.compile(r'[0-9a-fA-F][0-9a-fA-F]')
            match = pat.match(padding)
            if not match or (match and match.group(0) != padding):
                num = -1
            else:
                num = int(padding, 16)

        if num < 0 or num > 0xFF:
            raise ValueError(f'padding={padding} must be between 0 and 255')
        self.__padding_value = num

    @property
    def data_length_optimization_enabled(self):
        """Whether data length optimization for DLCs is enabled.

        This only applies to DLCs less than 8 bytes long. When this is enabled,
        requests shorter than 8 bytes won't have padding added.

        e.g. A request to enter a programming session would look like:
                [02] 10 02 [00 00 00 00 00] when optimization is disabled or
                [02] 10 02 when optimization is enabled, so the DLC would be 3.
        """
        return self.__dlc_opt_enabled

    @data_length_optimization_enabled.setter
    def data_length_optimization_enabled(self, enabled):
        """Set the p2_star_server timeout in milliseconds."""
        if not isinstance(enabled, bool):
            raise TypeError(f'Expected bool but got {type(enabled)}')
        self.__dlc_opt_enabled = enabled

    def _check(self, check_type, data):
        """Generic funcion for checking types."""
        expected_len = expected_max = 0
        if check_type in ['DID', 'RID']:
            expected_len = 4
            expected_max = 0xFFFF
            fmt_str = '{:04X}'
        else:
            raise NotImplementedError(f'{check_type} is not implemented')
        if isinstance(data, str):
            if len(data) > expected_len:
                raise ValueError(f'{check_type} length must be less than or '
                                 f'equal to {expected_len} characters. '
                                 f'{data:X} is {len(data)} characters long.')
            data = data.zfill(expected_len)
        elif isinstance(data, int) and not isinstance(data, bool):
            if data > expected_max:
                raise ValueError(f'{data:X} not in range: 0 <= {check_type} <='
                                 f' 0x{expected_max:X}')
            data = fmt_str.format(data)
        return list(bytes.fromhex(data))

    def _check_data(self, data):
        """Check that data is either a hex string or list of bytes.

        As a trade off for performance, if a list is passed, checking the type
        and range of each element is skipped.
        """
        if isinstance(data, str):
            try:
                data = list(bytes.fromhex(data))
            except TypeError:
                # Odd length string can't be converted to hex
                raise
        elif not isinstance(data, list):
            raise TypeError('Expected a hex string or list of bytes but got '
                            f'{type(data)}')
        return data

    def _error(self, msg):
        """A common function for raising errors."""
        # TODO: Decide if something like this makes sense. Also if removing
        # raise_error and always raising and error.
        raise AssertionError(msg)

    def session_control(self, session, **kwargs):
        """Session Control - Service 0x10."""
        raise NotImplementedError

    def ecu_reset(self, reset_type, raise_error=True, **kwargs):
        """ECU Reset - Service 0x11."""
        result = None
        reset_types = {'hard_reset': 0x01}
        if reset_type not in reset_types:
            raise NotImplementedError(f'Reset type {reset_type} is not '
                                      'implemented for service 0x11')
        successful, data = self.send_service(0x11, [reset_types[reset_type]],
                                             **kwargs)
        if not successful:
            if raise_error:
                raise AssertionError('Failed resetting the ECU!')
        else:
            result = data
        return result

    def clear_dtcs(self, *args, **kwargs):
        """Clear Diagnostic Information - Service 0x14."""
        raise NotImplementedError

    def dtcs_dtcs(self, *args, **kwargs):
        """Read DTC Information - Service 0x19."""
        raise NotImplementedError

    def read_did(self, did, raise_error=True, **kwargs):
        """Read Data by Identifier - Service 0x22."""
        result = None
        request = self._check('DID', did)
        successful, data = self.send_service(0x22, request, **kwargs)
        if not successful:
            if raise_error:
                raise AssertionError('Failed to read DID '
                                     f'0x{request[0]:02X}{request[1]:02X}')
        else:
            result = data[2:]  # Remove the DID from the response
        return result

    def read_mba(self, *args, **kwargs):
        """Read Memory by Address - Service 0x23."""
        raise NotImplementedError

    def read_scaling_did(self, *args, **kwargs):
        """Read Scaling Data by Identifier - Service 0x24."""
        raise NotImplementedError

    def read_periodic_did(self, *args, **kwargs):
        """Read Data by Periodic Identifier - Service 0x2A."""
        raise NotImplementedError

    def dyamically_define_did(self, *args, **kwargs):
        """Dynamically Define Data Identifier - Service 0x2C."""
        raise NotImplementedError

    def write_did(self, did, data, raise_error=True, **kwargs):
        """Read Data by Identifier - Service 0x2E."""
        result = None
        request = self._check('DID', did) + self._check_data(data)
        successful, data = self.send_service(0x2E, request, **kwargs)
        if not successful:
            if raise_error:
                raise AssertionError('Failed to write DID '
                                     f'0x{request[0]:02X}{request[1]:02X}')
        else:
            result = data[2:]  # Remove the DID from the response
        return result

    def io_cid(self, *args, **kwargs):
        """Input/Ouput Control by Identifier - Service 0x2F."""
        raise NotImplementedError

    def security_access(self, level, key=None, **kwargs):
        """Security Access - Service 0x27.

        If level is odd, this will request the seed for that level.
        if level is even, this will send the key for level - 1.
        """
        raise NotImplementedError

    def communication_control(self, on_off, **kwargs):
        """Communication Control - Service 0x28."""
        raise NotImplementedError

    def start_rid(self, rid, data=[], raise_error=True, **kwargs):
        """Routine Control - Service 0x31, Start RID - SubFunction 0x01."""
        self.last_nrc = 0
        result = None
        # Start routine sub function
        sub_func = [0x01]
        request = sub_func + self._check('RID', rid) + self._check_data(data)
        successful, data = self.send_service(0x31, request, **kwargs)
        if not successful:
            if raise_error:
                raise AssertionError('Failed to start RID '
                                     f'0x{request[1]:02X}{request[2]:02X}')
        else:
            # TODO: Fix send_service so rid_len can be set to 2
            result = data[3:]  # Remove the DID from the response
        return result

    def stop_rid(self, rid, data=[], raise_error=True, **kwargs):
        """Routine Control - Service 0x31, Stop RID - SubFunction 0x02."""
        raise NotImplementedError

    def rid_result(self, rid, data=[], raise_error=True, **kwargs):
        """Routine Control - Service 0x31, RID Result - SubFunction 0x03."""
        raise NotImplementedError

    def request_download(self, *args, **kwargs):
        """Request Download - Service 0x34."""
        raise NotImplementedError

    def request_upload(self, *args, **kwargs):
        """Request Upload - Service 0x35."""
        raise NotImplementedError

    def transfer_data(self, *args, **kwargs):
        """Transfer Data - Service 0x36."""
        raise NotImplementedError

    def request_transfer_exit(self, *args, **kwargs):
        """Request Transfer Exit - Service 0x37."""
        raise NotImplementedError

    def request_file_transfer(self, *args, **kwargs):
        """Request File Transfer - Service 0x38."""
        raise NotImplementedError

    def write_mba(self, *args, **kwargs):
        """Write Memory by Address - Service 0x3D."""
        raise NotImplementedError

    def send_tester_present(self, tx_id=None, period=2000):
        """Send tester present - Service 0x3E.

        Data is fixed with supressing the positive response since handling
        these responses asynchronously with other diagnostic requests isn't
        implemented.
        """
        tx_id = self.tx_msg.id if tx_id is None else tx_id
        msg = deepcopy(self.can.db.get_message(tx_id))
        # UDS does not care about the signals defined for this message and
        # needs to be able to use the entire DLC.
        msg.signals = []
        if self.data_length_optimization_enabled:
            data = '023E80'
            msg.dlc = 3
        else:
            data = '023E80' + f'{self.padding_byte_value:02X}' * (msg.dlc - 3)
        msg.data = data
        msg.period = period
        self.can._send(msg)
        self.__tester_msg = msg

    def stop_tester_present(self):
        """Stop sending tester present. - Service 0x3E.

        This function will only work if tester present was started by calling
        send_tester_present without once=True.
        """
        if self.__tester_msg is not None:
            self.can.stop_message(self.__tester_msg.id)
            self.__tester_msg = None

    def access_timing_param(self, *args, **kwargs):
        """Access Timing Parameter- Service 0x83.."""
        raise NotImplementedError

    def secured_data_tx(self, *args, **kwargs):
        """Secured Data Transmission - Service 0x84.."""
        raise NotImplementedError

    def control_dtc_setting(self, on_off, **kwargs):
        """Control DTC setting - Service 0x85.."""
        raise NotImplementedError

    def response_on_event(self, *args, **kwargs):
        """Response on Event- Service 0x86.."""
        raise NotImplementedError

    def link_control(self, *args, **kwargs):
        """Link Control - Service 0x87.."""
        raise NotImplementedError

    def decode_nrc(self, nrc):
        """Convert the negative response code to text."""
        nrc_text = f'Negative response code {nrc} not found'
        nrc_dict = {'10': 'General reject',
                    '11': 'Service not supported',
                    '12': 'Sub-function not supported',
                    '13': 'Incorrect message length or invalid format',
                    '14': 'Response too long',
                    '21': 'Busy repeat request',
                    '22': 'Conditions not correct',
                    '24': 'Request sequence error',
                    '25': 'No response from subnet component',
                    '26': 'Failure prevents execution of requested action',
                    '31': 'Request out of range',
                    '33': 'Security access denied',
                    '35': 'Invalid key',
                    '36': 'Exceeded number of security access attempts',
                    '37': 'Required time delay not expired',
                    '70': 'Upload/download not accepted',
                    '71': 'Transfer data suspended',
                    '72': 'General programming failure',
                    '73': 'Wrong block sequence counter',
                    '7E': 'Sub-function not supported in active session',
                    '7F': 'Service not supported in active session',
                    '92': 'Voltage too high',
                    '93': 'Voltage too low'}
        if nrc in nrc_dict:
            nrc_text = nrc_dict[nrc]
        return nrc_text

    def send_service(self, service, data_bytes, fc_id=None, timeout=None):
        """Send a diagnostic serivce."""
        # TODO: Move this function to can_tp.py so uds can handle only
        #       ISO 14229-1 and can_tp.py can handle only ISO 15765-2.
        p2 = self.p2_server if timeout is None else timeout
        p2_star = self.p2_star_server
        positive_resp = f'{service | 0x40:02X}'
        pending_resp = f'7F{service:02X}78'
        opt = self.data_length_optimization_enabled
        # Determine which of the 4 frame formats (N_PCI) we need to use:
        #                Byte   -  1       2     3     4    5      6
        #              Nibble   - 1 2     3-4   5-6   7-8  9-10  11-12
        #   SF with CAN_DL<=8   - 0 FF_DL
        #   SF with CAN_DL>8    - 0 0     FF_DL
        #   FF with FF_DL<=4095 - 1 FF_DL FF_DL
        #   FF with FF_DL>4095  - 1 0     0 0   FF_DL FF_DL FF_DL FF_DL
        n_pci_len = 1
        tx_data = [service] + data_bytes
        ff_dl = len(tx_data)
        can_dl = n_pci_len + ff_dl

        if self.__max_dlc > 8 and can_dl > 8:
            n_pci_len = 2
            can_dl = n_pci_len + ff_dl

        frames = []
        if can_dl > self.__max_dlc:
            # Multi frame
            if ff_dl > 4095:
                n_pci = f'1000{ff_dl:08X}'
            else:
                n_pci = f'1{ff_dl:03X}'
            ff_bytes = self.__max_dlc - (len(n_pci) // 2)
            frames.append(n_pci + bytes(tx_data[:ff_bytes]).hex())
            tx_data = tx_data[ff_bytes:]
            # Ceiling division.
            # https://stackoverflow.com/a/17511341/3277956 explains why this is
            # more accurate than math.ceil because it avoids floating point.
            data_len = self.__max_dlc - 1
            num_frames = -(len(tx_data) // -data_len)
            for x in range(0, num_frames):
                frame_data = bytes(tx_data[x * data_len:x * data_len + data_len]).hex()
                sequence_num = (x + 1) % 0x10
                frames.append(f'2{sequence_num:01X}{frame_data}')
        else:
            # Single frame
            if n_pci_len == 2:
                # CAN_DL>8
                frames.append(f'00{ff_dl:02X}{bytes(tx_data).hex()}')
            else:
                # CAN_DL<=8
                frames.append(f'0{ff_dl:01X}{bytes(tx_data).hex()}')

        last_frame_bytes = len(frames[-1]) // 2
        pad_length = 0
        if last_frame_bytes < 8:
            if not opt:
                # Optimization is disabled so padding is needed up to 8 bytes
                pad_length = 8 - last_frame_bytes
        elif last_frame_bytes > 8:
            # Padding is mandatory for more than 8 bytes only up to the next
            # valid CAN FD DLC. There is no option to pad past this point.
            valid_fd_dlcs = [12, 16, 20, 24, 32, 48, 64]
            if last_frame_bytes not in valid_fd_dlcs:
                while last_frame_bytes not in valid_fd_dlcs:
                    last_frame_bytes += 1
                    pad_length += 1

        if pad_length:
            frames[-1] += f'{self.padding_byte_value:02X}' * pad_length

        if fc_id:
            self.can.start_queue(fc_id, 10000)
            dequeue_id = fc_id
        else:
            self.can.start_queue(self.rx_msg.id, 10000)
            dequeue_id = self.rx_msg.id
        # Send out the first frame
        self.tx_msg.dlc = len(frames[0]) // 2
        self.tx_msg.data = frames[0]
        self.can._send(self.tx_msg, send_once=True)
        _, resp = self.can.dequeue_msg(dequeue_id, p2)
        while resp and resp[2:8] == pending_resp:
            _, resp = self.can.dequeue_msg(dequeue_id, p2_star)

        if fc_id:
            self.can.stop_queue(fc_id)
            self.can.start_queue(self.rx_msg.id, 10000)

        if resp and len(frames) > 1:
            # Sending multiframe, expecting to receive a flow control frame
            if resp[0] == '3':
                if resp[1] == '0':  # Continue to Send
                    block_size = int(resp[2:4], 16)
                    if block_size != 0:
                        logging.warning('Received a flow control frame with '
                                        f'block size = {block_size:02X}. Only '
                                        ' block size = 0 is supported. Frames '
                                        'will be sent without waiting for '
                                        'additional flow control frames!')
                    # The minimum separation time between consecutive frames in
                    # milliseconds. Converted to seconds for sleep()
                    st_min = int(resp[4:6], 16) / 1000
                    # I have these split since I think sleep(0) will still
                    # cause a context switch preventing st_min=0 to be sent
                    # at the fastest possible rate.
                    if st_min == 0:
                        frames = frames[1:]
                        for data in frames:
                            self.tx_msg.dlc = len(data) // 2
                            self.tx_msg.data = data
                            self.can._send(self.tx_msg, send_once=True)
                    else:
                        sent = False
                        frames = frames[1:]
                        for data in frames:
                            if sent:
                                sleep(st_min)
                            self.tx_msg.dlc = len(data) // 2
                            self.tx_msg.data = data
                            self.can._send(self.tx_msg, send_once=True)
                            sent = True
                    _, resp = self.can.dequeue_msg(self.rx_msg.id, p2)
                    while resp and resp[2:8] == pending_resp:
                        _, resp = self.can.dequeue_msg(self.rx_msg.id, p2_star)

        data = False
        valid_resp = False
        if resp:
            msgs_to_rx = 0
            # The amount of data that can be sent in consecutive frames using
            # this same DLC.
            rx_data_len = len(resp) // 2 - 1
            # Determine which of the 4 frame formats (N_PCI) we need to use:
            #                Byte   -  1       2     3     4    5      6
            #              Nibble   - 1 2     3-4   5-6   7-8  9-10  11-12
            #   SF with CAN_DL<=8   - 0 FF_DL
            #   SF with CAN_DL>8    - 0 0     FF_DL
            #   FF with FF_DL<=4095 - 1 FF_DL FF_DL
            #   FF with FF_DL>4095  - 1 0     0 0   FF_DL FF_DL FF_DL FF_DL
            if resp[:4] == '1000':  # FF_DL>4095
                # Remove N_PCI
                resp = resp[4:]
                num_bytes = int(resp[:8], 16)
                # Removed the length
                resp = resp[8:]
            elif resp[0] == '1':  # FF_DL<=4095
                # Remove N_PCI
                resp = resp[1:]
                num_bytes = int(resp[:3], 16)
                # Remove the length
                resp = resp[3:]
            elif resp[:2] == '00':  # SF_DL>8
                # A maximum of 7 bytes in the first frame
                num_bytes = int(resp[:4], 16)
                # Remove the length
                resp = resp[4:]
            elif resp[0] == '0':  # SF_DL<=8
                # A maximum of 7 bytes in the first frame
                num_bytes = int(resp[:2], 16)
                # Remove N_PCI and the length
                resp = resp[2:]
            if resp[:2] == positive_resp:
                valid_resp = True
                # Remove the positive response byte
                resp = resp[2:]
                num_bytes -= 1
                bytes_in_resp = len(resp) // 2
                if num_bytes >= bytes_in_resp:
                    data = resp
                    bytes_left = num_bytes - bytes_in_resp
                    msgs_to_rx = -(bytes_left // -rx_data_len)
                else:
                    data = resp[:2 * num_bytes]
                    msgs_to_rx = 0
            else:
                nrc = resp[4:6]
                self.last_nrc = int(nrc, 16)
                logging.info(f'Negative Response: {self.decode_nrc(nrc)}')
                data = 0
                msgs_to_rx = 0

            if msgs_to_rx > 0:
                # Multi frame response, send the flow control frame
                flow_control = '300000'
                if not opt:
                    pad_len = self.__max_dlc - (len(flow_control) // 2)
                    flow_control += f'{self.padding_byte_value:02X}' * pad_len
                self.tx_msg.dlc = len(flow_control) // 2
                self.tx_msg.data = flow_control
                self.can._send(self.tx_msg, send_once=True)
                msgs_received = []
                timeout = p2
                while len(msgs_received) < msgs_to_rx:
                    _, resp = self.can.dequeue_msg(self.rx_msg.id, timeout)
                    if not resp:
                        break
                    elif resp[2:8] == pending_resp:
                        timeout = p2_star
                    else:
                        timeout = p2
                        msgs_received.append(resp)
                resp = msgs_received

                if resp:
                    if len(resp) == msgs_to_rx:
                        seqnr = 1
                        tmp = ''
                        # Only return values in a valid sequence
                        for x in range(len(resp)):
                            if resp[x][:2] == f'2{seqnr:01X}':
                                tmp += resp[x][2:]
                                seqnr = (seqnr + 1) % 16
                            else:
                                break
                        else:
                            data += tmp
                    else:
                        valid_resp = False
                        data = False
                else:
                    valid_resp = False
                    data = False

        self.can.stop_queue(self.rx_msg.id)

        if valid_resp:
            if data:
                # Split the bytestring into a list of numbers
                data = [int(data[chunk:chunk + 2], 16) for chunk in range(0, len(data), 2)]
                data = data[:num_bytes]
            else:
                data = []
        return (valid_resp, data)
