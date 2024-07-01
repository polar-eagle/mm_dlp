from ctypes import *
import threading
import time

DevType = c_uint

'''
    Device Type
'''
USBCAN1 = DevType(4)
'''
    Device Index
'''
DevIndex = c_uint(0)  # 设备索引
'''
    Channel
'''
Channel1 = c_uint(0)  # CAN1
'''
    ECAN Status
'''
STATUS_ERR = 0
STATUS_OK = 1

'''
    Device Information
'''


class BoardInfo(Structure):
    _fields_ = [("hw_Version", c_ushort),  # 硬件版本号，用16进制表示
                ("fw_Version", c_ushort),  # 固件版本号，用16进制表示
                ("dr_Version", c_ushort),  # 驱动程序版本号，用16进制表示
                ("in_Version", c_ushort),  # 接口库版本号，用16进制表示
                ("irq_Num", c_ushort),  # 板卡所使用的中断号
                ("can_Num", c_byte),  # 表示有几路CAN通道
                ("str_Serial_Num", c_byte * 20),  # 此板卡的序列号，用ASC码表示
                ("str_hw_Type", c_byte * 40),  # 硬件类型，用ASC码表示
                ("Reserved", c_byte * 4)]  # 系统保留


class CAN_OBJ(Structure):
    _fields_ = [("ID", c_uint),  # 报文帧ID
                ("TimeStamp", c_uint),  # 接收到信息帧时的时间标识，从CAN控制器初始化开始计时，单位微秒
                ("TimeFlag", c_byte),  # 是否使用时间标识，为1时TimeStamp有效，TimeFlag和TimeStamp只在此帧为接收帧时有意义。
                ("SendType", c_byte),
                # 发送帧类型。=0时为正常发送，=1时为单次发送（不自动重发），=2时为自发自收（用于测试CAN卡是否损坏），=3时为单次自发自收（只发送一次，用于自测试），只在此帧为发送帧时有意义
                ("RemoteFlag", c_byte),  # 是否是远程帧。=0时为数据帧，=1时为远程帧
                ("ExternFlag", c_byte),  # 是否是扩展帧。=0时为标准帧（11位帧ID），=1时为扩展帧（29位帧ID）
                ("DataLen", c_byte),  # 数据长度DLC(<=8)，即Data的长度
                ("data", c_ubyte * 8),  # CAN报文的数据。空间受DataLen的约束
                ("Reserved", c_byte * 3)]  # 系统保留。


class INIT_CONFIG(Structure):
    _fields_ = [("acccode", c_uint32),  # 验收码。SJA1000的帧过滤验收码
                ("accmask", c_uint32),  # 屏蔽码。SJA1000的帧过滤屏蔽码。屏蔽码推荐设置为0xFFFF FFFF，即全部接收
                ("reserved", c_uint32),  # 保留
                ("filter", c_byte),  # 滤波使能。0=不使能，1=使能。使能时，请参照SJA1000验收滤波器设置验收码和屏蔽码
                ("timing0", c_byte),  # 波特率定时器0,详见动态库使用说明书7页
                ("timing1", c_byte),  # 波特率定时器1,详见动态库使用说明书7页
                ("mode", c_byte)]  # 模式。=0为正常模式，=1为只听模式，=2为自发自收模式。


class ECAN(object):
    def __init__(self):
        self.dll = cdll.LoadLibrary('./libs/ECanVci64.dll')
        if self.dll == None:
            print("DLL Couldn't be loaded")

    def OpenDevice(self, DeviceType, DeviceIndex):
        try:
            return self.dll.OpenDevice(DeviceType, DeviceIndex, 0)
        except:
            print("Exception on OpenDevice!")
            raise

    def CloseDevice(self, DeviceType, DeviceIndex):
        try:
            return self.dll.CloseDevice(DeviceType, DeviceIndex, 0)
        except:
            print("Exception on CloseDevice!")
            raise

    def InitCan(self, DeviceType, DeviceIndex, CanInd, Initconfig):
        try:
            return self.dll.InitCAN(DeviceType, DeviceIndex, CanInd, byref(Initconfig))
        except:
            print("Exception on InitCan!")
            raise

    def StartCan(self, DeviceType, DeviceIndex, CanInd):
        try:
            return self.dll.StartCAN(DeviceType, DeviceIndex, CanInd)
        except:
            print("Exception on StartCan!")
            raise

    def ReadBoardInfo(self, DeviceType, DeviceIndex):
        try:
            mboardinfo = BoardInfo()
            ret = self.dll.ReadBoardInfo(DeviceType, DeviceIndex, byref(mboardinfo))
            return mboardinfo, ret
        except:
            print("Exception on ReadBoardInfo!")
            raise

    def Receivce(self, DeviceType, DeviceIndex, CanInd, length):
        try:
            recmess = (CAN_OBJ * length)()
            ret = self.dll.Receive(DeviceType, DeviceIndex, CanInd, byref(recmess), length, 0)
            return length, recmess, ret
        except:
            print("Exception on Receive!")
            raise

    def Tramsmit(self, DeviceType, DeviceIndex, CanInd, mcanobj):
        try:
            # mCAN_OBJ=CAN_OBJ*2
            # self.dll.Transmit.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, POINTER(CAN_OBJ),
            # ctypes.c_uint16]
            return self.dll.Transmit(DeviceType, DeviceIndex, CanInd, byref(mcanobj), c_uint16(1))
        except:
            print("Exception on Tramsmit!")
            raise


class RMortor:

    def __init__(self,st_pos):
        self.ecan = ECAN()
        self.musbcanopen = False
        self.t = threading.Timer(0.03, self.ReadCAN)
        self.lock = threading.RLock()
        self.buffer = None
        self.caninit()
        self.st_pos = st_pos
        self.tank = [self.st_pos]#1903534
        for i in range(4):
            self.tank.append(self.tank[-1] - 104857)

    def ReadCAN(self):
        if (self.musbcanopen == True):
            scount = 0
            while (scount < 50):
                scount = scount + 1
                len, rec, ret = self.ecan.Receivce(USBCAN1, DevIndex, Channel1, 1)
                # print(rec[0].DataLen)
                if (len > 0 and ret == 1):
                    # for i in range(0, rec[0].DataLen):
                    #     print(rec[0].data[i])
                    if rec[0].DataLen == 5:
                        self.lock.acquire()
                        self.buffer = rec[0].data[0] * (16 ** 6) + rec[0].data[1] * (16 ** 4) + rec[0].data[2] * (
                                16 ** 2) + rec[0].data[3]
                        self.lock.release()

            self.t = threading.Timer(0.03, self.ReadCAN)
            self.t.start()

    def caninit(self):
        if (self.musbcanopen == False):
            initconfig = INIT_CONFIG()
            initconfig.acccode = 0  # 设置验收码
            initconfig.accmask = 0xFFFFFFFF  # 设置屏蔽码
            initconfig.filter = 0  # 设置滤波使能
            # 打开设备
            if (self.ecan.OpenDevice(USBCAN1, DevIndex) != STATUS_OK):
                print("ERROR", "Open CAN1 Failed!")
                return
            initconfig.timing0, initconfig.timing1 = self.getTiming("1M")
            initconfig.mode = 0
            # 初始化CAN1
            if (self.ecan.InitCan(USBCAN1, DevIndex, Channel1, initconfig) != STATUS_OK):
                print("ERROR", "InitCan CAN Failed!")
                self.ecan.CloseDevice(USBCAN1, DevIndex)
                return
            if (self.ecan.StartCan(USBCAN1, DevIndex, Channel1) != STATUS_OK):
                print("ERROR", "StartCan CAN Failed!")
                self.ecan.CloseDevice(USBCAN1, DevIndex)
                return
            self.musbcanopen = True
            print('open')
            self.t = threading.Timer(0.03, self.ReadCAN)
            self.t.start()
        else:
            self.musbcanopen = False
            self.ecan.CloseDevice(USBCAN1, DevIndex)

    def closeCan(self):
        self.ecan.CloseDevice(USBCAN1, DevIndex)

    def getTiming(self, mbaud):
        if mbaud == "1M":
            return 0, 0x14
        if mbaud == "800k":
            return 0, 0x16
        if mbaud == "666k":
            return 0x80, 0xb6
        if mbaud == "500k":
            return 0, 0x1c
        if mbaud == "400k":
            return 0x80, 0xfa
        if mbaud == "250k":
            return 0x01, 0x1c
        if mbaud == "200k":
            return 0x81, 0xfa
        if mbaud == "125k":
            return 0x03, 0x1c
        if mbaud == "100k":
            return 0x04, 0x1c
        if mbaud == "80k":
            return 0x83, 0xff
        if mbaud == "50k":
            return 0x09, 0x1c

    def sendcan(self, data):
        if (self.musbcanopen == False):
            return ""
        else:
            canobj = CAN_OBJ()
            canobj.ID = int('64B', 16)
            canobj.DataLen = int(data[0])
            for i in range(data[0]):
                canobj.data[i] = int(data[i + 1], 16)

            canobj.RemoteFlag = 0
            canobj.ExternFlag = 0
            self.ecan.Tramsmit(USBCAN1, DevIndex, Channel1, canobj)

    def trans(self, x):
        return [str(hex(x // (16 ** 6))), str(hex(x % (16 ** 6) // (16 ** 4))), str(hex(x % (16 ** 4) // (16 ** 2))),
                str(hex(x % (16 ** 2)))]

    def setPositionMode(self):
        # 位置控制
        self.sendcan([6, '00', '4E', '00', '00', '00', '03'])
        # 绝对位置运动
        self.sendcan([6, '00', '8D', '00', '00', '00', '01'])

    def setSpeed(self, acc, dec, speed):
        # 加速度
        self.sendcan([6, '00', '88'] + self.trans(acc))
        # 减速度
        self.sendcan([6, '00', '89'] + self.trans(dec))
        # 速度
        self.sendcan([6, '00', '8A'] + self.trans(speed))

    def enable(self):
        # 使能
        self.sendcan([6, '01', '00', '00', '00', '00', '01'])

    def disable(self):
        # 下使能
        self.sendcan([6, '01', '00', '00', '00', '00', '00'])

    def setPosition(self, pos):
        # 目标位置
        self.sendcan([6, '00', '86'] + self.trans(pos))

    def startMove(self):
        # 开始运动
        self.sendcan([2, '00', '83'])

    def stopMove(self):
        # 停止运动
        self.sendcan([2, '00', '84'])

    def getSpeed(self):
        # 读取速度
        self.sendcan([4, '00', '05', '00', '01'])
        time.sleep(0.1)
        self.lock.acquire()
        t = self.buffer
        self.lock.release()
        return t

    def getPosition(self):
        # 读取位置
        self.sendcan([2, '00', '02'])
        time.sleep(0.1)
        self.lock.acquire()
        t = self.buffer
        self.lock.release()
        return t

    def getCurrent(self):
        # 读取电流
        self.sendcan([2, '00', '08'])
        time.sleep(0.1)
        self.lock.acquire()
        t = self.buffer
        self.lock.release()
        return t

    def moveTank(self, n):
        self.setPositionMode()
        self.setSpeed(10000, 10000, 20000)
        self.enable()
        target_pos = self.tank[n]
        self.setPosition(target_pos)
        self.startMove()
        while abs(self.getPosition() - target_pos) > 2:
            # if self.getCurrent() > :
            #     self.stopMove()
            time.sleep(0.1)
        self.disable()
