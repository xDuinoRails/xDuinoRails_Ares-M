import rp2
from machine import Pin
from rp2 import PIO
import time

@rp2.asm_pio( set_init     = rp2.PIO.OUT_LOW
            , out_shiftdir = rp2.PIO.SHIFT_RIGHT # Shift the data right (no idea why)
            , pull_thresh  = 9                   # Send 9 bits messages
            , autopull     = True                # Automatic reload the data from FIFO to OSR
            )
def dcc_bit():
    label("do_high")
    # First half (HIGH):
    # ... FOR bit == '1/0' THEN stay 29 clocks (58us) 'HIGH' in any case
    out(x, 1)                              # L: +2us  (1x) - Read next bit from the OSR to X
    set(pins, 1)                     [14]  # H:+30us (15x) - Set Pin to '1' (HIGH)
    jmp(not_x, "do_low_0")           [13]  # H:+28us (14x) - IF bit == '0' THEN jump
    jmp(not_x, "do_low_0")           [13]  # H:+28us (14x) - IF bit == '0' THEN jump

    # --- START - bit == '0' only ---
    label("do_low_0")
    nop()                            [20]  # H:+42us (21x) - Maintain '1' (HIGH) longer  = 100us
    set(pins, 0)                     [20]  # L:+42us (21x) - Set Pin to '0' (LOW) longer = 100us
    # --- END   - bit == '0' only ---

    # ... FOR bit == '1/0' THEN add another 29 clocks (58us) 'LOW' in any case
    label("do_low_1")
    set(pins, 0)                     [13]  # L:+28us (14x) - Set Pin to '0' (LOW)
    jmp("do_high")                   [13]  # L:+28us (14x) - The same over & over again

sm_bit   = rp2.StateMachine(1, dcc_bit, freq= 500_000, set_base=Pin(7) )
sm_bit.active(1)

print("Start of DCC")

# Send the preamble (17x '1', 1x '0')
sm_bit.put(0b000000000)
sm_bit.put(0b100000000)

print("End of Preamble")
time.sleep(0.01)

sm_bit.put(0b110000010)
sm_bit.put(0b111000010)
sm_bit.put(0b111100010)
time.sleep(0.01)

print("End of DCC")

