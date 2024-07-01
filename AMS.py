import serial
import time
class AMS:
    def __init__(self, port):
        self.ard=serial.Serial(port,9600,timeout=1)
        # self.ard = 0

    def feed(self, mortor, rounds):
        self.ard.write(chr(60*mortor+rounds).encode('ascii'))
        while self.ard.in_waiting<=0:
            pass
        data=self.ard.readline().decode('utf-8').rstrip()

    def backflow(self):
        self.ard.write(chr(120).encode('ascii'))
        while self.ard.in_waiting<=0:
            pass
        data=self.ard.readline().decode('utf-8').rstrip()


# a=AMS('COM4')
# time.sleep(2)
# a.backflow()
