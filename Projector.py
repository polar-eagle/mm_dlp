import ctypes
import sys
import time
import threading
from PyQt5.QtWidgets import QApplication, QLabel, QDesktopWidget, QMainWindow
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap

'''
LIBUSB3DPRINTER_API void Delay10Ms(U16 m10s);
LIBUSB3DPRINTER_API void Delay1Ms(U16 ms);

LIBUSB3DPRINTER_API unsigned char GetStatus(void);
LIBUSB3DPRINTER_API Bool LedOnOff(U8 index,unsigned char flag);
LIBUSB3DPRINTER_API Bool GetCurrent(U8 index,U8 *Value);
LIBUSB3DPRINTER_API Bool SetCurrent(U8 index,U8 Value);
LIBUSB3DPRINTER_API Bool Flip(unsigned char FlipX,unsigned char FlipY);
LIBUSB3DPRINTER_API unsigned char  GetProductID(unsigned char *pID);
LIBUSB3DPRINTER_API unsigned char GetSysStatus(void);
LIBUSB3DPRINTER_API unsigned char PowerOnOff(unsigned char flag);
LIBUSB3DPRINTER_API Bool GetLedDefaultStatus(U8 *flag);
LIBUSB3DPRINTER_API Bool SetLedDefaultStatus(U8 flag);
LIBUSB3DPRINTER_API Bool GetTemperature(S16 *Temperature);
LIBUSB3DPRINTER_API Bool GetUseTime(U32 *UseTime);
LIBUSB3DPRINTER_API Bool GetMyVersion(U16 *Value);
//LIBUSB3DPRINTER_API Bool ShakeHands(U8 dwPort,U32 dwBaudRate);
LIBUSB3DPRINTER_API unsigned char  GetLedSourceSwitch(unsigned char *flag);
LIBUSB3DPRINTER_API Bool LedSourceSwitce(unsigned char flag);

//LIBUSB3DPRINTER_API unsigned char CheckUsbVidPid(char *DevicePath,int vendorID,int productID);
LIBUSB3DPRINTER_API unsigned char EnumUsbDevice(void);//枚举符合本产品的USB设备,返回值为USB设备数量
LIBUSB3DPRINTER_API void SetUsbDeviceIndex(unsigned char UsbIndex);//UsbIndex>=0,设置USB设备索引,当有多个USB设备时,用于选择需要控制哪个USB设备
LIBUSB3DPRINTER_API void GetUsbDeviceSerial(unsigned char UsbIndex,char *SerialNo);//返回指定USB设备索引的序列号
LIBUSB3DPRINTER_API unsigned char CheckUSBOnline(void);//用于检查当前选择的USB设备是否断开连接
'''


class FullScreenImageWindow(QMainWindow):
    def __init__(self, image_path, screen_index):
        super().__init__()

        # Load the image
        pixmap = QPixmap(image_path)

        # Get the screen geometry of the specified screen index
        screen = QDesktopWidget().screenGeometry(screen_index)

        # Set QMainWindow properties
        self.setGeometry(screen)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Create a QLabel to display the image and add it to the QMainWindow
        label = QLabel(self)
        label.setPixmap(pixmap)
        label.setGeometry(0, 0, screen.width(), screen.height())

        # Show the window
        self.showFullScreen()


    def close_window(self):
        self.close()


class Projector:
    def __init__(self):
        self.USB3DPrinter = ctypes.CDLL('./libs/LibUSB3DPrinter-x64.dll')
        self.USB3DPrinter.EnumUsbDevice()
        flag = self.USB3DPrinter.CheckUSBOnline()
        print(flag)
        if not flag:
            print('Open projector failed')

    def setCurrent(self, current):
        self.USB3DPrinter.SetCurrent(0, current)

    def LedOn(self):
        self.USB3DPrinter.LedOnOff(0, True)

    def LedOff(self):
        self.USB3DPrinter.LedOnOff(0, False)

    def Delay10Ms(self, t):
        self.USB3DPrinter.Delay10Ms(t)

    def Delay1Ms(self, t):
        self.USB3DPrinter.Delay1Ms(t)




    def showOnProj(self, imagePath, screenIndex, displayTime, current):
        print('tttt')
        self.window = FullScreenImageWindow(imagePath, screenIndex)
        self.Delay10Ms(20)
        self.setCurrent(current)
        self.LedOn()
        self.Delay10Ms(int(displayTime * 100))
        self.LedOff()
        self.window.close()