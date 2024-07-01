import sys
import interface
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox, QGraphicsScene, QGraphicsPixmapItem, QLabel, QVBoxLayout
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, Qt
from PyQt5.QtGui import QPixmap, QImage

QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
import os
import requests
import yaml
import cv2
import numpy as np
import shutil
import zipfile
import mmdlp
import time

global sliceName, cmdBuffer, proj_screen_pos, cancelprint
sliceName = os.getcwd()
cmdBuffer = None
idle_mut = QMutex()
cancelprint = False
cancelprint_mut = QMutex()
stopprint_mut = QMutex()

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
    sig = pyqtSignal(str)

    def __init__(self):
        super(printThread, self).__init__()

    def run(self):
        global sliceName
        f = open(sliceName + 'run.gcode', encoding='utf-8')
        line = f.readline().strip()
        gcode = []
        while line:
            gcode.append(line)
            line = f.readline().strip()
        f.close()
        for i in gcode:
            stopprint_mut.lock()
            stopprint_mut.unlock()
            cancelprint_mut.lock()
            global cancelprint
            if cancelprint:
                cancelprint_mut.unlock()
                break
            cancelprint_mut.unlock()
            idle_mut.lock()
            global cmdBuffer
            cmdBuffer = i
            print(i)
            self.sig.emit('run')
        self.sig.emit('finish')

class controlThread(QThread):
    sig = pyqtSignal(str)

    def __init__(self):
        super(controlThread, self).__init__()
        self.mmdlp = mmdlp.MM_DLP(-4.8,29.52,5.0,3134676)
        self.imageWindow = None

    def run(self):
        print('reading cmdBuffer')
        global cmdBuffer
        cur_cmd = cmdBuffer
        print(cur_cmd)
        line = cur_cmd.split()
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
            pos = max(pos,-50)
            pos = min(pos,0)
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
            global sliceName
            path = sliceName + line[1]
            display_time = float(line[2])
            cur = int(line[3])
            self.sig.emit(path)
            time.sleep(0.2)
            self.mmdlp.projector.setCurrent(cur)
            self.mmdlp.projector.LedOn()
            time.sleep(display_time)
            self.mmdlp.projector.LedOff()
            self.sig.emit('closeWindow')
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
            self.mmdlp.zmortor.plateMove(80)
            self.mmdlp.zmortor.glassMove(-50)
            self.mmdlp.rmortor.moveTank(int(line[1]))
        print('emit sig finish')
        self.sig.emit('finish')

class sliceThread(QThread):
    sig = pyqtSignal(int)

    def run(self):
        global sliceName
        for i in os.listdir(sliceName):
            if i[-4:] != 'yaml':
                os.remove(sliceName + i)
        with open(sliceName + 'config.yaml') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        # -------------------- dp算路径 -----------------------
        layers = []
        for i in range(config['material_num']):
            layers.append(0)
            for filename in os.listdir(config['img_path_' + str(i)]):
                if filename[-3:] == 'png' and filename[:-4].isdigit():
                    layers[i] = max(layers[i], int(filename[:-4]))
        n = max(layers)

        m = config['material_num']
        a = np.zeros((n + 1, m), int)  # a[i][j]表示第i层第j个槽位 图片有几个白色像素
        b = np.zeros((n + 1), int)  # b[i]表示第i层有几个槽位需要打印
        for i in range(1, n + 1):
            for j in range(m):
                if i <= layers[j]:
                    img = cv2.imread('%s%d.png' % (config['img_path_%d' % j], i), cv2.IMREAD_GRAYSCALE)
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
        f = open(sliceName + 'run.gcode', 'w')
        if config['lapse']:
            f.write('cameraMode\n')
        f.write('fan open\n')
        f.write('clean open\n')
        f.write('wait 3\n')
        f.write('fan close\n')
        f.write('clean close\n')
        f.write('z_enable\n')
        f.write('plate 150 %.2f %.2f %.2f\n' % (config['z_acc2'], config['z_dec2'], config['z_speed2']))
        f.write('glass -50 %.2f %.2f %.2f\n' % (config['z_acc2'], config['z_dec2'], config['z_speed2']))
        f.write('tank %d %d %d %d\n' % (ed_tank[0], config['r_acc'], config['r_dec'], config['r_speed']))
        f.write('plate %.2f %.2f %.2f %.2f\n' % (20.0, config['z_acc'], config['z_dec'], config['z_speed']))
        now_tank = ed_tank[0]

        def printLayer(tank, layer, f, config, now_tank):
            src_img_path = '%s%d.png' % (config['img_path_%d' % tank], layer)
            dst_img_path = '%d_%d.png' % (i, tank)
            # shutil.copyfile(src_img, dst_img)
            src_img = cv2.imread(src_img_path)
            top = (1080 - src_img.shape[0]) // 2
            bottom = (1081 - src_img.shape[0]) // 2
            left = (1920 - src_img.shape[1]) // 2
            right = (1921 - src_img.shape[1]) // 2
            dst_img = cv2.copyMakeBorder(src_img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))
            cv2.imwrite(sliceName + dst_img_path, dst_img)
            height = config['layer_height'] * float(layer)
            if now_tank != tank:
                f.write(
                    'plate %.2f %.2f %.2f %.2f\n' % (5.0 + height, config['z_acc'], config['z_dec'], config['z_speed']))
                f.write('plate %.2f %.2f %.2f %.2f\n' % (
                95.0 + height, config['z_acc2'], config['z_dec2'], config['z_speed2']))
                f.write('glass -50 %.2f %.2f %.2f\n' % (config['z_acc2'], config['z_dec2'], config['z_speed2']))
                f.write('wait %d\n' % (40 if layer < 50 else 5))
                # --------清洗---------
                f.write('tank %d\n' % config['clean_tank'])
                f.write('clean open\n')
                f.write('plate %.2f\n' % (33.0 + height * 0.5))  # 33
                f.write('wait %d\n' % 6)  # 6
                f.write('plate %.2f\n' % (43.0 + height * 0.5))
                f.write('plate %.2f\n' % (33.0 + height * 0.5))
                f.write('wait %d\n' % 6)
                f.write('plate %.2f\n' % (100.0 + height))
                f.write('clean close\n')  # 6
                f.write('wait %d\n' % (20 if layer < 50 else 5))
                # f.write('wait %d\n' % (20))
                f.write('tank %d\n' % config['fan_tank'])
                f.write('plate %.2f\n' % (60.0 + height))  # 60
                f.write('fan open\n')
                # f.write('wait %d\n' % (50 if layer < 50 else 20))
                f.write('wait %d\n' % (80))
                f.write('plate %.2f\n' % (100.0 + height))
                f.write('fan close\n')

                # --------延时---------
                if config['lapse']:
                    f.write('plate %.2f\n' % (150))
                    f.write('tank 0\n')
                    f.write('wait 1\n')
                    f.write('capture\n')
                    f.write('wait 1\n')
                # --------延时---------

                # --------清洗---------
                f.write('tank %d\n' % tank)
                f.write('glass 0 %.2f %.2f %.2f\n' % (config['z_acc'], config['z_dec'], config['z_speed']))
                f.write('plate %.2f\n' % (20.0 + height))
                f.write('plate %.2f %.2f %.2f %.2f\n' % (height, config['z_acc'], config['z_dec'], config['z_speed']))
                now_tank = tank
            else:
                f.write('glass %.2f\n' % 0)
                f.write('plate %.2f\n' % (height + config['back_distance']))
                f.write('plate %.2f\n' % height)

            f.write('proj %s %.2f %d\n' % (
                dst_img_path,
                config['bottom_exposure_time_%d' % now_tank] if layer <= config['bottom_layers'] else config[
                    'standard_exposure_time_%d' % now_tank],
                config['bottom_exposure_current_%d' % now_tank] if layer <= config['bottom_layers'] else config[
                    'standard_exposure_current_%d' % now_tank]))

        for i in range(1, n + 1):
            if a[i][ed_tank[i - 1]] > 0:
                printLayer(ed_tank[i - 1], i, f, config, now_tank)

            for j in range(m):
                if a[i][j] > 0 and j != ed_tank[i - 1] and j != ed_tank[i]:
                    printLayer(j, i,f,config,now_tank)

            if ed_tank[i] != ed_tank[i - 1]:
                printLayer(ed_tank[i], i,f,config,now_tank)

        f.write('plate %.2f\n' % (n * config['layer_height'] + 90))
        f.write('glass -50 %.2f %.2f %.2f\n' % (config['z_acc2'], config['z_dec2'], config['z_speed2']))
        f.close()
        self.sig.emit(change_times)

class MainWidget(QWidget):

    def __init__(self, parent=None):
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

        self.sliceThread = sliceThread()
        self.sliceThread.sig.connect(self.sliceThreadFinish)
        self.controlThread = controlThread()
        self.controlThread.sig.connect(self.controlThreadFinish)
        self.printThread = printThread()
        self.printThread.sig.connect(self.printThreadFinish)
        self.is_printing = False
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
        self.z_is_enable = False
        self.scene = QGraphicsScene()
        self.ui.graphicsView.setScene(self.scene)
        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)
        self.ui.cancelButton.setEnabled(False)
        self.ui.stopButton.setEnabled(False)
        self.ui.sliceButton.setEnabled(False)
        self.imageWindow = None

    def setButtonEnable(self, flag):
        self.ui.fallButton.setEnabled(flag)
        self.ui.riseButton.setEnabled(flag)
        self.ui.homeButton.setEnabled(flag)
        self.ui.zEnableButton.setEnabled(flag)
        self.ui.closeProjButton.setEnabled(flag)
        self.ui.fanButton.setEnabled(flag)
        self.ui.cleanButton.setEnabled(flag)
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
        global sliceName
        sliceName = self.open_dir("保存切片文件到文件夹", os.getcwd()) + '/'
        if sliceName != '/':
            self.ui.sliceButton.setEnabled(False)
            if not os.path.exists(sliceName):
                os.makedirs(sliceName)
            with open(sliceName + 'config.yaml', 'w') as f:
                f.write(str(self.ui.configEdit.toPlainText()))
            self.ui.configPath.setText(sliceName + 'config.yaml')
            self.ui.slicePath.setText(sliceName)
            self.sliceThread.start()

    def sliceThreadFinish(self, sig):
        self.ui.sliceButton.setEnabled(True)
        reply = QMessageBox.information(self, '切片完成', '切片完成，切换次数为%d次' % sig, QMessageBox.Yes,
                                        QMessageBox.Yes)

    def controlThreadFinish(self,sig):
        if sig =='finish':
            idle_mut.unlock()
            print('finish unlock')
            self.setButtonEnable(True)
        elif sig == 'closeWindow':
            self.imageWindow.close()
            self.imageWindow = None
            self.pixmapItem.setPixmap(QPixmap())
        else:
            pixmap = QPixmap(sig)
            global proj_screen_pos
            self.pixmapItem.setPixmap(pixmap)
            self.imageWindow = ImageWindow(proj_screen_pos)
            self.imageWindow.showImage(pixmap)
            self.imageWindow.showFullScreen()


    def startPrint(self):
        global sliceName
        sliceName = self.open_dir("打开切片文件夹", sliceName) + '/'
        if sliceName == '/' or not os.path.exists(sliceName + 'run.gcode'):
            return
        self.ui.slicePath.setText(sliceName)
        self.is_printing = True
        global cancelprint
        cancelprint = False
        self.ui.printButton.setEnabled(False)
        self.ui.stopButton.setEnabled(True)
        self.printThread.start()

    def printThreadFinish(self, sig):
        if sig == 'run':
            print('ct_start')
            self.controlThread.start()
        elif sig == 'finish':
            self.ui.printButton.setEnabled(True)
            self.ui.stopButton.setEnabled(False)
            self.ui.cancelButton.setEnabled(False)

    def stopPrint(self):
        if self.is_printing:
            stopprint_mut.lock()
            self.ui.cancelButton.setEnabled(True)
            self.is_printing = False
        else:
            self.ui.cancelButton.setEnabled(False)
            stopprint_mut.unlock()
            self.is_printing = True

    def cancel_print(self):
        cancelprint_mut.lock()
        global cancelprint
        cancelprint = True
        cancelprint_mut.unlock()
        stopprint_mut.unlock()

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
            pos = int((self.controlThread.mmdlp.rmortor.getPosition() - self.controlThread.mmdlp.rmortor.st_pos)/ -104857.0) + 1
            pos = min(pos,4)
            pos = max(pos,0)
        self.setButtonEnable(False)
        idle_mut.lock()
        global cmdBuffer
        if self.plate_glass_r_choose == 'r':
            cmdBuffer = "%s %d" % (self.plate_glass_r_choose, pos)
        else:
            cmdBuffer = "%s %.2f" % (self.plate_glass_r_choose, pos)
        self.controlThread.start()

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
            pos = int((self.controlThread.mmdlp.rmortor.getPosition() - self.controlThread.mmdlp.rmortor.st_pos)/ -104857.0) - 1
            pos = min(pos,4)
            pos = max(pos,0)
        self.setButtonEnable(False)
        idle_mut.lock()
        global cmdBuffer
        if self.plate_glass_r_choose == 'r':
            cmdBuffer = "%s %d" % (self.plate_glass_r_choose, pos)
        else:
            cmdBuffer = "%s %.2f" % (self.plate_glass_r_choose, pos)
        self.controlThread.start()

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
        idle_mut.lock()
        global cmdBuffer
        cmdBuffer = t
        self.controlThread.start()

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
        idle_mut.lock()
        global cmdBuffer
        cmdBuffer = t
        self.controlThread.start()

    def home(self):
        self.setButtonEnable(False)
        idle_mut.lock()
        global cmdBuffer
        cmdBuffer = 'home'
        self.controlThread.start()

    def refreshPos(self):
        self.ui.plateDisplay.setText("%.2f"%(self.getPlatePos()))
        self.ui.glassDisplay.setText("%.2f"%(self.getGlassPos()))

    def setZero(self):
        pass

    def cleanDebris(self):
        pass

    def zEnable(self):
        t=None
        if self.z_is_enable:
            self.z_is_enable = False
            self.ui.zEnableButton.setStyleSheet(self.buttonDefaultStyle)
            t = 'z_disable'
        else:
            self.z_is_enable = True
            self.ui.zEnableButton.setStyleSheet(self.buttonHighlightStyle)
            t = 'z_enable'
        self.setButtonEnable(False)
        idle_mut.lock()
        global cmdBuffer
        cmdBuffer = t
        self.controlThread.start()

    def closeProj(self):
        self.setButtonEnable(False)
        idle_mut.lock()
        global cmdBuffer
        cmdBuffer = 'projector_close'
        self.controlThread.start()


app = QApplication(sys.argv)
screens = app.screens()
proj_screen_pos = screens[1].geometry()
window = MainWidget()
window.show()
sys.exit(app.exec_())
