import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QVBoxLayout, QLabel
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QPointF

class DraggableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super(DraggableGraphicsView, self).__init__(parent)
        self.zoomLevel = 0
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoomLevel += 1
        else:
            self.zoomLevel -= 1

        factor = 1.25 ** self.zoomLevel
        self.resetTransform()
        self.scale(factor, factor)

class MainWidget(QWidget):
    def __init__(self, screens):
        super().__init__()
        self.screens = screens
        self.imageWindow = None
        self.initUI()

    def initUI(self):
        self.setGeometry(self.screens[1].geometry())
        self.setWindowTitle('双屏软件')

        # 创建按钮
        self.buttonShow = QPushButton('显示图片', self)
        self.buttonClose = QPushButton('关闭图片', self)

        # 创建 DraggableGraphicsView 和 QGraphicsScene
        self.view = DraggableGraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)
        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)

        # 创建布局并添加控件
        layout = QVBoxLayout()
        layout.addWidget(self.buttonShow)
        layout.addWidget(self.buttonClose)
        layout.addWidget(self.view)
        self.setLayout(layout)

        # 连接按钮事件
        self.buttonShow.clicked.connect(self.showImage)
        self.buttonClose.clicked.connect(self.closeImage)

    def showImage(self):
        # 加载图片
        pixmap = QPixmap('C:/Users/Nuc/Desktop/mmdlp_gui/test1/1_0.png')  # 指定图片路径
        self.pixmapItem.setPixmap(pixmap)

        # 在第二屏显示图片
        if self.imageWindow is None:
            self.imageWindow = ImageWindow(self.screens[0].geometry())
        self.imageWindow.showImage(pixmap)
        self.imageWindow.showFullScreen()
        print(1111)

    def closeImage(self):
        if self.imageWindow is not None:
            self.imageWindow.close()
            self.imageWindow = None
        self.pixmapItem.setPixmap(QPixmap())  # 清空或显示全黑画面

class ImageWindow(QWidget):
    def __init__(self, screen_geometry):
        super().__init__()
        self.setGeometry(screen_geometry)
        self.initUI()

    def initUI(self):
        self.label = QLabel(self)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

    def showImage(self, pixmap):
        self.label.setPixmap(pixmap)
        self.label.setAlignment(Qt.AlignCenter)

def main():
    app = QApplication(sys.argv)
    screens = app.screens()
    mainWidget = MainWidget(screens)
    mainWidget.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
