#!/usr/bin/env python

"""Holds pyvxl's transmit and receive processes."""

import logging
import socket
from sys import exit
from os import path, getpid
from subprocess import Popen
from inspect import getmembers, ismethod
from select import select
from time import clock, sleep
from pickle import loads, dumps
from fractions import gcd
from threading import Thread, Event

logging.basicConfig(level=logging.DEBUG)


class Task(object):
    """Represents work that needs to be done."""

    def __init__(self, command='', args=(), kwargs={}, period=0, **extra_kwargs):
        """."""
        if not isinstance(command, str):
            raise TypeError('Task() argument 1 must be a string, not {}'.format(type(command)))
        if not isinstance(args, tuple):
            raise TypeError('Task() argument 2 must be a tuple, not {}'.format(type(args)))
        if not isinstance(kwargs, dict):
            raise TypeError('Task() argument 3 must be a dict, not {}'.format(type(kwargs)))
        if not isinstance(period, int):
            raise TypeError('Task() argument 4 must be an int, not {}'.format(type(period)))
        print 'Creating Task with {} {} {} {}'.format(command, args, kwargs, period)
        self.command = command
        self.args = args
        self.kwargs = kwargs
        # period of the task in milliseconds
        self.period = period


from pyvxl.daemon import Task


class Daemon(object):
    """."""

    def __init__(self, host='localhost', port=50063, logging=logging, file=None):
        """."""
        # All class variables are protected to prevent modification outside of this class
        # The connection address
        self.__address = (host, port)
        # Identifies this instance as the daemon or client
        self.__daemon = False
        # A list of active periodic tasks
        self.__periodic_tasks = []
        # A dictionary for faster lookups of periodic tasks
        self.__periodic_dict = {}
        # Use blocking receives until a periodic task is added
        self.__polling_recv = False
        # Will be used to hold the TCP socket for communication
        self.__sock = None
        # Value used to terminate all transmits
        self.__sentinel = '*-_-*'
        # Both times below are in milliseconds
        # The greatest common denominator of the current set of periodic task times
        self.__sleep_time = 0
        # The least common multiple of the current set of periodic task times
        self.__cycle_time = 0
        # The current process through a complete task cycle
        self.__elapsed = 0
        if not file:
            raise ValueError("Please pass in file=__file__ to the constructor for Daemon")
        self.__file = file

        # Grab all functions in the child class
        self.__child_functions = {}
        for name, method in getmembers(self, predicate=ismethod):
            # Ignore private and protected methods
            if not name.startswith('_') and name not in ['run']:
                self.__child_functions[name] = method
        self.__child_functions['__stop'] = self.__stop
        self.logging = logging
        self.logging.debug('init')

    def __del__(self):
        """Stop the daemon on object deletion."""
        print '\n\n__del__\n\n'
        self.logging.debug('del')
        if not self._is_daemon():
            self._add_task(Task('__stop'))

    def __stop(self):
        """Stop the daemon.

        Protected so it can't be overridden or called from subclasses.
        """
        self.logging.debug('stop')
        exit(0)

    def __send(self, data):
        """Send data to the daemon."""
        # TODO: Add a check for data too large
        self.logging.debug('send')
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(self.__address)
        except socket.error:
            self.logging.debug('Starting daemon')
            self.logging.debug('path: {}'.format(path.realpath(self.__file)))
            Popen(["python", path.realpath(self.__file)])
            try:
                sock.connect(self.__address)
            except socket.error:
                sock.close()
                raise AssertionError("Unable to start the daemon!")
        self.logging.debug('Sending data {}'.format([data]))
        sock.sendall(data)
        sock.close()

    def __receive(self):
        """Attempt to receive data from connected clients."""
        self.logging.debug('receive')
        data = ''
        if self.__polling_recv:
            # Does not block at all
            inputr, [], [] = select([self.__sock], [], [], 0)
        else:
            # Blocking wait for a connection
            inputr, [], [] = select([self.__sock], [], [])
        for s in inputr:
            if s == self.__sock:
                conn, addr = self.__sock.accept()
                data = conn.recv(4096)
                conn.close()
        self.logging.debug('Received data {}'.format([data]))
        return data

    def __update_tasks(self):
        """Receive and process new tasks."""
        self.logging.debug('update_tasks')
        periodic_updated = False
        data = self.__receive()

        for task in data.split(self.__sentinel):
            if task:
                action, task = loads(task)
                if getattr(self, action + '_task')(task):
                    periodic_updated = True

        if periodic_updated:
            self.__update_times()

    def __update_times(self):
        """Update the sleep and cycle time of the run loop."""
        self.logging.debug('update_times')
        self.__polling_recv = True

        # self.elapsed is only reset in the first case to avoid delaying tasks with
        # longer periods.
        if len(self.__periodic_tasks) == 1:
            # Set all times to the single task period
            period = self.__periodic_tasks[0].period
            self.__sleep_time = self.__cycle_time = self.__elapsed = period
        else:
            cGcd = 0
            cLcm = 0
            prev_task = False
            for task in self.__periodic_tasks:
                if not prev_task:
                    prev_task = task
                    continue
                tmpGcd = gcd(prev_task.period, task.period)
                tmpLcm = (prev_task.period * task.period) / tmpGcd
                if tmpGcd < cGcd:
                    cGcd = tmpGcd
                if tmpLcm > cLcm:
                    cLcm = tmpLcm
                prev_task = task
            self.__sleep_time = cGcd
            self.__cycle_time = cLcm

    def __execute_task(self, task):
        """Execute a task."""
        self.logging.debug('execute_task')
        self.__child_functions[task.command](*task.args, **task.kwargs)

    def _is_daemon(self):
        """Check if the calling instance is the daemon.

        Allows the protected variable, daemon, to be read from child classes
        """
        self.logging.debug('is_daemon {}'.format(self.__daemon))
        return self.__daemon

    def _add_task(self, task):
        """Add a task to the daemon."""
        self.logging.debug('add_task')
        periodic_added = False
        self.logging.debug('{} {}'.format(type(task), Task))
        if not isinstance(task, Task):
            raise TypeError('_add_task() argument 1 must be a Task, not {}'.format(type(task)))
        if self._is_daemon():
            if task.command not in self.__child_functions:
                self.logging.error('Received invalid task command {}')
            elif task.period:
                # Valid periodic task, execution delayed until the next cycle
                pickled_task = dumps(task)
                if pickled_task not in self.__periodic_dict:
                    self.__periodic_dict[pickled_task] = task
                    self.__periodic_tasks.append(task)
                periodic_added = True
            else:
                # Valid non-periodic task, execute immedately
                self.__execute_task(task)
        else:
            self.__send(dumps(('_add', task)) + self.__sentinel)
        return periodic_added

    def _remove_task(self, task):
        """Remove a task from the daemon."""
        if not isinstance(task, Task):
            raise TypeError('_remove_task() argument 1 must be a Task, not {}'.format(type(task)))
        if self._is_daemon():
            if task.command not in self.__child_functions:
                self.logging.error('Received invalid task command {}')
            elif task.period:
                # Valid periodic task, execution delayed until the next cycle
                pickled_task = dumps(task)
                if pickled_task in self.__periodic_dict:
                    self.__periodic_dict.pop(pickled_task)
                    self.__periodic_tasks.remove(task)
                else:
                    self.logging.error("Task not found")
            else:
                self.logging.error('Cannot remove a non-periodic task from the list of periodic tasks')
        else:
            self.__send(dumps(('_remove', task)) + self.__sentinel)

    def _update_task(self, task):
        """Update a current periodic task."""
        if not isinstance(task, Task):
            raise TypeError('_update_task() argument 1 must be a Task, not {}'.format(type(task)))
        if self._is_daemon():
            raise NotImplementedError
        else:
            self.__send(dumps(('_update', task)) + self.__sentinel)

    def _clear_tasks(self, task=Task()):
        """Remove all periodic tasks from the daemon."""
        if not isinstance(task, Task):
            raise TypeError('_clear_task() argument 1 must be a Task, not {}'.format(type(task)))
        if self._is_daemon():
            self.logging.info('Clearing all tasks')
            # Reset everything to its initial state
            self.__periodic_tasks = []
            self.__periodic_dict = {}
            self.__polling_recv = False
            self.__sleep_time = 0
            self.__cycle_time = 0
            self.__elapsed = 0
        else:
            self.__send(dumps(('_clear', task)) + self.__sentinel)

    def run(self):
        """The main process loop for the daemon."""
        used_time = 0
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__sock.bind(self.__address)
        # Allow a backlog of up to 5 queued connections. After this limit is reached, clients
        # will start blocking on the connect command.
        self.__sock.listen(5)
        self.__daemon = True
        self.logging.debug("Daemon started - pid = {}".format(getpid()))

        while True:
            # Convert sleep time to seconds and subtract the time used in the last loop
            sleep_time = self.__sleep_time / 1000.0 - used_time
            if sleep_time > 0:
                sleep(sleep_time)

            loop_start = clock()

            # Execute periodic tasks
            for task in self.__periodic_tasks:
                if self.__elapsed % task.period == 0:
                    self.__execute_task(task)

            # Receive new tasks and execute non-periodic tasks
            self.__update_tasks()

            if self.__elapsed >= self.__cycle_time:
                self.__elapsed = self.__sleep_time
            else:
                self.__elapsed += self.__sleep_time

            used_time = clock() - loop_start
