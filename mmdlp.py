import Projector
import RMortor
import SensorFanClean
import ZMortor
import AMS
import time
import yaml

class MM_DLP:
    def __init__(self,glassHome, plateHome, lead, RMortor_st_pos, AMS_port):
        self.zmortor = ZMortor.ZMortor(glassHome,plateHome,lead)#-4.8,29.52,5.0
        self.rmortor = RMortor.RMortor(RMortor_st_pos)#1903534
        self.projector = Projector.Projector()
        # self.AMS = AMS.AMS(AMS_port)
        self.sensorFanClean = SensorFanClean.SensorFanClean()
        self.projector.LedOff()
        self.sensorFanClean.fanClose()
        self.sensorFanClean.cleanClose()
        self.projector.LedOff()
