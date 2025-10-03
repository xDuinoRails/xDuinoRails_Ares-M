import rp2
from machine import Pin
from rp2 import PIO
import time

@rp2.asm_pio( sideset_init = rp2.PIO.OUT_LOW     # Init Cutout-Pin low
            , out_init     = rp2.PIO.OUT_LOW     # Data pin starts LOW
            , out_shiftdir = rp2.PIO.SHIFT_LEFT  # Shift the data right (no idea why)
            , pull_thresh  = 12                  # Send 12 bit per messages
            , autopull     = True                # Automatic reload the data from FIFO to OSR
            , fifo_join    = rp2.PIO.JOIN_TX     # Use 8 word FIFO
            )
def sx_bit():
    #
    # Pulse Encoding (Binary)
    # =======================
    # - Data:  40us - Manchester: change polarity if input == '1'
    # - Clock: 10us - During each possible change
    #
    # H-Bridget Control
    # =================
    # - Out/Set-Pin: Direction
    # - Side-Pin:    Brake
    #

    # DATA SIGNAL (prepare)
    # ---------------------
    out(x, 1)           .side(0)      # 10us - Get next bit from FIFO via OSR
    jmp(x,"prepare_one").side(0)      # If X == 0 THEN flip data pin
    
    label("prepare_zero")
    jmp("bitloop")      .side(0)      # 10us - Keep voltage if "0" is read

    label("prepare_one")
    mov(y,invert(y))    .side(0)      # 10us - Invert Voltage if "1" is read

    # CLOCK SIGNAL
    # ------------
    label("bitloop")
    nop()               .side(1)      # 10us - Set Brake pulse

    # DATA SIGNAL (publish)
    # -------------------
    mov(pins, y)        .side(0)      # 10us - Read next bit from the OSR to X



sm_sx = rp2.StateMachine(1, sx_bit, freq= 100_000, set_base=Pin(7), out_base=Pin(7), sideset_base=Pin(8))
sm_sx.active(1)

print("Start of SX")

# 12 bits will be sent "000" = sync block
sm_sx.put(0x0001_1010_0101 << 20)

print("End of SX")
