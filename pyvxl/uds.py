#!/usr/bin/env python3

"""Implements UDS requests based on ISO 14229-1:2013."""

import logging


def hex_str_to_byte_array(hex_str):
    """Convert a string of hex bytes to a list of integers."""
    return [ord(x) for x in hex_str.decode('hex')]


def byte_array_to_ascii_str(byte_array):
    """Convert a list of integers to a string of hex bytes."""
    return ''.join([chr(x) for x in byte_array])


def byte_array_to_hex_str(byte_array):
    """Convert a list of integers to a string of hex bytes."""
    return ''.join(['{:02X}'.format(x) for x in byte_array])


class UDS:
    """Sends/receives UDS requests compliant with ISO 14229-1:2013."""

    def __init__(self, can):  # noqa
        self.sending_tester_present = 0
        self.last_nrc = 0
        self.tester = 0xF1
        self.can = can

    @property
    def func_id(self):
        """The functional msg ID used with send_service when phys_id=False."""
        return self.__func_id

    @func_id.setter
    def func_id(self, func_id):
        """The functional msg ID used with send_service when phys_id=False."""
        raise NotImplementedError

    @property
    def phys_id(self):
        """The physical msg ID used with send_service when phys_id=True."""
        return self.__phys_id

    @phys_id.setter
    def phys_id(self, func_id):
        """The physical msg ID used with send_service when phys_id=True."""
        raise NotImplementedError

    @property
    def tester(self):
        """The tester ID used for sending and receiving mesages."""
        return self.__tester

    @tester.setter
    def tester(self, tester):
        """The tester ID used for sending and receiving mesages."""
        if not isinstance(tester, int):
            raise TypeError('Expected an int but got {}'.format(type(tester)))
        # self.func_id = 0x10dbfe00 + tester
        # self.phys_id = 0x14da4600 + tester
        # self.recv_id = 0x14da0046 + (tester << 8)

    def send_tester_present(self, func_id=True, once=False):
        """Send tester present."""
        send_id = self.func_id if func_id else self.phys_id
        if not self.sending_tester_present:
            if once:
                assert self.can.send_message(send_id, '023E800000000000', inDatabase=False, cycleTime=0)
            else:
                assert self.can.send_message(send_id, '023E800000000000', inDatabase=False, cycleTime=2000)
                self.sending_tester_present = send_id

    def stop_tester_present(self):
        """Stop sending tester present.

        This function will only work if tester present was started by calling
        send_tester_present without once=True.
        """
        if self.sending_tester_present:
            self.stop_periodic(self.sending_tester_present)
            self.sending_tester_present = 0

    def stop_periodics(self):
        """An extention of pyvxl.CAN.stop_periodics to clear sending_tester_present."""
        super(UDS, self).stop_periodics()
        self.sending_tester_present = 0

    def ecu_reset(self, reset_type, raise_error=True, **kwargs):
        """ECU Reset - service 0x11."""
        result = None
        reset_types = {'hard_reset': 0x01}
        if reset_type not in reset_types:
            raise NotImplementedError('Reset type {} is not implemented for '
                                      'service 0x11'.format(reset_type))
        successful, data = self.send_service(0x11, [reset_types[reset_type]],
                                             **kwargs)
        if not successful:
            if raise_error:
                raise AssertionError('Failed resetting the ECU!')
        else:
            result = data
        return result

    def control_dtc_setting(self, on_off, **kwargs):
        """Control DTC setting (service 85)."""
        # TODO: Implement this
        pass

    def _check(self, check_type, data):
        """Generic funcion for checking types."""
        expected_len = expected_max = 0
        if check_type in ['DID', 'RID']:
            expected_len = 4
            expected_max = 0xFFFF
            fmt_str = '{:04X}'
        else:
            raise NotImplementedError('check_type == {} is not implemented'
                                      ''.format(check_type))
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
        return hex_str_to_byte_array(data)

    def _check_data(self, data):
        """Check that data is either a hex string or list of bytes.

        As a trade off for performance, if a list is passed, checking the type
        and range of each element is skipped.
        """
        if isinstance(data, str):
            try:
                data = hex_str_to_byte_array(data)
            except TypeError:
                # Odd length string can't be converted to hex
                raise
        elif not isinstance(data, list):
            raise TypeError('Expected a hex string or list of bytes but got '
                            '{}'.format(type(data)))
        return data

    def start_rid(self, rid, data=[], raise_error=True, **kwargs):
        """Start a routine (RID)."""
        self.last_nrc = 0
        result = None
        # Start routine sub function
        sub_func = [0x01]
        request = sub_func + self._check('RID', rid) + self._check_data(data)
        successful, data = self.send_service(0x31, request, **kwargs)
        if not successful:
            if raise_error:
                raise AssertionError('Failed to start RID 0x{:02x}{:02x}'.format(request[1], request[2]))
        else:
            # TODO: Fix send_service so rid_len can be set to 2
            result = data[3:]  # Remove the DID from the response
        return result

    def read_did(self, did, raise_error=True, **kwargs):
        """Read a diagnostic ID."""
        result = None
        request = self._check('DID', did)
        successful, data = self.send_service(0x22, request, **kwargs)
        if not successful:
            if raise_error:
                raise AssertionError('Failed to read DID 0x{:02x}{:02x}'.format(request[0], request[1]))
        else:
            result = data[2:]  # Remove the DID from the response
        return result

    def write_did(self, did, data, raise_error=True, **kwargs):
        """Write a diagnostic ID."""
        result = None
        request = self._check('DID', did) + self._check_data(data)
        successful, data = self.send_service(0x2E, request, **kwargs)
        if not successful:
            if raise_error:
                raise AssertionError('Failed to write DID 0x{:02x}{:02x}'.format(request[0], request[1]))
        else:
            result = data[2:]  # Remove the DID from the response
        return result

    def decode_nrc(self, nrc):
        """Convert the negative response code to text."""
        nrc_text = 'Negative response code {} not found'.format(nrc)
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

    def send_service(self, service, values, eleven_bit=False, phys_id=True,
                     fc_id=None, timeout=150, in_database=False, log_error=True):
        """Send a diagnostic serivce."""
        send_id = self.phys_id if phys_id else self.func_id
        send_id = 0x646 if eleven_bit else send_id
        num_bytes = 4
        num = 0
        valid_resp = False
        data = False
        frames = []
        positive_resp = '{:02X}'.format(service | 0x40)
        pending_resp = '7F{:02X}78'.format(service)
        length = len(values) + 1

        if len(values) > 6:
            first = '1{:03X}{:02X}'.format(length, service)
            first += ''.join(['{:02X}'.format(x) for x in values[:5]])
            frames.append(first)
            values = values[5:]
            num_frames = len(values) / 7 + (1 if len(values) % 7 else 0)
            for x in xrange(0, num_frames):
                tmp = ''.join(['{:02X}'.format(y) for y in values[x * 7:x * 7 + 7]])
                frames.append('2{:01X}{}'.format((x + 1) % 0x10, tmp))
                if x == num_frames - 1 and len(frames[-1]) < 16:
                    frames[-1] += '5' * (16 - len(frames[-1]))
        else:
            values += (6 - len(values)) * [0x55]
            values = ''.join(['{:02X}'.format(val) for val in values])
            msg = '{:02X}{:02X}{}'.format(length, service, values)
            frames.append(msg)

        # Send out the first frame
        if fc_id and len(frames) > 1:
            # Sending multi frame and looking for a specific flow control message ID
            resp = self.send_recv(send_id, frames[0], fc_id, timeout=timeout,
                                  inDatabase=in_database)
        else:
            resp = self.send_recv(send_id, frames[0], self.recv_id, timeout=timeout,
                                  inDatabase=in_database)
        while resp and resp[2:8] == pending_resp:
            resp = self.wait_for(self.recv_id, '', 5000, inDatabase=in_database,
                                 alreadySearching=True)
        self.stop_queue()

        if resp and len(frames) > 1:
            # Sending multiframe, expecting to receive a flow control frame
            resp = resp.replace(' ', '')
            if resp[0] == '3':    # Clear to send
                frames = frames[1:]
                msgObj = self.get_message(send_id)
                if msgObj:
                    for msg in frames[:-1]:
                        self._send(msgObj, msg, display=True)
                else:
                    print('Unable to find message for send_id {}'.format(send_id))
                resp = self.send_recv(send_id, frames[-1], self.recv_id, timeout=timeout)

                while resp and resp[2:8] == pending_resp:
                    resp = self.dequeue_msg(self.recv_id, 5000)
                self.stop_queue()

        if resp:
            if resp[0] == '1':    # multi-frame
                # A maximum of 6 bytes in the first frame and 7 in all following frames
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
                bytes_in_resp = len(resp) / 2
                if num_bytes >= bytes_in_resp:
                    data = resp
                    bytes_left = num_bytes - bytes_in_resp
                    num = bytes_left / 7
                    # Add an extra frame if num_bytes isn't evenly divisble by 7
                    if bytes_left % 7 != 0:
                        num += 1
                else:
                    data = resp[:2 * num_bytes]
                    num = 0
            else:
                if log_error:
                    nrc = resp[4:6]
                    self.last_nrc = int(nrc, 16)
                    logging.error('Negative Response: {}'.format(self.decode_nrc(nrc)))
                data = 0
                num = 0

            if num > 0:
                # Multi frame response, send the flow control frame
                # TODO: Fix this frame

                if fc_id:
                    resp = self.send_recv(fc_id, '3000000000000000', self.recv_id,
                                          timeout=timeout, inDatabase=in_database)
                else:
                    resp = self.send_recv(send_id, '3000000000000000', self.recv_id,
                                          inDatabase=in_database, timeout=timeout)
                if resp:
                    rxMsgs = []
                    messagesToReceive = num
                    while messagesToReceive:
                        if not resp:
                            break
                        elif resp[2:8] == pending_resp:
                            resp = self.dequeue_msg(self.recv_id, '', 5000, inDatabase=in_database,
                                                 alreadySearching=True)
                        else:
                            messagesToReceive -= 1
                            rxMsgs.append(resp)
                            resp = self.wait_for(self.recv_id, '', 150, inDatabase=in_database,
                                                 alreadySearching=True)
                    resp = rxMsgs

                self.stop_queue()

                if resp:
                    if len(resp) == num:
                        seqnr = 1
                        tmp = ''
                        # Only return values in a valid sequence
                        for x in range(len(resp)):
                            if resp[x][:2] == '2{:01X}'.format(seqnr):
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
