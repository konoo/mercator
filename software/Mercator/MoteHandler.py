import copy
import threading
import struct

import serial

import Hdlc
import MercatorDefines as d

class MoteHandler(threading.Thread):
    
    _BAUDRATE = 115200
    
    STAT_UARTNUMRXCRCOK      = 'uartNumRxCrcOk'
    STAT_UARTNUMRXCRCWRONG   = 'uartNumRxCrcWrong'
    STAT_UARTNUMTX           = 'uartNumTx'
    
    def __init__(self,serialport,cb_respNotif=None):
        
        self.serialport      = serialport
        self.cb_respNotif    = cb_respNotif
        self.serialLock      = threading.Lock()
        self.dataLock        = threading.RLock()
        self.hdlc            = Hdlc.Hdlc()
        self.busyReceiving   = False
        self.inputBuf        = ''
        self.lastRxByte      = self.hdlc.HDLC_FLAG
        self.goOn            = True
        self._resetStats()
        self.serial          = serial.Serial(self.serialport,self._BAUDRATE)
        
        threading.Thread.__init__(self)
        self.name = serialport
        
        self.start()
    
    #======================== thread ==========================================
    
    def run(self):
        
        while self.goOn:
            
            rxByte = self.serial.read(1)
            
            with self.dataLock:
                if      (
                            (not self.busyReceiving)             and 
                            self.lastRxByte==self.hdlc.HDLC_FLAG and
                            rxByte!=self.hdlc.HDLC_FLAG
                        ):
                    # start of frame
                    
                    self.busyReceiving       = True
                    self.inputBuf            = self.hdlc.HDLC_FLAG
                    self.inputBuf           += rxByte
                elif    (
                            self.busyReceiving                   and
                            rxByte!=self.hdlc.HDLC_FLAG
                        ):
                    # middle of frame
                    
                    self.inputBuf           += rxByte
                elif    (
                            self.busyReceiving                   and
                            rxByte==self.hdlc.HDLC_FLAG
                        ):
                    # end of frame
                    
                    self.busyReceiving       = False
                    self.inputBuf           += rxByte
                    
                    try:
                        self.inputBuf        = self.hdlc.dehdlcify(self.inputBuf)
                    except Hdlc.HdlcException as err:
                        self.stats[self.STAT_UARTNUMRXCRCWRONG] += 1
                    else:
                        self.stats[self.STAT_UARTNUMRXCRCOK] += 1
                        self._handle_inputBuf([ord(b) for b in self.inputBuf])
                
                self.lastRxByte = rxByte
    
    #======================== public ==========================================
    
    #=== stats
    
    def getStats(self):
        with self.dataLock:
            return copy.deepcopy(self.stats)
    
    #=== requests
    
    def send_REQ_ST(self):
        self._send(
            struct.pack(
                '>B',
                d.TYPE_REQ_ST,
            )
        )
    
    def send_REQ_IDLE(self):
        self._send(
            struct.pack(
                '>B',
                d.TYPE_REQ_IDLE,
            )
        )
    
    def send_REQ_TX(self,frequency,txpower,transctr,txnumpk,txifdur,txlength,txfillbyte):
        self._send(
            struct.pack(
                '>BBbBHHBB',
                d.TYPE_REQ_TX,
                frequency,
                txpower,
                transctr,
                txnumpk,
                txifdur,
                txlength,
                txfillbyte,
            )
        )
    
    def send_REQ_RX(self,frequency,srcmac,transctr,txlength,txfillbyte):
        [m0,m1,m2,m3,m4,m5,m6,m7] = srcmac
        self._send(
            struct.pack(
                '>BBBBBBBBBBBBB',
                d.TYPE_REQ_RX,
                frequency,
                m0,m1,m2,m3,m4,m5,m6,m7,
                transctr,
                txlength,
                txfillbyte,
            )
        )
    
    #======================== private =========================================
    
    #=== stats
    
    def _resetStats(self):
        with self.dataLock:
            self.stats = {
                self.STAT_UARTNUMRXCRCOK       : 0,
                self.STAT_UARTNUMRXCRCWRONG    : 0,
                self.STAT_UARTNUMTX            : 0,
            }
    
    #=== serial rx
    
    def _handle_inputBuf(self,inputBuf):
        print inputBuf
    
    #=== serial tx
    
    def _send(self,dataToSend):
        with self.dataLock:
            self.stats[self.STAT_UARTNUMTX] += 1
        with self.serialLock:
            self.serial.write(self.hdlc.hdlcify(dataToSend))
    