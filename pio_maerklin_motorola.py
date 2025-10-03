import rp2
from machine import Pin
from rp2 import PIO
import time

@rp2.asm_pio( set_init     = rp2.PIO.OUT_LOW     # Init DCC-Pin low
            , out_init     = rp2.PIO.OUT_LOW     # Data pin starts LOW
            , out_shiftdir = rp2.PIO.SHIFT_LEFT  # Shift the data right (no idea why)
            , pull_thresh  = 18                  # Send 9 trits (18 bits) messages
            , autopull     = True                # Automatic reload the data from FIFO to OSR
            , fifo_join    = rp2.PIO.JOIN_TX     # Use 8 word FIFO
            )
def mm_bit():
    # First half (HIGH)
    # =================
    #
    # Pulse Encoding (Binary):
    # - A binary "1": Seven time units positive, one time unit negative.
    # - A binary "0": One time units positive, seven time unit negative.
    #
    # 614kHz = 38'400 with 2*8clock per bit
    #
    set(pins, 1)                # H:  (1x) - Set Pin to '1' (HIGH)
    out(pins, 1)          [5]   # X:  (6x) - Read next bit from the OSR
    set(pins, 0)                # L:  (1x) - Set Pin to '0' (LOW)

sm_loco = rp2.StateMachine(0, mm_bit, freq= 307_200, set_base=Pin(7), out_base=Pin(7))
sm_loco.active(1)
sm_acc  = rp2.StateMachine(1, mm_bit, freq= 614_400, set_base=Pin(7), out_base=Pin(7))
sm_acc.active(1)

print("Start of MM")

# 18 bits / 9 trits will be sent
sm_loco.put(0b111111111111111111, 14)
time.sleep(0.01)
sm_loco.put(0b001100000000101011, 14)

print("End of MM")

