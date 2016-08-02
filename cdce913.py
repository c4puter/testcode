import serial
import math

class CDCE913(object):

    ADDR = 0xca
    XTAL = 20e6

    def __init__(self, xmega="/dev/ttyACM0"):
        self.s = serial.Serial(xmega, timeout=1)

    def read_until_prompt(self):
        """Read from the serial port until a prompt comes back, then return
        a list of all lines before it"""

        s = b""
        while True:
            c = self.s.read(1)
            s += c
            if s.endswith(b"\r\n% "):
                return s.decode('ascii').split("\r\n")[:-1]

    def send(self, msg):
        """Send a message, as a list of lines without line endings"""
        encoded = [(i + '\r').encode('ascii') for i in msg]
        for i in encoded:
            self.s.write(i)

    def issue(self, cmd):
        """Issue a command and return the response"""
        self.send([cmd])
        return self.read_until_prompt()[1:] # drop the echo

    def i2c_rd(self, offset, n=1, i2caddr=ADDR):
        # CDCE913 seems to have trouble with multibyte reads...
        b = []
        for i in range(n):
            cmd = "twic tx 0x%02x T 0x%02x R 1" % (i2caddr, 0x80 + offset)
            val = int(self.issue(cmd)[1], 16)
            b.append(val)
        return b

    def i2c_wr(self, offset, vals, i2caddr=ADDR):
        if isinstance(vals, int):
            vals = [vals]
        elif not isinstance(vals, list):
            raise TypeError("vals must be int or list")
        b = [offset, len(vals)] + vals
        cmd = ("twic tx 0x%02x T " % i2caddr) + " ".join("0x%02x" % i for i in b)
        print(cmd)
        self.issue(cmd)

    def enable(self):
        # Drive gate low on S0 pulldown
        self.issue("port c outclr 0x04")
        self.issue("port c dirset 0x04")
        # Power up CDCE913
        self.issue("port b outset 0xfa")
        self.issue("port b dirset 0xfa")
        # Power up I2C pullups
        self.issue("port c outset 0x80")
        self.issue("port c dirset 0x80")
        # Initialize I2C
        self.issue("twic en 100000") # 100kHz

    def disable(self):
        # Disable I2C
        self.issue("twic dis")
        # Power down pullups
        self.issue("port c dirclr 0x80")
        # Power down CDCE913
        self.issue("port b dirclr 0xfa")

    def y1div(self, divider):
        divider = int(divider)
        if divider < 0 or divider > 1023:
            raise ValueError("Divider must be from 0 to 1023 inclusive")

        reg02 = 0xb4 | ((divider & 0x300) >> 8)
        #reg02 = (self.i2c_rd(0x02)[0] & ~0x03) | ((divider & 0x300) >> 8)
        reg03 = divider & 0xff

        self.i2c_wr(0x02, [reg02, reg03])

    def loadcap(self, pf):
        pf = int(pf)
        if pf < 0 or pf > 20:
            raise ValueError("Acceptable load capacitance from 0pF to 20pF")
        reg05 = pf << 3
        self.i2c_wr(0x05, reg05)

    def usepll(self, v):
        reg14 = self.i2c_rd(0x14)[0]
        if v:
            reg14 &= ~0x80
        else:
            reg14 |= 0x80
        self.i2c_wr(0x14, reg14)

    def ratio(self, num, den, force=False):
        freq = self.XTAL * num / den

        if (freq < 80e6 or freq > 230e6) and not force:
            raise ValueError("Frequency must be from 80MHz to 230MHz, or use force=True")

        N = num
        M = den
        P = 4 - int(math.log2(N / M))
        Np = N * 2**P
        Q = int(Np / M)
        R = Np - M * Q

        if freq < 125e6:
            frange = 0
        elif freq < 150e6:
            frange = 1
        elif freq < 175e6:
            frange = 2
        else:
            frange = 3

        print("N = %d, P = %d, Q = %d, R = %d" % (N,P,Q,R))

        reg18 = (N & 0xff0) >> 4
        reg19 = ((N & 0x00f) << 4)  |  ((R & 0xf0) >> 4)
        reg1a = ((R &  0x0f) << 4)  |  ((Q & 0x38) >> 3)
        reg1b = ((Q &  0x07) << 5)  |  ((P & 0x03) << 2) | frange

        self.i2c_wr(0x18, reg18)
        self.i2c_wr(0x19, reg19)
        self.i2c_wr(0x1a, reg1a)
        self.i2c_wr(0x1b, reg1b)

c = CDCE913()
print("here, have 'c'")
print()
