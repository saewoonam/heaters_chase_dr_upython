from machine import Pin, I2C
from rp2 import PIO, StateMachine, asm_pio
from sys import stdin, stdout, exit
import select
import gc
import ujson
import machine

class High_power_heater_board:
    def __init__(self, out_pin, enable_pin, machine_number=0, i2c=None, addr=64, ina219=True):
        """
            class High_power_heater
            out_pin is the pin number to configure the heater
            enable_pin is the pine number to enable the heater
        """
        FREQ = 10_000
        self.sm = StateMachine(
            machine_number, self.easy_scale_tx, freq=3 * FREQ,
            #sideset_base=Pin(out_pin+1),
            out_base=Pin(out_pin)
        )
        self.machine_number = machine_number
        self._i = 0
        self.sm.active(1)
        self.enable_pin = enable_pin
        self.set(0)
        #self.set(11)
        self.i2c = i2c
        if self.i2c==None:
            #pico
            #self.i2c = I2C(0, scl=machine.Pin(17), sda=machine.Pin(16))
            # qtpy
            self.i2c = I2C(1, scl=machine.Pin(23), sda=machine.Pin(22))
        self.INA219 = ina219
        self.name = "heater"
        self.addr = addr
        self.enabled = True
        self.reset()
        
    @property
    def dac(self):
        return self._i
    @dac.setter
    def dac(self, new_i):
        self._i = new_i
        self.set(self._i, number_zeros=1)
        
    def expand(self, data, out, num_bits=8):
        for count in range(num_bits):
            out <<= 3
            if (data & (1<<(num_bits-1-count))):
                out |= 0b011
            else:
                out |= 0b001
            #print(bin(out))
        return out

    @asm_pio(sideset_init=PIO.OUT_LOW, out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_LEFT)
    def easy_scale_tx_debug():
        # sideset pin is for debugging timing.  It is high before the first bit.
        # shift out 32bits at a time with each pull
        pull()       .side(0)
        # Initialise bit counter, sideset to mark the beginning
        set(x, 30)   .side(1)  # set counter to shift out 31 bits       
        # Shift out 31 data bits, 3 execution cycles per bit
        label("bitloop")
        out(pins, 1) .side(0) 
        nop()
        jmp(x_dec, "bitloop")
        out(pins, 1)  # shift out last bit... next two clock cycles are at the top of the loop

    @asm_pio(out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_LEFT)
    def easy_scale_tx():
        # sideset pin is for debugging timing.  It is high before the first bit.
        # shift out 32bits at a time with each pull
        pull()       #.side(0)
        # Initialise bit counter, sideset to mark the beginning
        set(x, 30)   #.side(1)  # set counter to shift out 31 bits       
        # Shift out 31 data bits, 3 execution cycles per bit
        label("bitloop")
        out(pins, 1) #.side(0) 
        nop()
        jmp(x_dec, "bitloop")
        out(pins, 1)  # shift out last bit... next two clock cycles are at the top of the loop


    def set(self, setting, number_zeros=3, send_easystart=True):
        for i in range(number_zeros):
            self.sm.put(0)
        if send_easystart:
            self.sm.put(0xC7<<24 | 0x00FFFFFF)  # turn on easy mode
        self.sm.put( (self.expand(0x72, 0)<<8 )+ 0b00111111)  # send address then eos
        self.sm.put( (self.expand(setting & 0b00011111, 0)<<8 )+ 0b00111111)  # send data then eos

    def disable(self):
        p2 = Pin(self.enable_pin, Pin.OUT)
        p2.on()
        self.enabled = False
        
    def enable(self):
        p2 = Pin(self.enable_pin, Pin.OUT)
        p2.off()
        self.enabled = True
        
    def reset(self):
        p2 = Pin(self.enable_pin, Pin.OUT)
        p2.on()
        self.dac = 0
        self.dac = 1
        self.dac = 0
        '''
        self.set(0)
        self.set(1)
        self.set(0)
        '''
        p2.off()
        self.enabled = True

    # INA226
    def read_i_ina226(self):
        i2c = self.i2c
        i2c.writeto(self.addr, bytes([1]))
        raw = i2c.readfrom(self.addr, 2)
        return int.from_bytes(raw, 'big', True) * 2.5e-6

    def read_v_ina226(self):
        i2c = self.i2c
        i2c.writeto(self.addr, bytes([2]))
        raw = i2c.readfrom(self.addr, 2)
        return int.from_bytes(raw, 'big', True) * 1.25e-3

    #INA219
    def readReg(self, reg, signed=False):
        i2c = self.i2c
        addr=self.addr
        res = i2c.writeto(addr, bytes([reg]));
        result = bytearray(2)
        i2c.readfrom_into(addr, result)
        result = int.from_bytes(bytes(result), "big")
        if signed:
            if result & 0x8000:
                result = result - (1 << 16)
        return result

    def read_i_ina219(self):
        return self.readReg(1, True) / 100

    def read_v_ina219(self):
        #return (readReg(2)>>3) / 8000 * 32
        return (self.readReg(2)) / 2000 

    @property
    def i(self):
        if self.INA219:
            return self.read_i_ina219()
        else:
            return self.read_i_ina226()
    @property
    def v(self):
        if self.INA219:
            return self.read_v_ina219()
        else:
            return self.read_v_ina226()

def readUSB():
    global ONCE, CONTINUOUS, last
    gc.collect()
    while stdin in select.select([stdin], [], [], 0)[0]:
        #print('Got USB serial message')
        gc.collect()
        cmd = stdin.readline()
        #print(type(cmd), repr(cmd))
        cmd = cmd.strip().upper()
        if len(cmd)>0:
            do_command(cmd)

def writeUSB(msg):
    print(ujson.dumps(msg))
    
def do_command(cmd):
    global heater
    # print('cmd', cmd)
    cmd = cmd.split()
    # print('cmd', cmd)
    if len(cmd)>1:
        params = cmd[1:]
    else:
        params = []
    cmd = cmd[0]
    if len(cmd):  # respond to command
        if (cmd=='Q'):
            writeUSB('Got Q')
            exit(0)
        elif (cmd=='*IDN?'):
            writeUSB('high power heater')
        elif (cmd=='NAME?'):
            writeUSB(heater.name)
        elif (cmd=='PING'):
            writeUSB('PONG')
        elif (cmd=="I?"):
            writeUSB(heater.dac)
        elif (cmd=='MON?'):
            writeUSB([heater.v, heater.i])
        elif (cmd=="I"):
            if len(params)>0:
                heater.dac = int(params[0])
                #set(int(params[0]))
                print(ujson.dumps('done'))
            else:
                writeUSB('bad command')
        elif (cmd=="NAME"):
            if len(params)>0:
                heater.name = params[0]
                #set(int(params[0]))
                print(ujson.dumps('done'))
            else:
                writeUSB('bad command')
        elif (cmd=='RESET'):
            #print('before')
            heater.reset()
            print(ujson.dumps('done'))
        else:
            writeUSB('not understood')

#heater = High_power_heater_board(0, 1, addr=64);
#heater = High_power_heater_board(29, 28, addr=65);

# example code
#
# heater.dac = 5  # set dac to 5
# heater.i # fetch current measured by i2c chip
# heater.v # fetch voltage measured by the i2c chip
# heater.dac # fetch what was last sent to the TPS61165 via ez scale
# heater.reset()  # reset the ez scale protocol to set the current

#while True:
#    readUSB()