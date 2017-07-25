#!/usr/bin/env python

""""
Interface to CAN232 hardware.

Device: http://www.can232.com/?page_id=14
Drivers: N/A (uses RS-232 or any USB-Serial adapter)
"""

import time
import serial
import binascii
from threading import Thread, Event
from Queue import Queue, Empty
import logging

from autotest.can import common


ORIGINAL_BAUDRATE = 57600  # original baud rate on new hardware
DEFAULT_BAUDRATE = 115200  # COM port baud rate

# CAN232 S command bit-rates
SPEED = {
10000: 'S0',
20000: 'S1',
50000: 'S2',
100000: 'S3',
125000: 'S4',
250000: 'S5',
500000: 'S6',
800000: 'S7',
1000000: 'S8',
}
DEFAULT_SPEED = 500000  # 500 kbps

DEFAULT_MASK = 0x00000000
DEFAULT_FILTER = 0x00000000
DEFAULT_TIMEOUT = 3


class CAN232(common.BaseCAN):
    """Class to manage the CAN232 hardware."""

    def __init__(self, port, dbc_path, baud_rate):
        super(CAN232, self).__init__(port, dbc_path, baud_rate)
        self.speed = DEFAULT_SPEED
        self.mask = DEFAULT_MASK
        self.filter = DEFAULT_FILTER
        self.ser = None  # serial driver created when calling 'start'

        self._queue = Queue()  # Queue of data frames to send
        self._thread = None  # Thread for sending data frames
        self._event = Event()  # Event to signal the thread to stop
        self._threads = []  # list of (Thread, Event) for periodic data frames

    def start(self, baudrate=DEFAULT_BAUDRATE):
        """Open the port and start the driver.
        """
        # Open port
        logging.info("opening port '{0}'...".format(self.port))
        self.ser = serial.Serial(port=self.port,
                                 baudrate=baudrate,
                                 bytesize=serial.EIGHTBITS,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE,
                                 timeout=1)

        # Per manual - "empty any prior command or queued character in the CAN232"
        # Also, make sure the CAN channel is closed.
        self.ser.write("\r\r\rC\r\r\r")
        time.sleep(0.1)
        self.ser.flushInput()
        self.ser.flushOutput()

        # Verify device and initialize
        try:

            # Verify hardware and software version number
            self.ser.write("V\r")
            resp = self.ser.read(6)  # expecting: V1325\r
            if resp:
                logging.debug("received: {0}".format(repr(resp)))
                try:
                    hwver = int(resp[1:3])
                    swver = int(resp[3:5])
                except (IndexError, ValueError):
                    raise AssertionError("failed to get the HW/SW version from the device")
                logging.debug("HW version: {0}, SW version: {1}".format(hwver, swver))
                if hwver < 10 or swver < 25:  # pragma: no cover, testable with invalid hardware
                    raise AssertionError("unsupported HW/SW version: {0}".format((hwver, swver)))

            # Verify serial number
            self.ser.write("N\r")
            resp = self.ser.read(6)  # expecting: Nxxxx\r
            if resp:
                logging.debug("received: {0}".format(resp))
            else:  # pragma: no cover, testable with invalid hardware
                raise AssertionError("failed to get the serial number from the device")

            # Configure the device to use the default settings
            # TODO: Update this to work with GMlan
            if baudrate == ORIGINAL_BAUDRATE:  # pragma: no cover, only happens once per device
                # Configure the device:
                #  X1 - auto poll/send on
                #  Z1 - time stamps on
                #  U1 - 115200 baud
                self.ser.write("X1\r")
                assert self.ser.read(1) == '\r'
                self.ser.write("Z1\r")
                assert self.ser.read(1) == '\r'
                self.ser.write("U1\r")
                assert self.ser.read(1) == '\r'
                self.terminate()
                self.start(baudrate=DEFAULT_BAUDRATE)
                return

            # Set CAN bit-rate
            self.ser.write("{0}\r".format(SPEED[self.speed]))
            resp = self.ser.read(1)  # expecting: \r
            if not resp or '\r' != resp:  # pragma: no cover, this is unlikely to fail
                raise AssertionError("failed to set CAN bit-rate")

            # Open the CAN channel
            self.ser.write("O\r")  # TODO: filter mode, acceptance code, and mask
            resp = self.ser.read(1)  # expecting: \r
            if not resp or '\r' != resp:  # pragma: no cover, this is unlikely to fail
                raise AssertionError("failed to open the CAN channel")

        except AssertionError:
            self.terminate()
            if baudrate == ORIGINAL_BAUDRATE:  # this was the configuration attempt
                raise
            else:
                logging.warning("no response from device, attempting to reconfigure...")
                self.start(baudrate=ORIGINAL_BAUDRATE)

        else:
            logging.debug("starting the primary thread to send messages...")
            self._thread = Thread(target=self._send_loop)
            self._thread.daemon = True  # thread will die with the program
            self._thread.start()

    def terminate(self):
        """Close the port and stop the driver.
        """
        self.stop_periodic()
        if self._thread and not self._event.is_set():
            logging.debug("stopping the primary thread to send messages...")
            self._event.set()  # tell the thread to exit
            self._thread.join()
        logging.info("closing port '{0}'...".format(self.port))

        # Close the CAN channel
        self.ser.write("C\r")
        self.ser.flush()
        self.ser.flushInput()
        self.ser.flushOutput()

        # Close the port
        self.ser.close()

    def send(self, address, data, show_message=True):
        """Send a data frame to the specified CAN address.
        @param address: CAN ID of the message to be sent
        @param data: data to be sent
        @param show_message: determines log levels: True = INFO, False = DEBUG
        """
        logging.log(logging.INFO if show_message else logging.DEBUG,
                    "sending to 0x{0:X}: {1}".format(int(address),
                                                     binascii.hexlify(data)))
        self._queue.put((address, data), timeout=3)

    def _send(self, address, data):
        """Send a data frame to the specified CAN address.
        """
        logging.debug("sending to 0x{0:X}: {1}".format(int(address),
                                                       binascii.hexlify(data)))
        cmd = "t{0:03X}{1}{2}".format(int(address), len(data),
                                      binascii.hexlify(data))
        self.ser.write("{0}\r".format(cmd))
        self.ser.flushInput()  # TODO: Better strategy necessary
        resp = self.ser.read(2)  # expecting: z\r
        if resp:
            if 'z\r' != resp:
                return False  # TODO: what are we doing with this error?

    def _send_loop(self):
        """Threaded loop to send data frames from the queue.
        """
        while not self._event.is_set():
            try:
                address, data = self._queue.get_nowait()
                self._send(address, data)
            except Empty:
                pass

    def send_periodic(self, address, data, period=2):
        """Periodically send a data from to the specified CAN address.
        """
        logging.info("periodically sending to "
                     "0x{0:X}: {1} @ {2} seconds".format(int(address),
                                                         binascii.hexlify(data),
                                                         period))
        # Create thread
        event = Event()
        thread = Thread(name=str(address),
                        target=self._send_periodic,
                        args=(address, data, period, event))
        logging.debug("starting periodic thread {0}...".format(repr(thread.name)))
        # Start thread
        thread.daemon = True  # thread will die with the program
        thread.start()
        self._threads.append((thread, event))
        # Show all threads
        logging.debug("current periodic threads: {0}".format([t.name for t, _e in self._threads]))

    def _send_periodic(self, address, data, period, event):
        """Threaded function to send data periodically.
        """
        while not event.is_set():
            self.send(address, data, show_message=False)
            event.wait(period)

    def stop_periodic(self, address=None):
        """Stop sending periodic messages to the specified address.
        """
        logging.info("stopping periodic CAN for {0}...".format("all" if address is None
                                                               else hex(address)))
        # Stop thread(s)
        for thread, event in self._threads:
            if thread.name == str(address) or address is None:
                logging.debug("stopping periodic thread {0}...".format(repr(thread.name)))
                event.set()
                thread.join()
        # Show all threads
        self._threads[:] = [(t, e) for t, e in self._threads if not e.is_set()]
        logging.debug("remaining periodic threads: {0}".format([t.name for t, _ in self._threads]))
        if not self._threads:
            logging.info("all CAN activity stopped")

    def receive(self, address, timeout=1):
        """Get the oldest logged data frame from the specified CAN address.
        """
        resp = self.ser.read(5)  # expecting: taaal\r
        if resp:
            logging.debug("received: {0}".format(binascii.hexlify(resp)))
            if 5 != len(resp):
                logging.debug("unexpected response")
                return False
        else:
            logging.debug("no response")
            return False
        address = int(resp[1:4], 16)
        length = int(resp[4])
        logging.debug("address: 0x{0:03x}; length {1} B".format(address, length))

        resp = self.ser.read(length + 5)  # expecting: ddddddddtttt\r
        if resp:
            logging.debug("received: {0}".format(binascii.hexlify(resp)))
            if length + 5 != len(resp):
                logging.debug("unexpected response")
                return False
        else:
            logging.debug("no response")
            return False

        # TODO: Convert data
        # TODO: Return timestamp?
        raise NotImplementedError("receive functionality is not yet implemented")

    def wait(self, address, data, timeout=3):  # pragma: no cover
        """Wait for the specified data frame to be received on the CAN address.
        """
        raise NotImplementedError()


def main():  # pragma: no cover, this is only tested manually
    """Run the command-line program for the current class.
    """
    #common.main(custom_class=CAN232)


def run(*args):  # pylint: disable=R0913
    """Run the program for the current class.
    """
    #return common.run(*args, custom_class=CAN232)


if __name__ == '__main__':  # pragma: no cover
    main()
