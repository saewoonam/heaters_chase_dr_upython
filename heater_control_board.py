from sys import stdin, stdout, exit
import select
import gc
import ujson
import machine
from high_power_heater_v2 import High_power_heater_board
from bh2221 import BH2221

heaters = [
    High_power_heater_board(29, 28, machine_number=0, addr=65), 
    High_power_heater_board(27, 26, machine_number=1, addr=64), 
    ]
# heaters = [heater]
lph = BH2221(out=20, clk_ld=5)

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
    global heaters, lph
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
            writeUSB('heater_control_board')
        elif (cmd=='NAME?'):
            if len(params)>0:
                channel = int(params[0])
                writeUSB(heaters[channel].name)
            else:
                writeUSB('bad command')
        elif (cmd=='PING'):
            writeUSB('PONG')
        elif (cmd=="I?"):
            if len(params)>0:
                channel = int(params[0])
                if channel < len(heaters):
                    writeUSB(heaters[channel].dac)
                else:
                    writeUSB('bad command')
            else:
                writeUSB('bad command')
        elif (cmd=='MON?'):
            if len(params)>0:
                channel = int(params[0])
                if channel < len(heaters):
                    writeUSB([heaters[channel].v, heaters[channel].i])
                else:
                    writeUSB('bad command')
            else:
                writeUSB('bad command')
        elif (cmd=="EN?"):
            if len(params)>0:
                channel = int(params[0])
                if channel < len(heaters):
                    if heaters[channel].enabled:
                        writeUSB(1)
                    else:
                        writeUSB(0)
                else:
                    writeUSB('bad command')
            else:
                writeUSB('bad command')
        elif (cmd=="I"):
            if len(params)>1:
                channel = int(params[0])
                dac_value = int(params[1])
                heaters[channel].dac = dac_value
                #set(int(params[0]))
                #print(ujson.dumps('done'))
                writeUSB('done')
            else:
                writeUSB('bad command')
        elif (cmd=="EN"):
            if len(params)>1:
                channel = int(params[0])
                value = int(params[1])
                if value==0:
                    heaters[channel].disable()
                else:
                    heaters[channel].enable()
                writeUSB('done')
            else:
                writeUSB('bad command')
        elif (cmd=="LPH?"):
            if len(params)>0:
                channel = int(params[0])
                writeUSB(lph.get_channel(channel))
            else:
                writeUSB('bad command')
        elif (cmd=="LPH"):
            if len(params)>1:
                channel = int(params[0])
                if (channel>0) and (channel<5):
                    dac_value = int(params[1])
                    lph.set_channel(channel, dac_value)
                    writeUSB('done')
                else:
                    writeUSB('bad command')
            else:
                writeUSB('bad command')
        elif (cmd=="NAME"):
            if len(params)>1:
                channel = int(params[0])
                heaters[channel].name = params[1]
                #set(int(params[0]))
                print(ujson.dumps('done'))
            else:
                writeUSB('bad command')
        elif (cmd=='RESET'):
            if len(params)>0:
                channel = int(params[0])
                heaters[channel].reset()
                print(ujson.dumps('done'))
            else:
                writeUSB('bad command')
        else:
            writeUSB('not understood')

while True:
    readUSB()