# selectrix_tx.py  —  SX1 Sender (T0+T1) für RP2040 PIO in MicroPython
# Autor: Olivier’s Copilot 😉
#
# Hardware:
#  - RP2040-Pins über Pegelwandler (5V!) an SX-Bus: T0 (Clock), T1 (Daten).
#  - Niemals +20V an den Pico! T0/T1 sind 5V-Logik, D nur lesen (hier ungenutzt).

import _thread
import utime
from machine import Pin
from rp2 import PIO, StateMachine, asm_pio

# === PIO-Programm ===
# - sideset(1) steuert T0.
# - out(pins, 1) schiebt 1 Bit aus OSR auf T1 (out_base).
# - SM-Frequenz = 1 MHz -> 1 Zyklus = 1 µs.
# - T0 low: 10 µs  (out ... .side(0) [9])   -> währenddessen T1-Bit ausgeben
# - T0 high: 40 µs (nop       .side(1) [39])

@asm_pio(
    sideset_init = PIO.OUT_LOW,     # T0 initial Low
    out_init     = PIO.OUT_LOW,         # T1 initial Low
    out_shiftdir=PIO.SHIFT_LEFT,  # MSB-first aus OSR
    autopull=True,                # automatisch 32 Bit nachladen
    pull_thresh=32                # immer volle 32 Bit ziehen
)
def sx_tx():
    wrap_target()
    # Low-Phase: nächstes T1-Bit ausgeben, T0 = 0, 10 µs halten
    out(pins, 1).side(0) [9]
    # High-Phase: T0 = 1, 40 µs halten (T1 bleibt stabil)
    nop()        .side(1) [39]
    wrap()

class SelectrixTX:
    """
    Einfache SX1-Zentrale: streamt alle 112 Kanäle (bytes) zyklisch als 16 Blöcke.
    T0 wird im PIO generiert; T1 wird bitserial nach SX-Codierung ausgegeben.
    """
    def __init__(self, t0_pin, t1_pin, sm_id=0, sm_freq=1_000_000):
        self._t0 = Pin(t0_pin, Pin.OUT)
        self._t1 = Pin(t1_pin, Pin.OUT)
        self.sm = StateMachine(
            sm_id, sx_tx, freq=sm_freq,
            sideset_base=self._t0, out_base=self._t1
        )
        self.channels = bytearray(112)   # 112 SX-Adressen à 8 Bit
        self.rail_on = 1                 # Gleisspannung-Bit im Blockheader
        self._frame_words = []
        self._dirty = True
        self._run = False

    # --------- SX-Codierung ---------
    @staticmethod
    def _encode_byte12(value):
        """8 Bit -> 12 Bit (nach je 2 Datenbits eine '1' einfügen, MSB-first)."""
        b = int(value) & 0xFF
        bits = []
        pairs = [(7,6), (5,4), (3,2), (1,0)]
        for hi, lo in pairs:
            bits.append((b >> hi) & 1)
            bits.append((b >> lo) & 1)
            bits.append(1)  # Einschub-1
        return bits  # Länge 12

    def _encode_header12(self, base_nibble):
        """12 Header-Bits: 0001 + rail_on + 1 + (b3 b2 1 b1 b0 1)."""
        b3 = (base_nibble >> 3) & 1
        b2 = (base_nibble >> 2) & 1
        b1 = (base_nibble >> 1) & 1
        b0 = (base_nibble >> 0) & 1
        return [0,0,0,1, self.rail_on, 1, b3, b2, 1, b1, b0, 1]

    @staticmethod
    def _bits_to_words_msb_first(bits):
        """Packt Bitliste (b0 zuerst zu senden) in 32-Bit-Wörter (b0 -> Bit31)."""
        words = []
        i = 0
        n = len(bits)
        while i < n:
            w = 0
            chunk_len = min(32, n - i)
            for j in range(chunk_len):
                if bits[i + j]:
                    w |= (1 << (31 - j))
            # Rest wird implizit mit 0 gepolstert
            words.append(w)
            i += chunk_len
        return words

    def _encode_block_words(self, base):
        """
        Erzeugt 3x 32-Bit-Wörter (= 96 Bits) für einen SX-Block:
        12 Bit Header + 7 * (12 Bit Daten) = 96 Bit.
        Adressen in diesem Block: base, base+16, ..., base+96.
        """
        bits = self._encode_header12(base)
        for i in range(7):
            addr = base + 16*i
            bits += self._encode_byte12(self.channels[addr])
        assert len(bits) == 96
        return self._bits_to_words_msb_first(bits)  # 3 Wörter

    def _rebuild_frame(self):
        """Komplette 16-Blöcke-Frame (48 Wörter) neu aufbauen."""
        words = []
        for base in range(16):
            words += self._encode_block_words(base)
        self._frame_words = words
        self._dirty = False

    # --------- API ---------
    def set_track_power(self, on: bool):
        self.rail_on = 1 if on else 0
        self._dirty = True

    def set_channel(self, addr: int, value: int):
        if 0 <= addr < 112:
            self.channels[addr] = value & 0xFF
            self._dirty = True

    def start(self):
        self._rebuild_frame()
        self.sm.active(1)
        self._run = True
        _thread.start_new_thread(self._tx_loop, ())

    def stop(self):
        self._run = False
        utime.sleep_ms(5)
        self.sm.active(0)

    # Hintergrund-Streamer: schiebt fortlaufend 48 Wörter / Frame in die PIO
    def _tx_loop(self):
        while self._run:
            # ggf. Frame aktualisieren (z.B. nach set_channel)
            if self._dirty:
                self._rebuild_frame()
            for w in self._frame_words:
                if not self._run:
                    break
                self.sm.put(w)  # blockiert, wenn FIFO voll; PIO läuft deterministisch
