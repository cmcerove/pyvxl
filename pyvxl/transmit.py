#!/usr/bin/env python

"""pyvxl's transmit process."""

import logging
from copy import deepcopy
from pywindaemon import Daemon, Task, import_args
from pyvxl.vxl import VxlCan

#logging.basicConfig(level=logging.INFO)

# TODO: Make sure that all locations where dbc data was assumed to be updated in Vector are now
#       properly updating these values in the daemon as well


class Transmit(Daemon):
    """."""

    def __init__(self, channel=0, baudrate=500000):
        """."""
        port = 50100 + 2 * channel
        kwargs = {'channel': channel, 'baudrate': baudrate}
        # Initialize the daemon
        super(Transmit, self).__init__(port=port, file=__file__, kwargs=kwargs)
        self.vxl = VxlCan(channel, baudrate=500000)
        self.vxl.start()
        # A dictionary of all messages being transmitted
        self.messages = {}
        # A dictionary of all tasks being executed
        self.tasks = {}

    def transmit(self, msg, msg_data):
        """Transmit a periodic CAN message."""
        if msg.update_task:
            msg_data = msg.update_task.execute(self)
            logging.debug('Transmit received {}'.format(msg_data))
        self.vxl.send(msg.id, msg_data)

    def update_msg(self, msg):
        """Update a message already being transmitted."""
        if not self.is_daemon():
            logging.debug('update_msg {:X} {:X}'.format(msg.id, msg.data))
            self.add_task(Task('update_msg', args=(msg,)))
        else:
            self.messages[msg.id] = msg

    def add(self, msg, msg_data):
        """Begin transmitting a message periodically."""
        if not self.is_daemon():
            if msg.id in self.messages:
                self.remove(msg)
            logging.debug('add {:X} {:X}'.format(msg.id, msg.data))
            # Store only a copy of the message in the task. This allows msg
            # to change while still being able to use this original task to
            # look up the current task being sent.
            self.tasks[msg.id] = Task('transmit', args=(deepcopy(msg), msg_data),
                                      period=msg.period)
            msg.sending = True
            self.messages[msg.id] = msg
            self.add_task(self.tasks[msg.id])
        else:
            logging.error('Transmit.add() called from the Daemon!')

    def remove(self, msg):
        """Stop transmitting a message periodically."""
        if not self.is_daemon():
            if msg.id in self.messages:
                self.remove_task(self.tasks[msg.id])
                self.tasks.pop(msg.id)
                msg = self.messages.pop(msg.id)
                msg.sending = False
            else:
                logging.warning('Msg ID {} is not currently '
                                'being sent'.format(msg.id))
        else:
            logging.error('Transmit.remove() called from the Daemon!')

    def is_transmitting(self, msg_id=0):
        """Return whether we're transmitting any messages or a specific id."""
        return msg_id in self.messages if msg_id else bool(self.messages)


if __name__ == '__main__':
    args, kwargs = import_args(__file__)
    transmit = Transmit(**kwargs)
    transmit.run()
