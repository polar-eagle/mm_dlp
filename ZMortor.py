# 下面-1.9 上面29.5
import libs.Control as Control
import time


class ZMortor:
    def __init__(self, glassHome, plateHome, lead):
        self.glassHome = glassHome  # -3.65
        self.plateHome = plateHome  # 29.47
        self.lead = lead  # 5.0
        # 初始化Control对象时，创建一个ActuatorController对象，并赋值给self.controller
        self.controller = Control.Control()
        self.enableActuatorInBatch()
        if self.controller.ActuatorNums > 0:
            for i in range(0, self.controller.ActuatorNums):
                self.activateActuatorMode(i, Control.ActuatorMode.Mode_Profile_Pos)
            self.setProfilePositionVelocity(60, -60, 60, 0)
            self.setProfilePositionVelocity(60, -60, 60, 1)
        # self.disableAllActuators()

    def enableActuatorInBatch(self):
        # 调用ActuatorController的enableActuatorInBatch方法，批量启用执行器
        self.controller.enableActuatorInBatch()

    def enableSingleActuator(self, index):
        # 启用单个执行器，index为执行器的索引，默认为0
        self.controller.enableSingleActuator(index)

    def activateActuatorMode(self, index, mode=Control.ActuatorMode.Mode_Profile_Pos):
        # 激活执行器的工作模式，index为执行器的索引，默认为0
        # mode为执行器的工作模式，默认为Control.ActuatorMode.Mode_Profile_Pos
        self.controller.activateActuatorMode(index, mode)

    def getCurrent(self, index):
        # 获取执行器的电流值，index为执行器的索引，默认为0
        return self.controller.getCurrent(index)

    def getPosition(self, index):
        # 获取执行器的位置值，index为执行器的索引，默认为0
        return self.controller.getPosition(index)

    def disableAllActuators(self):
        # 禁用所有执行器
        self.controller.disable_all_actuators()

    def enableAllActuators(self):
        self.enableActuatorInBatch()
        if self.controller.ActuatorNums > 0:
            for i in range(0, self.controller.ActuatorNums):
                self.activateActuatorMode(i, Control.ActuatorMode.Mode_Profile_Pos)
            self.setProfilePositionVelocity(60, -60, 60, 0)
            self.setProfilePositionVelocity(60, -60, 60, 1)

    def positionControl(self, position, index):
        # 控制执行器的位置，position为目标位置，index为执行器的索引，默认为0
        self.controller.positionControl(position, index)

    def setProfilePositionVelocity(self, acceleration, deceleration, velocity, index):
        # 设置执行器的Profile位置模式的参数，加速度acceleration，减速度deceleration，目标速度velocity，index为执行器的索引，默认为0
        return self.controller.setProfilePositionVelocity(acceleration, deceleration, velocity, index)

    def move(self, targetPosition, index):
        self.positionControl(targetPosition, index)
        now_pos = self.getPosition(index)
        time.sleep(0.1)
        while abs(now_pos - targetPosition) > 0.0001:
            now_pos = self.getPosition(index)
            time.sleep(0.1)
        # st_t = time.time()
        # while abs(targetPosition - self.getPosition(index)) > 0.001:
        #     ed_t = time.time()
        #     if ed_t - st_t > 30:
        #         print(ed_t - st_t)
        #     if ed_t - st_t > 60:
        #         break

    def glassMove(self, targetPosition):
        self.move(targetPosition / self.lead + self.glassHome, 1)

    def getGlassPos(self):
        return (self.getPosition(1) - self.glassHome) * self.lead

    def setGlassSpeed(self, acc, dec, speed):
        self.setProfilePositionVelocity(acc, dec, speed, 1)

    def plateMove(self, targetPosition):
        self.move(self.plateHome - targetPosition / self.lead, 0)

    def getPlatePos(self):
        return (self.getPosition(0) - self.plateHome) * (-self.lead)

    def setPlateSpeed(self, acc, dec, speed):
        self.setProfilePositionVelocity(acc, dec, speed, 0)

# a=ZMortor(1,1,1)
# a.setPlateSpeed(90,-90,120)
# a.plateMove(130)
# a.setPlateSpeed(400,-1000,400)
# a.plateMove(60)
# a.disableAllActuators()
