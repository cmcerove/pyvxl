#!/usr/bin/env python3

"""Implements UDS requests based on ISO 14229-1:2013."""

import logging
from copy import deepcopy


class UDS:
    """Sends/receives UDS requests compliant with ISO 14229-1:2013."""

    def __init__(self, can):  # noqa
        self.last_nrc = 0
        self.can = can
        self.__tx_msg = None
        self.__rx_msg = None
        self.__p2_server = None
        self.__p2_star_server = None

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
        self.__tx_msg = deepcopy(self.can.db.get_message(tx_name_or_id))

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
        if not isinstance(timeout, int):
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
        if not isinstance(timeout, int):
            raise TypeError(f'Expected int but got {type(timeout)}')
        self.__p2_star_server = timeout

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
        elif isinstance(data, int):
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

    def send_tester_present(self, once=False):
        """Send tester present - Service 0x3E."""
        if once:
            self.can.send_message(self.tx_msg.id, '023E800000000000', 0)
        else:
            self.can.send_message(self.tx_msg.id, '023E800000000000', 2000)

    def stop_tester_present(self):
        """Stop sending tester present. - Service 0x3E.

        This function will only work if tester present was started by calling
        send_tester_present without once=True.
        """
        self.can.stop_message(self.tx_msg)

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

    def _send_recv(self, tx_data, timeout, tx_id=None, queue_size=10000):
        """Similar to can.send_recv without changing any db Message data."""
        tx_msg = self.tx_msg if tx_id is None else self.can.get_message(tx_id)
        self.can.start_queue(self.rx_msg.id, queue_size)
        tx_msg.data = tx_data
        self.can._send(self.tx_msg, send_once=True)
        _, msg_data = self.can.dequeue_msg(self.rx_msg.id, timeout)
        return msg_data

    def send_service(self, service, values, fc_id=None, timeout=None):
        """Send a diagnostic serivce."""
        p2 = self.p2_server if timeout is None else timeout
        p2_star = self.p2_star_server
        num_bytes = 4
        num = 0
        valid_resp = False
        data = False
        frames = []
        positive_resp = f'{service | 0x40:02X}'
        pending_resp = f'7F{service:02X}78'
        length = len(values) + 1

        if len(values) > 6:
            first = f'1{length:03X}{service:02X}'
            first += ''.join([f'{x:02X}' for x in values[:5]])
            frames.append(first)
            values = values[5:]
            num_frames = int(len(values) / 7) + (1 if len(values) % 7 else 0)
            for x in range(0, num_frames):
                tmp = ''.join(['{y:02X}' for y in values[x * 7:x * 7 + 7]])
                frames.append(f'2{(x + 1) % 0x10:01X}{tmp}')
                if x == num_frames - 1 and len(frames[-1]) < 16:
                    frames[-1] += '5' * (16 - len(frames[-1]))
        else:
            values += (6 - len(values)) * [0x55]
            values = ''.join([f'{val:02X}' for val in values])
            data = f'{length:02X}{service:02X}{values}'
            frames.append(data)

        # Send out the first frame
        if fc_id and len(frames) > 1:
            resp = self._send_recv(frames[0], fc_id, timeout=p2)
        else:
            resp = self._send_recv(frames[0], timeout=p2)
        frames = frames[1:]
        while resp and resp[2:8] == pending_resp:
            _, resp = self.can.dequeue(self.rx_msg.id, p2_star)
        self.can.stop_queue(self.rx_msg.id)

        if resp and len(frames) > 1:
            # Sending multiframe, expecting to receive a flow control frame
            if resp[0] == '3':    # Clear to send
                for data in frames[:-1]:
                    self.can._send(self.tx_msg, send_once=True)
                resp = self._send_recv(frames[-1], timeout=p2)

                while resp and resp[2:8] == pending_resp:
                    _, resp = self.can.dequeue_msg(self.rx_msg.id, p2_star)
                self.can.stop_queue(self.rx_msg.id)

        if resp:
            if resp[0] == '1':    # multi-frame
                # A maximum of 6 bytes in the first frame and 7 in all
                # additional frames.
                # Remove the multi-frame nibble
                resp = resp[1:]
                num_bytes = int(resp[:3], 16)
                # Remove the length
                resp = resp[3:]
            else:
                # A maximum of 7 bytes in the first frame
                num_bytes = int(resp[:2], 16)
                # Remove the length
                resp = resp[2:]

            if resp[:2] == positive_resp:  # and resp[2:4] == did:
                valid_resp = True
                # Remove the positive response byte
                resp = resp[2:]
                num_bytes -= 1
                bytes_in_resp = int(len(resp) / 2)
                if num_bytes >= bytes_in_resp:
                    data = resp
                    bytes_left = num_bytes - bytes_in_resp
                    num = int(bytes_left / 7)
                    # Add an extra frame if num_bytes isn't evenly divisble by 7
                    if bytes_left % 7 != 0:
                        num += 1
                else:
                    data = resp[:2 * num_bytes]
                    num = 0
            else:
                nrc = resp[4:6]
                self.last_nrc = int(nrc, 16)
                logging.info(f'Negative Response: {self.decode_nrc(nrc)}')
                data = 0
                num = 0

            if num > 0:
                # TODO: Implement other parameters for the flow control msg
                # Multi frame response, send the flow control frame
                if fc_id:
                    resp = self._send_recv('3000000000000000', fc_id,
                                           timeout=p2)
                else:
                    resp = self._send_recv('3000000000000000', timeout=p2)
                if resp:
                    rxMsgs = []
                    messagesToReceive = num
                    while messagesToReceive:
                        if not resp:
                            break
                        elif resp[2:8] == pending_resp:
                            _, resp = self.can.dequeue_msg(self.rx_msg.id,
                                                           p2_star)
                        else:
                            messagesToReceive -= 1
                            rxMsgs.append(resp)
                            resp = self.can.dequeue_msg(self.rx_msg.id, p2)
                    resp = rxMsgs

                self.can.stop_queue(self.rx_msg.id)

                if resp:
                    if len(resp) == num:
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

        if valid_resp:
            if data:
                # Split the bytestring into a list of numbers
                data = [int(data[chunk:chunk + 2], 16) for chunk in range(0, len(data), 2)]
                data = data[:num_bytes]
            else:
                data = []
        return (valid_resp, data)
