from machine import Pin
from rp2 import PIO, StateMachine, asm_pio
from sys import stdin, stdout, exit
import select

class BH2221:
    def __init__(self, out=26, clk_ld=27):
        FREQ = 200_000
        PIN_BASE=0
        self.sm = StateMachine(
                5, self.bh2221_pio, freq= FREQ, sideset_base=Pin(clk_ld), out_base=Pin(out)
            )
        #sm.put(0x17F<<20)
        self.sm.active(1)
        #sm.put(0x17F<<20)
        #sm.put(0x27F<<20)
        self._i = [0]*6

    @asm_pio(sideset_init=(PIO.OUT_HIGH, PIO.OUT_LOW), out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_LEFT)
    def bh2221_pio():
        # sideset pins are for clock and load
        # first sideset bit is clock
        # second sideset bit is load
        pull()       .side(1)
        # Initialise bit counter, sideset to mark the beginning
        set(x, 11)   .side(1)  # set counter to shift out 12 bits       
        # Shift out 12 data bits, 4 execution cycles per bit
        label("bitloop")
        out(pins, 1) .side(0)
        nop()        .side(0)
        nop()        .side(1)
        jmp(x_dec, "bitloop")
        #nop()        .side(0)
        nop()        .side(3)  # set =load high
        nop()        .side(2) # clk low, set high
        nop()        .side(0) # both low

    def set_channel(self, channel, digital):
        '''
            BH2221 receives 12 bits of data.
                upper 4 bits are the channel number: little endian
                next 8 bits are the DAC value: bit endian
        '''
        value = 0
        # convert channel into little endian
        for i in range(4):
            value +=  ( 1<<(3-i) ) if (channel & (1<<i)) else 0
        # shift channel into upper 4 bits
        value <<= 8
        # add dac settting to value
        value += digital
        # set dac with state machine
        self.sm.put(value<<20)
        self._i[channel-1] = digital
    
    def get_channel(self, channel):
        if (channel<1) or (channel>4):
            return -1
        else:
            return self._i[channel-1]
    
'''
for channel in range(1, 13):
    set_channel(channel, channel*0x20)

settings = 7*[0]
def readUSB():
    global settings
    #gc.collect()
    while stdin in select.select([stdin], [], [], 0)[0]:
        #print('Got USB serial message')
        #gc.collect()
        cmd = stdin.readline()
        #print(type(cmd), repr(cmd))
        cmd = cmd.strip().upper()
        parse_cmd(cmd)
        
def parse_cmd(cmd):
    if len(cmd):
            cmd = cmd.split(' ');
            print(cmd)
            if len(cmd):  # respond to command
                if (cmd[0]=='Q'):
                    print('Got Q')
                elif (cmd[0]=='PING'):
                    print('PONG')
                elif (cmd[0]=='SET'):
                    print('set', cmd[1], cmd[2])
                    dac_value = int(float(cmd[2])/3.3*255)
                    print('dac_value', dac_value)
                    # need to add argument checking 
                    set_channel(int(cmd[1]), dac_value)
                    settings[int(cmd[1])] = cmd[2]
                    print('set done', settings)
                elif (cmd[0]=='GET'):
                    print('get', cmd[1])
                    idx = int(cmd[1])
                    print(settings[idx])
                    print('get done')
                    
#while True:
#    readUSB()
'''