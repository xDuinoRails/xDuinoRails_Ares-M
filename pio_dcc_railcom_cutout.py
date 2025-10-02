import rp2
from machine import Pin
from rp2 import PIO
import time

@rp2.asm_pio( set_init     = rp2.PIO.OUT_LOW     # Init DCC-Pin low
            , sideset_init = rp2.PIO.OUT_LOW     # Init Cutout-Pin low
            , out_shiftdir = rp2.PIO.SHIFT_LEFT # Shift the data right (no idea why)
            , pull_thresh  = 9                   # Send 9 bits messages
            , autopull     = True                # Automatic reload the data from FIFO to OSR
            , fifo_join    = rp2.PIO.JOIN_TX     # Use 8 word FIFO
            )
def dcc_bit():

    out(y, 9)                .side(0)        # L: +2us  (1x) - Load package size to Y

    # First half (HIGH):
    # ... FOR bit == '1/0' THEN stay 29 clocks (58us) 'HIGH' in any case
    label("do_high")
    out(x, 1)                .side(0)        # L: +2us  (1x) - Read next bit from the OSR to X
    set(pins, 1)             .side(0)  [13]  # H:+28us (14x) - Set Pin to '1' (HIGH)
    jmp(not_x, "do_low_0")   .side(0)  [13]  # H:+28us (14x) - IF bit == '0' THEN jump
    jmp("do_low_1")          .side(0)        # H: +2s   (1x) - IF bit == '1' THEN jump

    # --- START - bit == '0' only ---
    label("do_low_0")
    nop()                    .side(0)  [15]  # H:+32us (16x) - Maintain '1' (HIGH) 
    nop()                    .side(0)   [4]  # H:+10us  (5x) - Maintain '1' (HIGH) total = 100us
    set(pins, 0)             .side(0)  [15]  # L:+32us (16x) - Set Pin to '0' (LOW) longer = 100us
    nop()                    .side(0)   [4]  # L:+10us  (5x) - Maintain '1' (LOW) longer  = 100us
    # --- END   - bit == '0' only ---

    # ... FOR bit == '1/0' THEN add another 29 clocks (58us) 'LOW' in any case
    label("do_low_1")
    set(pins, 0)             .side(0)  [13]  # L:+28us (14x) - Set Pin to '0' (LOW)
    jmp(y_dec, "do_high")    .side(0)  [13]  # L:+28us (14x) - The same over & over again

    #
    # Generate the Railcom-Cutout
    # - OPTIONAL: Block RX port by setting pindir to "output" outside the cutout window.
    #
    set(pins, 1)             .side(0)  [13]  # L:+28us    (14x) - Set Pin to '1' (HIGH)
    set(y, 24)               .side(1)        # C: +2us     (1x) - Enable  the Cutout
    label("loop_450us")
    jmp(y_dec, "loop_450us") .side(1)   [8]  # C:450us  (9*25x) - Keep    the Cutout
    set(pins, 0)             .side(0)  [13]  # L:+28us    (14x) - Set Pin to '1' (HIGH)
    

sm_bit   = rp2.StateMachine(1, dcc_bit, freq= 500_000, set_base=Pin(7), sideset_base=Pin(8))
sm_bit.active(1)

print("Start of DCC")

# time.sleep(10)

# N + 1 bits will be sent
sm_bit.put(5*9-1, 23)
sm_bit.put(0b111111111, 23)
sm_bit.put(0b111111110, 23)
sm_bit.put(0b001101110, 23)
sm_bit.put(0b011001110, 23)
sm_bit.put(0b010100001, 23)

# Expact cutout
time.sleep(0.01)

print("End of DCC")
