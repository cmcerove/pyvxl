#!/usr/bin/env python

"""pyvxl's transmit process."""

import logging
from copy import copy, deepcopy
from cPickle import dumps
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
        # Holds references to the current message object.
        self.messages = {}
        # Holds pickled copies of the currently transmitting message object.
        self.message_dumps = {}
        # Holds references to all tasks being executed.
        self.tasks = {}

    def transmit(self, msg_id):
        """Transmit a periodic CAN message."""
        msg = self.messages[msg_id]
        if msg.update_task:
            # Copy the message and remove the update task
            msg_copy = copy(msg)
            msg_copy.update_task = None
            msg.update_task.args = (msg_copy,)
            send_data = msg.update_task.execute(self)
            msg.set_data(send_data)
            logging.debug('Transmit received {}'.format(send_data))
            self.vxl.send(msg.id, send_data)
        else:
            self.vxl.send(msg.id, msg.get_data())

    def transmit_once(self, msg):
        """Transmit a non-periodic CAN message."""
        if msg.update_task:
            # Copy the message and remove the update task
            msg_copy = copy(msg)
            msg_copy.update_task = None
            msg.update_task.args = (msg_copy,)
            send_data = msg.update_task.execute(self)
            msg.set_data(send_data)
            logging.debug('Transmit received {}'.format(send_data))
            self.vxl.send(msg.id, send_data)
        else:
            self.vxl.send(msg.id, msg.get_data())

    def add(self, msg):
        """Begin transmitting a message periodically."""
        if not self.is_daemon():
            if msg.id in self.message_dumps:
                if dumps(msg) == self.message_dumps[msg.id]:
                    # Since the message hasn't changed, the daemon doesn't need
                    # its copy of the task updated. Just retransmit the
                    # message.
                    self.transmit(msg.id)
                else:
                    # Since the message has changed, update the existing task
                    # in the daemon.
                    logging.debug('updating {:X}'.format(msg.id))
                    self.message_dumps[msg.id] = dumps(msg)
                    self.messages[msg.id] = msg
                    # Transmit the new message immediately
                    self.transmit(msg.id)
                    # Since this message already exists in the daemon, it will
                    # know to update the existing task rather than adding
                    # another
                    self.add_task(Task('add', args=(msg,)))
            else:
                # Message is not being sent
                logging.debug('add {:X} {}'.format(msg.id, msg.get_data()))
                msg.sending = True
                self.message_dumps[msg.id] = dumps(msg)
                self.messages[msg.id] = msg
                # Transmit the new message immediately
                self.transmit(msg.id)
                # Add the task to the daemon
                self.add_task(Task('add', args=(msg,)))
        else:
            logging.debug('add(daemon) 0x{:X} {}'.format(msg.id, msg.get_data()))
            if msg.id in self.messages:
                # Update the existing task
                logging.debug('(daemon) updating existing task')
                # Save a copy of the old task
                old_task = self.tasks[msg.id]
                new_task = Task('transmit', args=(msg.id,), period=msg.period)
                self.tasks[msg.id] = new_task
                self.messages[msg.id] = msg
                self.update_task(old_task, new_task)
            else:
                # Add a new task
                logging.debug('(daemon) adding new task')
                new_task = Task('transmit', args=(msg.id,), period=msg.period)
                self.tasks[msg.id] = new_task
                self.messages[msg.id] = msg
                self.add_task(new_task)

    def remove(self, msg):
        """Stop transmitting a message periodically."""
        if not self.is_daemon():
            if msg.id in self.tasks:
                self.add_task(Task('remove', args=(msg,)))
                self.messages.pop(msg.id)
                self.message_copies.pop(msg.id)
                msg.sending = False
            else:
                logging.warning('Msg ID {} is not currently '
                                'being sent'.format(msg.id))
        else:
            logging.debug('(daemon) remove msg id 0x{:X}'.format(msg.id))
            if msg.id in self.messages:
                self.tasks.pop(msg.id)
                self.messages.pop(msg.id)
            else:
                raise AssertionError('(daemon) remove called with an invalid'
                                     ' msg - 0x{:X}'.format(msg.id))

    def remove_all(self):
        """Remove all periodic messages."""
        if not self.is_daemon():
            # Set all messages to not being sent
            for message in self.messages:
                message.sending = False
            self.tasks = []
            self.messages = []
            self.message_copies = []
            self.add_task(Task('remove_all'))
        else:
            self.tasks = []
            self.messages = []
            self.clear_tasks()

    def is_transmitting(self, msg_id=0):
        """Return whether we're transmitting any messages or a specific id."""
        return msg_id in self.messages if msg_id else bool(self.messages)


if __name__ == '__main__':
    args, kwargs = import_args(__file__)
    transmit = Transmit(**kwargs)
    transmit.run()
