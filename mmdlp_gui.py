import sys
import interface
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox, QGraphicsScene, QGraphicsPixmapItem, QLabel, QVBoxLayout
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, Qt, QWaitCondition
from PyQt5.QtGui import QPixmap, QImage

QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
import os
import requests
import yaml
import cv2
import numpy as np
import shutil
import zipfile
import mmdlp as hardware
import time


class ImageWindow(QWidget):
    def __init__(self, screen_geometry):
        super().__init__()
        self.setGeometry(screen_geometry)
        self.initUI()

    def initUI(self):
        # 设置窗口无边框，并且覆盖任务栏
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # 设置背景为黑色，并去除内边距和边框
        self.setStyleSheet("background-color: black; margin: 0px; border: 0px;")

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # 去除布局边距
        layout.addWidget(self.label)
        self.setLayout(layout)

    def showImage(self, pixmap):
        self.label.setPixmap(pixmap)
        self.label.setAlignment(Qt.AlignCenter)


class printThread(QThread):
    finished_sig = pyqtSignal()
    cmd_sig = pyqtSignal(str)

    def __init__(self):
        super(printThread, self).__init__()
        self.sliceName = None
        self.stopPrint_mut = QMutex()
        self.stopPrint = False
        self.cancelPrint_mut = QMutex()
        self.cancelPrint = False
        self.condition = QWaitCondition()
        self.mutex = QMutex()

    def run(self):
        self.cancelPrint = False
        f = open(self.sliceName + 'run.gcode', encoding='utf-8')
        line = f.readline().strip()
        gcode = []
        while line:
            gcode.append(line)
            line = f.readline().strip()
        f.close()
        for i in gcode:
            self.stopPrint_mut.lock()
            self.stopPrint_mut.unlock()
            self.cancelPrint_mut.lock()
            if self.cancelPrint:
                self.cancelPrint_mut.unlock()
                break
            self.cancelPrint_mut.unlock()
            self.cmd_sig.emit(i)
            self.mutex.lock()
            self.condition.wait(self.mutex)
            self.mutex.unlock()
        self.finished_sig.emit()

    def next_command(self):
        self.mutex.lock()
        self.condition.wakeOne()
        self.mutex.unlock()

    def set_sliceName(self, sliceName):
        self.sliceName = sliceName

    def stop_print(self):
        if self.stopPrint:
            self.stopPrint = False
            self.stopPrint_mut.unlock()
        else:
            self.stopPrint = True
            self.stopPrint_mut.lock()

    def cancel_print(self):
        self.cancelPrint_mut.lock()
        self.cancelPrint = True
        self.cancelPrint_mut.unlock()
        self.stopPrint_mut.unlock()


class controlThread(QThread):
    proj = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self):
        super(controlThread, self).__init__()
        self.mmdlp = hardware.MM_DLP(-4.8, 29.42, 5.0, 3134676, 'COM7')
        self.condition = QWaitCondition()
        self.mutex = QMutex()
        self.command = None
        self.sliceName = None

    def run(self):
        while True:
            self.mutex.lock()
            self.condition.wait(self.mutex)
            self.work()
            self.mutex.unlock()
            self.finished.emit()

    def receiveCommand(self, command):
        print(command)
        self.mutex.lock()
        self.command = command
        self.condition.wakeOne()
        self.mutex.unlock()

    def work(self):
        print(self.command)
        print('----------------')
        line = self.command.split()
        if line[0] == 'tank':
            tank = int(line[1])
            if len(line) > 2:
                acc = int(line[2])
                dec = int(line[3])
                speed = int(line[4])
                self.mmdlp.rmortor.setSpeed(acc, dec, speed)
            self.mmdlp.rmortor.moveTank(tank)
        elif line[0] == 'fan':
            if line[1] == 'open':
                self.mmdlp.sensorFanClean.fanOpen()
            elif line[1] == 'close':
                self.mmdlp.sensorFanClean.fanClose()
        elif line[0] == 'clean':
            if line[1] == 'open':
                self.mmdlp.sensorFanClean.cleanOpen()
            elif line[1] == 'close':
                self.mmdlp.sensorFanClean.cleanClose()
        elif line[0] == 'glass':
            pos = float(line[1])
            if len(line) > 2:
                acc = float(line[2])
                dec = float(line[3])
                speed = float(line[4])
                self.mmdlp.zmortor.setGlassSpeed(acc, dec, speed)
            pos = max(pos, -50)
            pos = min(pos, 0)
            self.mmdlp.zmortor.glassMove(pos)
        elif line[0] == 'plate':
            pos = float(line[1])
            if len(line) > 2:
                acc = float(line[2])
                dec = float(line[3])
                speed = float(line[4])
                self.mmdlp.zmortor.setPlateSpeed(acc, dec, speed)
            pos = max(pos, 0)
            pos = min(pos, 160)
            self.mmdlp.zmortor.plateMove(pos)
        elif line[0] == 'proj':
            path = self.sliceName + line[1]
            display_time = float(line[2])
            cur = int(line[3])
            self.proj.emit(path)
            time.sleep(0.2)
            self.mmdlp.projector.setCurrent(cur)
            self.mmdlp.projector.LedOn()
            time.sleep(display_time)
            self.mmdlp.projector.LedOff()
            self.proj.emit('closeWindow')
        elif line[0] == 'feed':
            self.mmdlp.AMS.feed(int(line[1]),int(line[2]))
        elif line[0] == 'wait':
            time.sleep(float(line[1]))
        elif line[0] == 'capture':
            requests.get(url='http://172.25.112.51:8080/gopro/camera/shutter/start')
        elif line[0] == 'cameraMode':
            requests.get(url='http://172.25.112.51:8080/gopro/camera/presets/set_group?id=1001')
            requests.get(url='http://172.25.112.51:8080/gopro/camera/control/wired_usb?p=1')
        elif line[0] == 'z_disable':
            self.mmdlp.zmortor.disableAllActuators()
        elif line[0] == 'z_enable':
            self.mmdlp.zmortor.enableAllActuators()
        elif line[0] == 'projector_close':
            self.mmdlp.projector.LedOff()
        elif line[0] == 'home':
            self.mmdlp.zmortor.plateMove(0)
            self.mmdlp.zmortor.glassMove(0)
        elif line[0] == 'r':
            self.mmdlp.zmortor.enableAllActuators()
            self.mmdlp.zmortor.plateMove(160)
            self.mmdlp.zmortor.glassMove(-50)
            self.mmdlp.rmortor.moveTank(int(line[1]))
        elif line[0] == 'backflow':
            self.mmdlp.AMS.backflow()

    def set_sliceName(self, sliceName):
        self.sliceName = sliceName


class sliceThread(QThread):
    sig = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.sliceName = None
        self.config = None
        self.now_tank = 0

    def run(self):
        change_times = self.work()
        self.sig.emit(change_times)

    def work(self):
        for i in os.listdir(self.sliceName):
            if i[-4:] != 'yaml':
                os.remove(self.sliceName + i)
        with open(self.sliceName + 'config.yaml') as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)
        # -------------------- dp算路径 -----------------------
        layers = []
        for i in range(self.config['material_num']):
            layers.append(0)
            for filename in os.listdir(self.config['img_path_' + str(i)]):
                if filename[-3:] == 'png' and filename[:-4].isdigit():
                    layers[i] = max(layers[i], int(filename[:-4]))
        n = max(layers)
        m = self.config['material_num']
        a = np.zeros((n + 1, m), int)  # a[i][j]表示第i层第j个槽位 图片有几个白色像素
        b = np.zeros((n + 1), int)  # b[i]表示第i层有几个槽位需要打印
        for i in range(1, n + 1):
            for j in range(m):
                if i <= layers[j]:
                    img = cv2.imread('%s%d.png' % (self.config['img_path_%d' % j], i), cv2.IMREAD_GRAYSCALE)
                    a[i][j] = cv2.countNonZero(img)
                    if a[i][j] > 0:
                        b[i] += 1
        f = np.full((n + 1, m), m * n, int)
        g = np.full((n + 1, m), -1, int)
        for j in range(m):
            f[0][j] = 0
        for i in range(1, n + 1):
            for j in range(m):
                if a[i][j] > 0:
                    for k in range(m):
                        if f[i][j] > f[i - 1][k] + b[i] - (1 if a[i][k] > 0 else 0) + (1 if j == k and b[i] > 1 else 0):
                            f[i][j] = f[i - 1][k] + b[i] - (1 if a[i][k] > 0 else 0) + (1 if j == k and b[i] > 1 else 0)
                            g[i][j] = k
        ed_tank = [0]

        change_times = n * m
        for i in range(m):
            if f[n][i] < change_times:
                change_times = f[n][i]
                ed_tank[0] = i

        for i in range(n, 0, -1):
            ed_tank.append(g[i][ed_tank[-1]])
        ed_tank.reverse()
        # -------------------- dp算路径 -----------------------
        f = open(self.sliceName + 'run.gcode', 'w')
        if self.config['lapse']:
            f.write('cameraMode\n')
        f.write('fan open\n')
        f.write('clean open\n')
        f.write('wait 3\n')
        f.write('fan close\n')
        f.write('clean close\n')
        f.write('z_enable\n')
        f.write('plate 150 %.2f %.2f %.2f\n' % (self.config['z_acc2'], self.config['z_dec2'], self.config['z_speed2']))
        f.write('glass -50 %.2f %.2f %.2f\n' % (self.config['z_acc2'], self.config['z_dec2'], self.config['z_speed2']))
        f.write('tank %d %d %d %d\n' % (ed_tank[0], self.config['r_acc'], self.config['r_dec'], self.config['r_speed']))
        f.write('plate %.2f %.2f %.2f %.2f\n' % (self.config['pre_z_height'], self.config['z_acc'], self.config['z_dec'], self.config['z_speed']))
        self.now_tank = ed_tank[0]

        for i in range(1, n + 1):
            if a[i][ed_tank[i - 1]] > 0:
                self.printLayer(ed_tank[i - 1], i, f)

            for j in range(m):
                if a[i][j] > 0 and j != ed_tank[i - 1] and j != ed_tank[i]:
                    self.printLayer(j, i, f)

            if ed_tank[i] != ed_tank[i - 1]:
                self.printLayer(ed_tank[i], i, f)

        f.write('plate %.2f\n' % (self.config['max_height']))
        f.write('glass -50 %.2f %.2f %.2f\n' % (self.config['z_acc2'], self.config['z_dec2'], self.config['z_speed2']))
        if self.config['AMS']:
            f.write('backflow\n')
        f.close()
        return change_times

    def printLayer(self, tank, layer, f):
        print(tank, layer)
        src_img_path = '%s%d.png' % (self.config['img_path_%d' % tank], layer)
        dst_img_path = '%d_%d.png' % (layer, tank)
        # shutil.copyfile(src_img, dst_img)
        src_img = cv2.imread(src_img_path)
        top = (1080 - src_img.shape[0]) // 2
        bottom = (1081 - src_img.shape[0]) // 2
        left = (1920 - src_img.shape[1]) // 2
        right = (1921 - src_img.shape[1]) // 2
        dst_img = cv2.copyMakeBorder(src_img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        cv2.imwrite(self.sliceName + dst_img_path, dst_img)
        height = self.config['layer_height'] * float(layer)
        if self.now_tank != tank:
            f.write('plate %.2f %.2f %.2f %.2f\n' % (
            self.config['pre_z_height'] + height, self.config['z_acc'], self.config['z_dec'], self.config['z_speed']))
            f.write('plate %.2f %.2f %.2f %.2f\n' % (
                self.config['max_height'], self.config['z_acc2'], self.config['z_dec2'], self.config['z_speed2']))
            f.write(
                'glass -50 %.2f %.2f %.2f\n' % (self.config['z_acc2'], self.config['z_dec2'], self.config['z_speed2']))
            f.write('wait %d\n' % (
                self.config['drop_time_0'] if layer < self.config['drop_0_layers'] else self.config['drop_time_1']))

            # --------清洗---------
            f.write('tank %d\n' % self.config['clean_tank'])
            f.write('clean open\n')

            for i in range(self.config['clean_times']):
                f.write(
                    'plate %.2f\n' % (self.config['clean_height'] + height * self.config['clean_height_coefficient']))
                f.write('wait %d\n' % (self.config['clean_time']))
                f.write('plate %.2f\n' % (
                            self.config['clean_height'] + height * self.config['clean_height_coefficient'] + 10.0))

            f.write('plate %.2f\n' % (self.config['max_height']))
            f.write('clean close\n')
            f.write('wait %d\n' % (
                self.config['drop_time_0'] if layer < self.config['drop_0_layers'] else self.config['drop_time_1']))
            # --------清洗---------

            # --------风干---------
            f.write('tank %d\n' % self.config['fan_tank'])
            f.write('plate %.2f\n' % (self.config['dry_height'] + height))
            f.write('fan open\n')
            f.write('wait %d\n' % (
                self.config['dry_time_0'] if layer < self.config['drop_0_layers'] else self.config['dry_time_1']))
            f.write('plate %.2f\n' % (self.config['max_height']))
            f.write('fan close\n')
            # --------风干---------

            # --------加料---------
            if self.config['AMS']:
                if layer < self.config['feed_layers']:
                    f.write('tank %d\n'%(self.now_tank+1))
                    f.write('feed %d %d\n'%(self.now_tank,self.config['feed_rounds']))
            # --------加料---------
            
            # --------延时---------
            if self.config['lapse']:
                f.write('plate %.2f\n' % (self.config['max_height']))
                f.write('tank 0\n')
                f.write('wait 2\n')
                f.write('capture\n')
                f.write('wait 2\n')
            # --------延时---------

            f.write('tank %d\n' % tank)
            f.write('glass 0 %.2f %.2f %.2f\n' % (self.config['z_acc'], self.config['z_dec'], self.config['z_speed']))
            f.write('plate %.2f\n' % (self.config['pre_z_height'] + height))
            f.write('plate %.2f %.2f %.2f %.2f\n' % (
            height, self.config['z_acc'], self.config['z_dec'], self.config['z_speed']))
            self.now_tank = tank
        else:
            f.write('glass %.2f\n' % 0)
            f.write('plate %.2f\n' % (height + self.config['back_distance']))
            f.write('plate %.2f\n' % height)

        f.write('proj %s %.2f %d\n' % (
            dst_img_path,
            self.config['bottom_exposure_time_%d' % self.now_tank] if layer <= self.config['bottom_layers'] else
            self.config[
                'standard_exposure_time_%d' % self.now_tank],
            self.config['bottom_exposure_current_%d' % self.now_tank] if layer <= self.config['bottom_layers'] else
            self.config[
                'standard_exposure_current_%d' % self.now_tank]))

    def set_sliceName(self, sliceName):
        self.sliceName = sliceName


class MainWidget(QWidget):

    def __init__(self, proj_screen_pos, parent=None):
        super(QWidget, self).__init__(parent)
        self.ui = interface.Ui_Form()
        self.ui.setupUi(self)
        self.ui.configEdit.textChanged.connect(self.config_changed)
        self.ui.openConfigButton.clicked.connect(self.open_config)
        self.ui.saveConfigButton.clicked.connect(self.save_config)
        self.ui.sliceButton.clicked.connect(self.slice)
        self.ui.printButton.clicked.connect(self.startPrint)
        self.ui.cancelButton.clicked.connect(self.cancel_print)
        self.ui.stopButton.clicked.connect(self.stopPrint)
        self.ui._001Button.clicked.connect(self._001choose)
        self.ui._01Button.clicked.connect(self._01choose)
        self.ui._1Button.clicked.connect(self._1choose)
        self.ui._10Button.clicked.connect(self._10choose)
        self.ui.cleanButton.clicked.connect(self.clean)
        self.ui.fanButton.clicked.connect(self.fan)
        self.ui.glassChooseButton.clicked.connect(self.glassChoose)
        self.ui.plateChooseButton.clicked.connect(self.plateChoose)
        self.ui.rChooseButton.clicked.connect(self.rChoose)
        self.ui.fallButton.clicked.connect(self.fall)
        self.ui.riseButton.clicked.connect(self.rise)
        self.ui.homeButton.clicked.connect(self.home)
        self.ui.setZeroButton.clicked.connect(self.setZero)
        self.ui.cleanDebrisButton.clicked.connect(self.cleanDebris)
        self.ui.refreshPosButton.clicked.connect(self.refreshPos)
        self.ui.zEnableButton.clicked.connect(self.zEnable)
        self.ui.closeProjButton.clicked.connect(self.closeProj)
        self.ui.feed0Button.clicked.connect(self.feed0)
        self.ui.feed1Button.clicked.connect(self.feed1)
        self.ui.backflowButton.clicked.connect(self.backflow)
        self.step = 0.01
        self.buttonDefaultStyle = """
                QPushButton {
                    font-family: '微软雅黑';
                    font-size: 26px;
                }
            """
        self.buttonHighlightStyle = """
                QPushButton {
                    background-color: lightgreen;
                    font-family: '微软雅黑';
                    font-size: 26px;
                }
            """
        self.ui._001Button.setStyleSheet(self.buttonHighlightStyle)
        self.plate_glass_r_choose = 'plate'
        self.ui.plateChooseButton.setStyleSheet(self.buttonHighlightStyle)
        self.is_cleaning = False
        self.is_fanning = False
        self.is_printing = False
        self.z_is_enable = False
        self.scene = QGraphicsScene()
        self.ui.graphicsView.setScene(self.scene)
        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)
        self.ui.cancelButton.setEnabled(False)
        self.ui.stopButton.setEnabled(False)
        self.ui.sliceButton.setEnabled(False)
        self.imageWindow = None
        self.proj_screen_pos = proj_screen_pos
        self.sliceName = os.getcwd()

        self.sliceThread = sliceThread()
        self.sliceThread.sig.connect(self.sliceThreadFinish)

        self.controlThread = controlThread()
        self.controlThread.finished.connect(self.controlThreadFinish)
        self.controlThread.proj.connect(self.controlThreadProj)
        self.controlThread.start()

        self.printThread = printThread()
        self.printThread.finished_sig.connect(self.printThreadFinish)
        self.printThread.cmd_sig.connect(self.printThreadsendcmd)

    def setButtonEnable(self, flag):
        self.ui.fallButton.setEnabled(flag)
        self.ui.riseButton.setEnabled(flag)
        self.ui.homeButton.setEnabled(flag)
        self.ui.zEnableButton.setEnabled(flag)
        self.ui.closeProjButton.setEnabled(flag)
        self.ui.fanButton.setEnabled(flag)
        self.ui.cleanButton.setEnabled(flag)
        self.ui.feed0Button.setEnabled(flag)
        self.ui.feed1Button.setEnabled(flag)
        self.ui.backflowButton.setEnabled(flag)

    def open_dir(self, dialogName, currentPath):
        dirName = QtWidgets.QFileDialog.getExistingDirectory(self, dialogName, currentPath)
        return dirName

    def save_file(self, dialogName, currentPath, supportType):
        fileName, fileType = QtWidgets.QFileDialog.getSaveFileName(self, dialogName, currentPath, supportType)
        return fileName

    def open_file(self, dialogName, currentPath, supportType):
        fileName, fileType = QtWidgets.QFileDialog.getOpenFileName(self, dialogName, currentPath, supportType)
        return fileName

    def open_config(self):
        fileName = self.open_file("打开配置", os.getcwd(), "config file(*.yaml)")
        if fileName != '':
            self.ui.configPath.setText(fileName)
            with open(fileName, 'r') as f:
                data = f.read()
                self.ui.configEdit.setText(data)

    def save_config(self):
        fileName = self.save_file("保存配置", os.getcwd(), "config file(*.yaml)")
        if fileName != '':
            self.ui.configPath.setText(fileName)
            with open(fileName, 'w') as f:
                f.write(str(self.ui.configEdit.toPlainText()))

    def config_changed(self):
        if self.ui.configEdit.toPlainText() == '':
            self.ui.sliceButton.setEnabled(False)
        else:
            self.ui.sliceButton.setEnabled(True)

    def slice(self):
        self.sliceName = self.open_dir("保存切片文件到文件夹", os.getcwd()) + '/'
        if self.sliceName != '/':
            self.ui.sliceButton.setEnabled(False)
            if not os.path.exists(self.sliceName):
                os.makedirs(self.sliceName)
            with open(self.sliceName + 'config.yaml', 'w') as f:
                f.write(str(self.ui.configEdit.toPlainText()))
            self.ui.configPath.setText(self.sliceName + 'config.yaml')
            self.ui.slicePath.setText(self.sliceName)
            self.sliceThread.set_sliceName(self.sliceName)
            self.sliceThread.start()

    def sliceThreadFinish(self, sig):
        self.ui.sliceButton.setEnabled(True)
        reply = QMessageBox.information(self, '切片完成', '切片完成，切换次数为%d次' % sig, QMessageBox.Yes,
                                        QMessageBox.Yes)

    def controlThreadFinish(self):
        if self.is_printing:
            self.printThread.next_command()
        else:
            self.setButtonEnable(True)

    def controlThreadProj(self, proj):
        if proj == 'closeWindow':
            self.imageWindow.close()
            self.imageWindow = None
            self.pixmapItem.setPixmap(QPixmap())
        else:
            pixmap = QPixmap(proj)
            self.pixmapItem.setPixmap(pixmap)
            self.imageWindow = ImageWindow(self.proj_screen_pos)
            self.imageWindow.showImage(pixmap)
            self.imageWindow.showFullScreen()

    def startPrint(self):
        self.sliceName = self.open_dir("打开切片文件夹", self.sliceName) + '/'
        if self.sliceName == '/' or not os.path.exists(self.sliceName + 'run.gcode'):
            return
        self.ui.slicePath.setText(self.sliceName)
        self.ui.printButton.setEnabled(False)
        self.ui.stopButton.setEnabled(True)
        self.printThread.set_sliceName(self.sliceName)
        self.controlThread.set_sliceName(self.sliceName)
        self.is_printing = True
        self.setButtonEnable(False)
        self.printThread.start()

    def printThreadFinish(self):
        print('finish print')
        self.ui.printButton.setEnabled(True)
        self.ui.stopButton.setEnabled(False)
        self.ui.cancelButton.setEnabled(False)
        self.is_printing = False
        self.setButtonEnable(True)

    def printThreadsendcmd(self, cmd_sig):
        self.controlThread.receiveCommand(cmd_sig)

    def stopPrint(self):
        if self.printThread.stopPrint:
            self.ui.cancelButton.setEnabled(False)
        else:
            self.ui.cancelButton.setEnabled(True)
        self.printThread.stop_print()

    def cancel_print(self):
        self.printThread.cancel_print()

    def _001choose(self):
        self.step = 0.01
        self.ui._001Button.setStyleSheet(self.buttonHighlightStyle)
        self.ui._01Button.setStyleSheet(self.buttonDefaultStyle)
        self.ui._1Button.setStyleSheet(self.buttonDefaultStyle)
        self.ui._10Button.setStyleSheet(self.buttonDefaultStyle)

    def _01choose(self):
        self.step = 0.1
        self.ui._001Button.setStyleSheet(self.buttonDefaultStyle)
        self.ui._01Button.setStyleSheet(self.buttonHighlightStyle)
        self.ui._1Button.setStyleSheet(self.buttonDefaultStyle)
        self.ui._10Button.setStyleSheet(self.buttonDefaultStyle)

    def _1choose(self):
        self.step = 1
        self.ui._001Button.setStyleSheet(self.buttonDefaultStyle)
        self.ui._01Button.setStyleSheet(self.buttonDefaultStyle)
        self.ui._1Button.setStyleSheet(self.buttonHighlightStyle)
        self.ui._10Button.setStyleSheet(self.buttonDefaultStyle)

    def _10choose(self):
        self.step = 10
        self.ui._001Button.setStyleSheet(self.buttonDefaultStyle)
        self.ui._01Button.setStyleSheet(self.buttonDefaultStyle)
        self.ui._1Button.setStyleSheet(self.buttonDefaultStyle)
        self.ui._10Button.setStyleSheet(self.buttonHighlightStyle)

    def plateChoose(self):
        self.plate_glass_r_choose = 'plate'
        self.ui.plateChooseButton.setStyleSheet(self.buttonHighlightStyle)
        self.ui.glassChooseButton.setStyleSheet(self.buttonDefaultStyle)
        self.ui.rChooseButton.setStyleSheet(self.buttonDefaultStyle)

    def glassChoose(self):
        self.plate_glass_r_choose = 'glass'
        self.ui.plateChooseButton.setStyleSheet(self.buttonDefaultStyle)
        self.ui.glassChooseButton.setStyleSheet(self.buttonHighlightStyle)
        self.ui.rChooseButton.setStyleSheet(self.buttonDefaultStyle)

    def rChoose(self):
        self.plate_glass_r_choose = 'r'
        self.ui.plateChooseButton.setStyleSheet(self.buttonDefaultStyle)
        self.ui.glassChooseButton.setStyleSheet(self.buttonDefaultStyle)
        self.ui.rChooseButton.setStyleSheet(self.buttonHighlightStyle)

    def getGlassPos(self):
        return self.controlThread.mmdlp.zmortor.getGlassPos()

    def getPlatePos(self):
        return self.controlThread.mmdlp.zmortor.getPlatePos()

    def rise(self):
        if self.plate_glass_r_choose == 'plate':
            pos = self.getPlatePos() + self.step
            pos = max(pos, 0)
            pos = min(pos, 160)
            self.ui.plateDisplay.setText(str(pos))
        elif self.plate_glass_r_choose == 'glass':
            pos = self.getGlassPos() + self.step
            pos = max(pos, -50)
            pos = min(pos, 0)
            self.ui.glassDisplay.setText(str(pos))
        elif self.plate_glass_r_choose == 'r':
            pos = int((
                                  self.controlThread.mmdlp.rmortor.getPosition() - self.controlThread.mmdlp.rmortor.st_pos) / -104857.0) + 1
            pos = min(pos, 4)
            pos = max(pos, 0)
        self.setButtonEnable(False)
        if self.plate_glass_r_choose == 'r':
            self.controlThread.receiveCommand("%s %d" % (self.plate_glass_r_choose, pos))
        else:
            self.controlThread.receiveCommand("%s %.2f" % (self.plate_glass_r_choose, pos))

    def fall(self):
        if self.plate_glass_r_choose == 'plate':
            pos = self.getPlatePos() - self.step
            pos = max(pos, 0)
            pos = min(pos, 160)
            self.ui.plateDisplay.setText(str(pos))
        elif self.plate_glass_r_choose == 'glass':
            pos = self.getGlassPos() - self.step
            pos = max(pos, -50)
            pos = min(pos, 0)
            self.ui.glassDisplay.setText(str(pos))
        elif self.plate_glass_r_choose == 'r':
            pos = int((
                                  self.controlThread.mmdlp.rmortor.getPosition() - self.controlThread.mmdlp.rmortor.st_pos) / -104857.0) - 1
            pos = min(pos, 4)
            pos = max(pos, 0)
        self.setButtonEnable(False)
        if self.plate_glass_r_choose == 'r':
            self.controlThread.receiveCommand("%s %d" % (self.plate_glass_r_choose, pos))
        else:
            self.controlThread.receiveCommand("%s %.2f" % (self.plate_glass_r_choose, pos))

    def fan(self):
        t = None
        if self.is_fanning:
            t = "fan close"
            self.ui.fanButton.setStyleSheet(self.buttonDefaultStyle)
            self.is_fanning = False
        else:
            t = "fan open"
            self.ui.fanButton.setStyleSheet(self.buttonHighlightStyle)
            self.is_fanning = True
        self.setButtonEnable(False)
        self.controlThread.receiveCommand(t)

    def clean(self):
        t = None
        if self.is_cleaning:
            t = 'clean close'
            self.ui.cleanButton.setStyleSheet(self.buttonDefaultStyle)
            self.is_cleaning = False
        else:
            t = "clean open"
            self.ui.cleanButton.setStyleSheet(self.buttonHighlightStyle)
            self.is_cleaning = True
        self.setButtonEnable(False)
        self.controlThread.receiveCommand(t)

    def home(self):
        self.setButtonEnable(False)
        self.controlThread.receiveCommand('home')

    def refreshPos(self):
        self.ui.plateDisplay.setText("%.2f" % (self.getPlatePos()))
        self.ui.glassDisplay.setText("%.2f" % (self.getGlassPos()))

    def feed0(self):
        self.setButtonEnable(False)
        self.controlThread.receiveCommand('feed 0 10')

    def feed1(self):
        self.setButtonEnable(False)
        self.controlThread.receiveCommand('feed 1 10')

    def backflow(self):
        self.setButtonEnable(False)
        self.controlThread.receiveCommand('backflow')

    def setZero(self):
        pass

    def cleanDebris(self):
        pass

    def zEnable(self):
        t = None
        if self.z_is_enable:
            self.z_is_enable = False
            self.ui.zEnableButton.setStyleSheet(self.buttonDefaultStyle)
            t = 'z_disable'
        else:
            self.z_is_enable = True
            self.ui.zEnableButton.setStyleSheet(self.buttonHighlightStyle)
            t = 'z_enable'
        self.setButtonEnable(False)
        self.controlThread.receiveCommand(t)

    def closeProj(self):
        self.setButtonEnable(False)
        self.controlThread.receiveCommand('projector_close')


app = QApplication(sys.argv)
screens = app.screens()
window = MainWidget(screens[1].geometry())
window.show()
sys.exit(app.exec_())
