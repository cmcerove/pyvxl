#!/usr/bin/env python

"""pyvxl's receive process."""

import logging
from pywindaemon.daemon import Daemon
from pyvxl.vxl import VxlCan

logging.basicConfig(level=logging.INFO)


class Receive(Daemon):
    """."""

    def __init__(self, channel=0, baudrate=500000):
        """."""
        port = 50100 + 2 * channel + 1
        # Initialize the daemon
        super(Receive, self).__init__(port=port, file=__file__)
        self.vxl = VxlCan(channel, baudrate=500000)
        self.vxl.start()
        self.messages = {}

    def start(self):
        pass

    def errors_found(self):
        """Return True if there have been CAN errors."""
        raise NotImplementedError


class messageToFind(object):
    """Helper class for the receive thread."""

    def __init__(self, msgID, data, mask):
        """."""
        self.msgID = msgID
        self.data = data
        self.mask = mask
        self.rxFrames = []

    def getFirstMessage(self):
        """ Returns the first found message """
        resp = None
        if self.rxFrames:
            resp = self.rxFrames[0]
            self.rxFrames = self.rxFrames[1:]
        return resp

    def getAllMessages(self):
        """ Returns all found messages """
        # Copy the list so we don't return the erased version
        resp = list(self.rxFrames)
        self.rxFrames = []
        return resp

'''
class receiveThread(Thread):
    """Receive thread for receiving CAN messages"""
    def __init__(self, stpevent, portHandle, msgEvent):
        super(receiveThread, self).__init__()
        self.daemon = True  # thread will die with the program
        self.stopped = stpevent
        self.portHandle = portHandle
        rxEvent = event()
        self.rxEventPtr = pointer(rxEvent)
        msg = c_uint(1)
        self.msgPtr = pointer(msg)
        self.msgEvent = msgEvent
        flushRxQueue(portHandle)
        resetClock(portHandle)
        self.logging = False
        self.outfile = None
        self.errorsFound = False
        self.messagesToFind = {}
        self.messages = []
        self.outfile = None

    def run(self):  # pylint: disable=R0912,R0914
        # Main receive loop. Runs every 1ms
        while not self.stopped.wait(0.01):
            # Blocks until a message is received or the timeout (ms) expires.
            # This event is passed to vxlApi via the setNotification function.
            # TODO: look into why setNotification isn't working and either
            #       remove or fix this.
            # WaitForSingleObject(self.msgEvent, 1)
            msg = c_uint(1)
            self.msgPtr = pointer(msg)
            status = 0
            received = False
            rxMsgs = []
            while not status:
                rxmsg = self.vxl.receive()
                status = receiveMsg(self.portHandle, self.msgPtr,
                                    self.rxEventPtr)
                if str(getError(status)) != 'XL_ERR_QUEUE_IS_EMPTY':
                    received = True
                    rxmsg = str(getEventStr(self.rxEventPtr)).split()
                    noError = 'error' not in rxmsg[4].lower()
                    if not noError:
                        self.errorsFound = True
                    else:
                        self.errorsFound = False

                    if noError and 'chip' not in rxmsg[0].lower():
                        # TODO: Figure out which part of the message determines
                        # absolute/relative
                        # print ' '.join(rxmsg)
                        tstamp = float(rxmsg[2][2:-1])
                        tstamp = str(tstamp/1000000000.0).split('.')
                        decVals = tstamp[1][:6]+((7-len(tstamp[1][:6]))*' ')
                        tstamp = ((4-len(tstamp[0]))*' ')+tstamp[0]+'.'+decVals
                        msgid = rxmsg[3][3:]
                        if len(msgid) > 4:
                            try:
                                msgid = hex(int(msgid, 16)&0x1FFFFFFF)[2:-1]+'x'
                            except ValueError:
                                print(' '.join(rxmsg))
                        msgid = msgid+((16-len(msgid))*' ')
                        dlc = rxmsg[4][2]+' '
                        io = 'Rx   d'
                        if int(dlc) > 0:
                            if rxmsg[6].lower() == 'tx':
                                io = 'Tx   d'
                        data = ''
                        if int(dlc) > 0:
                            data = ' '.join(findall('..?', rxmsg[5]))
                        data += '\n'
                        chan = str(int(math.pow(2, int(rxmsg[1][2:-1]))))
                        rxMsgs.append(tstamp+' '+chan+' '+msgid+io+dlc+data)
                        if self.messagesToFind:
                            msgid = int(rxmsg[3][3:], 16)
                            if msgid > 0xFFF:
                                msgid = msgid&0x1FFFFFFF
                            data = ''.join(findall('..?', rxmsg[5]))

                            # Is the received message one we're looking for?
                            if self.messagesToFind.has_key(msgid):
                                fndMsg = ''.join(findall('[0-9A-F][0-9A-F]?',
                                                         rxmsg[5]))
                                txt = 'Received CAN Msg: '+hex(msgid)
                                logging.info(txt+' Data: '+fndMsg)
                                storeMsg = False
                                # Are we also looking for specific data?
                                searchData = self.messagesToFind[msgid].data
                                mask = self.messagesToFind[msgid].mask
                                if searchData:
                                    try:
                                        data = int(data, 16) & mask
                                        if data == searchData:
                                            storeMsg = True
                                    except ValueError:
                                        pass
                                else:
                                    storeMsg = True

                                if storeMsg:
                                    self.messagesToFind[msgid].rxFrames.append(fndMsg)
                                    self.messages.append((msgid, fndMsg))
                elif received:
                    if self.logging:
                        self.outfile.writelines(rxMsgs)
            if self.logging:
                self.outfile.flush()
        if self.logging:
            self.outfile.close()

    def searchFor(self, msgID, data, mask):
        """Sets the variables needed to wait for a CAN message"""
        resp = False
        if not self.messagesToFind or \
                (self.messagesToFind and msgID not in self.messagesToFind):
            self.messagesToFind[msgID] = messageToFind(msgID, data, mask)
            resp = True
        return resp

    def stopSearchingFor(self, msgID):
        resp = False
        if self.messagesToFind:
            if self.messagesToFind.has_key(msgID):
                resp = True
                if len(self.messagesToFind) == 1:
                    self.clearSearchQueue()
                else:
                    del self.messagesToFind[msgID]
            else:
                logging.error('Message ID not in the receive queue!')
        else:
            logging.error('No messages in the search queue!')
        return resp

    def _getRxMessages(self, msgID, single=False):
        resp = False
        if msgID:
            if self.messagesToFind.has_key(msgID):
                if single:
                    resp = self.messagesToFind[msgID].getFirstMessage()
                else:
                    resp = self.messagesToFind[msgID].getAllMessages()
        else:
            if single:
                resp = self.messages[0]
                self.messages = self.messages[1:]
            else:
                resp = list(self.messages)
                self.messages = []
        return resp

    def getFirstRxMessage(self, msgID):
        """Removes the first received message and returns it"""
        return self._getRxMessages(msgID, single=True)

    def getAllRxMessages(self, msgID):
        """Removes all received messages and returns them"""
        return self._getRxMessages(msgID)

    def clearSearchQueue(self):
        self.messages = []
        self.messagesToFind = {}
        self.errorsFound = False
        return

    def logTo(self, path):
        """Begins logging the CAN bus"""
        if not self.logging:
            self.logging = True
            tmstr = time.localtime()
            hr = tmstr.tm_hour
            hr = str(hr) if hr < 12 else str(hr-12)
            mn = str(tmstr.tm_min)
            sc = str(tmstr.tm_sec)
            mo = tmstr.tm_mon
            da = str(tmstr.tm_mday)
            wda = tmstr.tm_wday
            yr = str(tmstr.tm_year)
            path = path+'['+hr+'-'+mn+'-'+sc+'].asc'
            if os.path.isfile(path):
                path = path[:-4]+'_1.asc'
            logging.info('Logging to: '+os.getcwd()+'\\'+path)
            self.outfile = open(path, 'w+')
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                      'Sep', 'Oct', 'Nov', 'Dec']
            enddate = months[mo-1]+' '+da+' '+hr+':'+mn+':'+sc+' '+yr+'\n'
            dateLine = 'date '+days[wda]+' '+enddate
            lines = [dateLine, 'base hex  timestamps absolute\n',
                     'no internal events logged\n']
            self.outfile.writelines(lines)
        return ''

    def stopLogging(self):
        """Stop logging."""
        if self.logging:
            self.logging = False
            self.outfile.close()
'''
