from ctypes import *
import os
import sys

import usb_device
import gpio


class SensorFanClean:
    def __init__(self):
        self.sensor1_pin = 5
        self.sensor2_pin = 6
        self.fan_pin = 8
        self.clean_pin = 0

        usb_device.SerialNumbers = (c_int * 20)()
        self.sn = 0
        # Scan device
        ret = usb_device.UsbDevice_Scan(byref(usb_device.SerialNumbers))
        if (0 > ret):
            print("Error: %d" % ret)
            exit()
        elif (ret == 0):
            print("No device!")
            exit()
        else:
            for i in range(ret):
                print("Dev%d SN: %d" % (i, usb_device.SerialNumbers[i]))

        self.sn = usb_device.SerialNumbers[0]  # 选择设备0

        ret3 = gpio.IO_InitPin(self.sn, self.fan_pin, 1, 0)
        if (0 > ret3):
            print("error: %d" % ret3)
        ret4 = gpio.IO_InitPin(self.sn, self.clean_pin, 1, 0)
        if (0 > ret4):
            print("error: %d" % ret4)


    # IO_InitPin -> sn, _pin_, mode 0为输入, pull

    def sensor1_read(self):
        ret1 = gpio.IO_InitPin(self.sn, self.sensor2_pin, 0, 0)
        if (0 > ret1):
            print("error: %d" % ret1)

        PinState = (c_int)()
        gpio.IO_ReadPin(self.sn, self.sensor1_pin, byref(PinState))
        return PinState.value

    def sensor2_read(self):
        ret2 = gpio.IO_InitPin(self.sn, self.sensor2_pin, 0, 0)
        if (0 > ret2):
            print("error: %d" % ret2)

        PinState = (c_int)()
        gpio.IO_ReadPin(self.sn, self.sensor2_pin, byref(PinState))
        return PinState.value

    def fanOpen(self):
        # 控制Px输出高电平
        # IO_WritePin -> sn, _pin_, pinstate
        ret = gpio.IO_WritePin(self.sn, self.fan_pin, 0)
        if (0 > ret):
            print("error: %d" % ret)
        #time.sleep(5)

    def fanClose(self):
        # 控制Px输出低电平
        # IO_WritePin -> sn, _pin_, pinstate
        ret = gpio.IO_WritePin(self.sn, self.fan_pin, 1)
        if (0 > ret):
            print("error: %d" % ret)
    def cleanOpen(self):
        # 控制Px输出高电平
        # IO_WritePin -> sn, _pin_, pinstate
        ret = gpio.IO_WritePin(self.sn, self.clean_pin, 0)
        if (0 > ret):
            print("error: %d" % ret)

    def cleanClose(self):
        # 控制Px输出低电平
        # IO_WritePin -> sn, _pin_, pinstate
        ret = gpio.IO_WritePin(self.sn, self.clean_pin, 1)
        if (0 > ret):
            print("error: %d" % ret)