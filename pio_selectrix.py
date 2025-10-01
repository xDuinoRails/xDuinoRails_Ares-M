import machine
import rp2
import time

# --- Configuration ---
# The GPIO pin to output the 10us signal. 
# Using GP0 as an example.
SIGNAL_PIN = 0 

# Desired PIO state machine frequency (Hz).
# System clock is typically 125 MHz.
# To make 1 PIO cycle = 1 microsecond (1 us), we need 1 / 1e-6 = 1,000,000 Hz (1 MHz).
# The PIO state machine configuration will automatically calculate the required divider (125MHz / 1MHz = 125.0).
TARGET_FREQ_HZ = 1_000_000 

# --- PIO Program Definition ---
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def pulse_10us():
    # .wrap_target and .wrap instruct the PIO to loop continuously between these lines.
    .wrap_target
    
    # Set the output pin high for 10 cycles.
    # The instruction itself takes 1 cycle. The '[9]' adds 9 delay cycles.
    # Total HIGH time: 1 cycle + 9 cycles = 10 cycles = 10 us (since 1 cycle = 1 us).
    # 
    set(pins, 1)        [9] 
    
    # Set the output pin low for 10 cycles.
    # Total LOW time: 1 cycle + 9 cycles = 10 cycles = 10 us.
    set(pins, 0)        [9] 
    .wrap

# --- Main Application ---
def start_pio_signal():
    """
    Initializes the PIO State Machine to run the 10us square wave program.
    """
    print(f"Starting PIO signal on GP{SIGNAL_PIN} at {TARGET_FREQ_HZ/1e6:.1f} MHz")
    
    # Claim a State Machine (sm 0-3 on PIO 0 is typical)
    # The 'freq' parameter sets the clock divider for us.
    sm = rp2.StateMachine(
        0,                             # State Machine ID (0-3)
        pulse_10us,                    # The PIO assembly program
        freq=TARGET_FREQ_HZ,           # The target clock frequency (1 MHz)
        set_base=machine.Pin(SIGNAL_PIN) # The base pin controlled by 'set' instructions
    )

    # Start the state machine running
    sm.active(1)

    # The PIO program runs in the background. The main Python thread can 
    # now run other code or simply wait.
    print(f"Signal running. The period is 20 us (50 kHz). Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
            # You can add main loop logic here if needed
            pass
    except KeyboardInterrupt:
        print("\nStopping PIO State Machine...")
        sm.active(0)
        # Reset the pin mode back to input/safe state
        machine.Pin(SIGNAL_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
        print("Signal stopped.")

if __name__ == "__main__":
    start_pio_signal()
