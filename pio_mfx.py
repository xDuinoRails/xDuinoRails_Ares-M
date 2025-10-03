import rp2
from machine import Pin
from rp2 import PIO
import time

@rp2.asm_pio( sideset_init = rp2.PIO.OUT_LOW     # Init Cutout-Pin low
            , set_init     = rp2.PIO.OUT_LOW     # Init DCC-Pin low
            , out_init     = rp2.PIO.OUT_LOW     # Data pin starts LOW
            , out_shiftdir = rp2.PIO.SHIFT_LEFT  # Shift the data right (no idea why)
            , pull_thresh  = 18                  # Send 9 trits (18 bits) messages
            , autopull     = True                # Automatic reload the data from FIFO to OSR
            , fifo_join    = rp2.PIO.JOIN_TX     # Use 8 word FIFO
            )
def mfx_bit():
    # Pulse Encoding (Binary):
    # - 100us per Bit
    # - "1": Change polarity twice
    # - "0": Change polarity once
    #
    label("bitloop")
    mov(y,invert(y))    .side(0)      # 10us - Prepare invert
    set(pins, y)        .side(0)      # 10us - Invert voltage if "1" is read
    out(x, 1)           .side(0)      # 10us - Read next bit from the OSR
    jmp(x, "do_one")    .side(0)      # 10us - IF   x == '1' THEN "do_one"

    label("do_zero")
    jmp("bitloop")      .side(0) [5]  # 60us - ELSE x == '0' THEN "do_zero"

    label("do_one")
    mov(y,invert(y))    .side(0) [1]  # 20us - Prepare Invert
    set(pins, y)        .side(0) [3]  # 40us - Invert voltage if "1" is read

def mfx_half_sync():
    #
    # Halbe Synchronisierung
    #
    out(x,4)            .side(0)      # 10us (1x) - Prepare loop (2x pro Sync)
    label("twice")
    mov(y,invert(y))    .side(0)      # 10us (1x) - Prepare invert
    set(pins, y)        .side(0) [7]  # 80us (8x) - Invert voltage if "1" is read
    mov(y,invert(y))    .side(0)      # 10us (1x) - Prepare invert
    set(pins, y)        .side(0) [3]  # 40us (4x) - Invert voltage if "1" is read
    mov(y,invert(y))    .side(0)      # 10us (1x) - Prepare invert
    set(pins, y)        .side(0) [8]  # 90us (9x) - Invert voltage if "1" is read
    jmp(x_dec,"twice")  .side(0)      # 10us (1x) - Repeat once

sm_loco = rp2.StateMachine(0, mfx_bit,       freq= 100_000, set_base=Pin(7), out_base=Pin(7), sideset_base=Pin(8))
sm_loco.active(1)
sm_acc  = rp2.StateMachine(1, mfx_half_sync, freq= 614_400, set_base=P7in(7), out_base=Pin(7), sideset_base=Pin(8))
sm_acc.active(1)

print("Start of mfx")

# 18 bits / 9 trits will be sent
sm_loco.put(0b111111111111111111, 14)
time.sleep(0.01)
sm_loco.put(0b001100000000101011, 14)

print("End of mfx")
