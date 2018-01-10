#!/usr/bin/env python

"""Holds pyvxl's transmit and receive processes."""

import logging
import socket.error
from sys import exit
from inspect import getmemebers, is_method
from select import select
from socket import socket, AF_INET, SOCK_STREAM

logging.basicConfig(level=logging.INFO)


class PeriodicTask(object):
    """."""

    def __init__(self, command, args, kwargs, period):
        """."""
        self.command = command
        self.args = args
        self.kwargs = kwargs
        self.period = period


class Daemon(object):
    """."""

    def __init__(self, host='localhost', port=50063):
        """."""
        # Protect variables so they can't be changed externally
        self._address = (host, port)
        # Whether we're the daemon.
        self.__daemon = False
        # Whether we've called socket.connect successfully
        self.__connected = False
        self._periodic_tasks = []
        self.sock = socket(AF_INET, SOCK_STREAM)

    def __del__(self):
        """Stop the daemon on object deletion."""
        if self.running():
            self._send('__stop')

    def start(self):
        """Start the daemon.

        To be called from the the host proccess only.

        TODO: Raise an appropriate error if starting fails. Maybe it's safer to force sys.exit to
              remove the possibility of an accidental forkbomb.
        """
        if not self.running():
            logging.info('Starting daemon')
            Popen(["python", os.path.realpath(__file__)])
            if not self.running():
                # Raise appropriate error
                pass
            else:
                logging.info('Daemon started successfully')
        else:
            logging.error('Daemon already running!')

    def __stop(self):
        """Stop the daemon.

        Protected so it cannot be accidentally overridden or called from subclasses.
        """
        exit(0)

    def running(self):
        """Verify the daemon is running by sending a message."""
        running = False
        if self.check_connection():
            # TODO: Send test message
            # if response indicating the daemon is running:
            #    running = True
            pass

        return running

    def check_connection(self):
        """Check if the server is already running."""
        if not self.is_connected:
            try:
                self.sock.connect((self.host, self.port))
                self.is_connected = True
            except socket.error:
                self.is_connected = False
        return self.is_connected

    def _send(self, *args, **kwargs):
        """Send data to the daemon."""
        try:
            sendSock.connect((HOST, PORT))
        except socket.error:
            logging.info('Starting SIB server')
            sib_path = os.path.dirname(os.path.realpath(__file__)) + '\\sib.py'
            Popen(["python", sib_path])
            try:
                sendSock.connect((HOST, PORT))
            except socket.error:
                logging.error('Something went wrong starting the server!')
                return False

    def _receieve(self, length=512):
        """Blocking receive."""
        waiting = True
        while waiting:
            # Blocking wait for a connection
            inputr, [], [] = select.select([sock], [], [], 3)
            for s in inputr:
                if s == sock:
                    waiting = False
        conn, addr = sock.accept()
        return conn.recv(length)

    def updateTimes(self):
        """Updates the GCD and LCM used in the run loop to ensure it's
           looping most efficiently"""
        if len(self.messages) == 1:
            self.currGcd = float(self.messages[0][1])/float(1000)
            self.currLcm = self.elapsed = self.increment = self.messages[0][1]
        else:
            cGcd = self.increment
            cLcm = self.currLcm
            for i in range(len(self.messages)-1):
                tmpGcd = gcd(self.messages[i][1], self.messages[i+1][1])
                tmpLcm = (self.messages[i][1]*self.messages[i+1][1])/tmpGcd
                if tmpGcd < cGcd:
                    cGcd = tmpGcd
                if tmpLcm > cLcm:
                    cLcm = tmpLcm
            self.increment = cGcd
            self.currGcd = float(cGcd)/float(1000)
            self.currLcm = cLcm

    def run(self):
        """The main process loop for the daemon."""
        # TODO: Figure out how to catch this error when two daemons are started
        self.sock.bind((self.host, self.port))
        self.sock.listen(1)
        self.is_daemon = True
        methods = {}
        # Grab all functions in the child class
        for name, method in getmemebers(self, predicate=is_method):
            # Ignore private and protected methods
            if not name.startswith('_'):
                methods[name] = method
        while True:
            # Block until data is received command, args, kwargs, = self._receive()
        while not self.stopped.wait(self.currGcd):
            for msg in self.messages:
                if self.elapsed % msg[1] == 0:
            if self.elapsed >= self.currLcm:
                self.elapsed = self.increment
            else:
                self.elapsed += self.increment


if __name__ == '__main__':
    main()
