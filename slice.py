import sys
import interface_slice as interface
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal

QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
import os
import yaml
import cv2
import numpy as np
import traceback


class sliceThread(QThread):
    sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.sliceName = None
        self.config = None
        self.now_tank = 0

    def run(self):
        try:
            change_times = self.work()
        except Exception:
            exc_info = traceback.format_exc()
            change_times = exc_info
        self.sig.emit(change_times)

    def work(self):
        # for i in os.listdir(self.sliceName):
        #     if i[-4:] != 'yaml':
        #         os.remove(self.sliceName + i)
        with open(self.sliceName + 'config.yaml') as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)
        # -------------------- dp算路径 -----------------------
        layers = []
        for i in range(self.config['material_num']):
            layers.append(0)
            if self.config['img_path_' + str(i)][-1] != '/':
                self.config['img_path_' + str(i)] += '/'
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
        f.write('r_enable\n')
        f.write('plate %.2f %.2f %.2f %.2f\n' % (
        self.config['max_height'], self.config['z_acc_h'], self.config['z_dec_h'], self.config['z_speed_h']))
        f.write('glass %.2f %.2f %.2f %.2f\n' % (
        self.config['min_height'], self.config['z_acc_h'], self.config['z_dec_h'], self.config['z_speed_h']))
        f.write('tank %.2f %.2f %.2f %.2f\n' % (
        ed_tank[0], self.config['r_acc'], self.config['r_dec'], self.config['r_speed']))
        f.write('plate %.2f %.2f %.2f %.2f\n' % (
        self.config['pre_z_height'], self.config['z_acc_h'], self.config['z_dec_h'], self.config['z_speed_h']))
        self.now_tank = ed_tank[0]
        self.change_cnt = 0
        for i in range(1, n + 1):
            if a[i][ed_tank[i - 1]] > 0:
                self.printLayer(ed_tank[i - 1], i, f)

            for j in range(m):
                if a[i][j] > 0 and j != ed_tank[i - 1] and j != ed_tank[i]:
                    self.printLayer(j, i, f)

            if ed_tank[i] != ed_tank[i - 1]:
                self.printLayer(ed_tank[i], i, f)

        f.write('plate %.2f %.2f %.2f %.2f\n' % (
        self.config['max_height'], self.config['z_acc_h'], self.config['z_dec_h'], self.config['z_speed_h']))
        f.write('glass %.2f %.2f %.2f %.2f\n' % (
        self.config['min_height'], self.config['z_acc_h'], self.config['z_dec_h'], self.config['z_speed_h']))
        f.write('tank %d\n' % self.config['clean_tank'])
        f.write('clean open\n')
        f.write('plate %.2f\n' % (self.config['clean_height'] + self.config['layer_height'] * float(n) * self.config['clean_height_coefficient']))
        if self.config['AMS']:
            f.write('AMS backflow\n')
        f.close()
        return str(change_times)

    def printLayer(self, tank, layer, f):
        # print(tank, layer)
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
            self.config['pre_z_height'] + height, self.config['z_acc_l'], self.config['z_dec_l'], self.config['z_speed_l']))
            f.write('plate %.2f %.2f %.2f %.2f\n' % (
            self.config['max_height'], self.config['z_acc_h'], self.config['z_dec_h'], self.config['z_speed_h']))
            f.write('glass %.2f %.2f %.2f %.2f\n' % (
            self.config['min_height'], self.config['z_acc_h'], self.config['z_dec_h'], self.config['z_speed_h']))
            f.write('wait %.2f\n' % (
            self.config['drop_time_bottom'] if layer < self.config['drop_layers_bottom'] else self.config['drop_time_standard']))

            if self.config['ASS'] and self.change_cnt > self.config['ASS_times']:
                f.write('ASS output %d\n' % ((self.config['clean_height'] - self.config['clean_tank_height']) * self.config[
                    'ASS_volume_per_h'] + 10))
                f.write('ASS input %d\n'%((self.config['clean_height']-self.config['clean_tank_height'])*self.config['ASS_volume_per_h']))
            # --------清洗---------
            f.write('tank %d\n' % self.config['clean_tank'])
            f.write('clean open\n')

            for i in range(self.config['clean_times']):
                f.write('plate %.2f\n' % (
                self.config['clean_height'] + height * self.config['clean_height_coefficient']))
                f.write('wait %.2f\n' % (self.config['clean_time']))
                f.write('plate %.2f\n' % (
                self.config['clean_height'] + height * self.config['clean_height_coefficient'] + self.config['clean_distance']))

            f.write('plate %.2f\n' % (self.config['max_height']))
            f.write('clean close\n')
            f.write('wait %.2f\n' % (
            self.config['drop_time_bottom'] if layer < self.config['drop_layers_bottom'] else self.config['drop_time_standard']))
            # --------清洗---------

            self.change_cnt += 1

            # --------风干---------
            f.write('tank %d\n' % self.config['dry_tank'])
            f.write('plate %.2f\n' % (self.config['dry_height'] + height))
            f.write('fan open\n')
            f.write('wait %.2f\n' % (
            self.config['dry_time_bottom'] if layer < self.config['drop_layers_bottom'] else self.config['dry_time_standard']))
            f.write('plate %.2f\n' % (self.config['max_height']))
            f.write('fan close\n')
            # --------风干---------

            # --------加料---------
            if self.config['AMS'] and layer < self.config['AMS_layers']:
                f.write('tank %d\n' % (self.now_tank + self.config['AMS_tank_offset']))
                f.write('AMS %d %d\n' % (self.now_tank, self.config['AMS_volume']))
            # --------加料---------

            # --------延时---------
            if self.config['lapse']:
                f.write('plate %.2f\n' % (self.config['lapse_height']))
                f.write('tank %d\n' % (self.config['lapse_tank']))
                f.write('wait 2\n')
                f.write('capture\n')
                f.write('wait 2\n')
            # --------延时---------

            f.write('tank %d\n' % tank)
            f.write('glass -5.00 %.2f %.2f %.2f\n' % (
            self.config['z_acc_h'], self.config['z_dec_h'], self.config['z_speed_h']))
            f.write('glass 0.00 %.2f %.2f %.2f\n' % (
            self.config['z_acc_l'], self.config['z_dec_l'], self.config['z_speed_l']))
            f.write('plate %.2f\n' % (self.config['pre_z_height'] + height))
            f.write('plate %.2f %.2f %.2f %.2f\n' % (
                height, self.config['z_acc_l'], self.config['z_dec_l'], self.config['z_speed_l']))
            self.now_tank = tank
        else:
            f.write('glass 0.00\n')
            f.write('plate %.2f\n' % (height + self.config['back_distance']))
            f.write('plate %.2f\n' % height)

        f.write('proj %s %.2f %d\n' % (
            dst_img_path,
            self.config['bottom_exposure_time_%d' % self.now_tank] if layer <= self.config['bottom_layers'] else
            self.config['standard_exposure_time_%d' % self.now_tank],
            self.config['bottom_exposure_current_%d' % self.now_tank] if layer <= self.config['bottom_layers'] else
            self.config['standard_exposure_current_%d' % self.now_tank]))

    def set_sliceName(self, sliceName):
        self.sliceName = sliceName


class MainWidget(QWidget):

    def __init__(self, parent=None):
        super(QWidget, self).__init__(parent)
        self.ui = interface.Ui_Form()
        self.ui.setupUi(self)
        self.ui.configEdit.textChanged.connect(self.config_changed)
        self.ui.openConfigButton.clicked.connect(self.open_config)
        self.ui.saveConfigButton.clicked.connect(self.save_config)
        self.ui.sliceButton.clicked.connect(self.slice)

        self.ui.sliceButton.setEnabled(False)
        self.sliceName = os.getcwd()

        self.sliceThread = sliceThread()
        self.sliceThread.sig.connect(self.sliceThreadFinish)

    def open_file(self, dialogName, currentPath, supportType):
        fileName, fileType = QtWidgets.QFileDialog.getOpenFileName(self, dialogName, currentPath, supportType)
        return fileName

    def open_dir(self, dialogName, currentPath):
        dirName = QtWidgets.QFileDialog.getExistingDirectory(self, dialogName, currentPath)
        return dirName

    def save_file(self, dialogName, currentPath, supportType):
        fileName, fileType = QtWidgets.QFileDialog.getSaveFileName(self, dialogName, currentPath, supportType)
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
            self.sliceThread.set_sliceName(self.sliceName)
            self.sliceThread.start()

    def sliceThreadFinish(self, sig):
        self.ui.sliceButton.setEnabled(True)
        if sig.isdigit():
            QMessageBox.information(self, '切片完成', '切片完成，切换次数为%s次' % sig, QMessageBox.Yes,
                                    QMessageBox.Yes)
        else:
            QMessageBox.critical(self, 'error', sig, QMessageBox.Yes,
                                 QMessageBox.Yes)


app = QApplication(sys.argv)
window = MainWidget()
window.show()
sys.exit(app.exec_())
