# sx_track_tx.py — Selectrix Gleissignal (SX1) mit RP2040 PIO (MicroPython)
#
# Erzeugt 3-stufiges SX-Gleis-Signal: 10 µs 0V + 40 µs ±V pro Bit
#
# Polaritätskodierung nach D&H: gleiche Polarität = '0', unterschiedliche = '1'
#
# Block-/Datenstruktur nach NEM 681 (Header + 7 Kanäle à 12 Bit)
#
# ACHTUNG: H-Brücke/Booster erforderlich. Nie direkt an die Schienen!
#
import _thread
import utime
from machine import Pin
from rp2 import PIO, StateMachine, asm_pio

# ===================== PIO: 2 Pins (IN1, IN2) =====================

@asm_pio(
    set_init=(PIO.OUT_LOW, PIO.OUT_LOW),  # 2 Pins per SET: (IN1, IN2)
    out_init=(PIO.OUT_LOW, PIO.OUT_LOW),  # dieselben 2 Pins per OUT
    out_shiftdir=PIO.SHIFT_LEFT,          # MSB->LSB in OSR wird links ausgegeben
    autopull=True, pull_thresh=32         # wir liefern 32er-Wörter, PIO nimmt sich Bits
)
def sx_track():
    # Pro Datenbit:
    #  - 10 µs Pause (0 V) => set(pins, 0b00) [9]
    #  - 40 µs Energie mit gewünschter Polarität:
    #       out(pins, 2)    (holt 2 Bits aus OSR: b1->IN2, b0->IN1)
    #       nop() [39]
    wrap_target()
    set(pins, 0b00)   [9]   # 10 µs Pause
    out(pins, 2)            # 2-Bit-Symbol -> IN2..IN1
    nop()             [39]  # 40 µs halten
    wrap()

# ===================== Host-Seite: Protokollaufbau =====================

class SelectrixTrackTX:
    """
    SX1-Zentrale für das Gleissignal.
    Erzeugt fortlaufend 16 Blöcke (112 Adressen) mit 20 kBit/s (50 µs/Bit).
    """
    def __init__(self, in1_pin, in2_pin, sm_id=0, sm_freq=1_000_000):
        # 1 MHz => 1 µs / Instruktion (10 + 40 µs Delays)
        self._in1 = Pin(in1_pin, Pin.OUT, value=0)
        self._in2 = Pin(in2_pin, Pin.OUT, value=0)
        self.sm = StateMachine(
            sm_id, sx_track, freq=sm_freq,
            set_base=self._in1, out_base=self._in1  # 2-Pin-Gruppe: IN1,IN2
        )
        self.channels = bytearray(112)  # 112 Adressen à 8 Bit
        self.rail_on = 1                # Z-Bit im Header
        self._frame_words = []
        self._dirty = True
        self._run = False

    # ---------- NEM 681: Header- und Datenkodierung ----------

    @staticmethod
    def _encode_byte12(value):
        """8->12 Bit: nach je 2 Datenbits eine '1' einfügen (MSB-first)."""
        v = value & 0xFF
        bits = []
        for hi, lo in ((7,6),(5,4),(3,2),(1,0)):
            bits.append((v >> hi) & 1)
            bits.append((v >> lo) & 1)
            bits.append(1)
        return bits  # 12 Bits

    def _encode_header12(self, base_nibble):
        """
        Header: 0 0 0 1  Z  1  BA3 BA2 1  BA1 BA0 1
        NEM 681: BA wird invertiert übertragen (BAinv).
        """
        ba = base_nibble & 0xF
        bainv = (~ba) & 0xF
        b3 = (bainv >> 3) & 1
        b2 = (bainv >> 2) & 1
        b1 = (bainv >> 1) & 1
        b0 = (bainv >> 0) & 1
        return [0,0,0,1, self.rail_on, 1, b3, b2, 1, b1, b0, 1]

    def _encode_block_bits(self, base):
        """
        Liefert die 96 Bits eines Blocks: 12 Header + 7×12 Daten.
        Adressen in diesem Block: base, base+16, ..., base+96
        """
        bits = self._encode_header12(base)
        for i in range(7):
            addr = base + 16*i
            bits += self._encode_byte12(self.channels[addr])
        return bits  # 96 Bits

    # ---------- Polaritätsabbildung & Wortpacken (2 Pins) ----------

    @staticmethod
    def _t1bits_to_polarity_symbols(t1_bits, start_polarity=1):
        """
        Aus T1-Bitfolge (0=gleiche Pol.; 1=wechselnde Pol.) absolute Polarität erzeugen.
        Rückgabe: Liste 2-Bit-Symbole pro Datenbit für (IN2..IN1):
          +V  => '01'  (IN2=0, IN1=1)
          -V  => '10'  (IN2=1, IN1=0)
        """
        pol = 1 if start_polarity else 0  # 1=+V, 0=-V
        symbols = []
        for b in t1_bits:
            if b & 1:  # '1' => toggeln
                pol ^= 1
            # Map auf (IN2..IN1):
            symbols.append(0b01 if pol else 0b10)
        return symbols

    @staticmethod
    def _symbols2_to_words(symbols):
        """
        Packt 2-Bit-Symbole (MSB-first) in 32-Bit-Wörter für OSR (SHIFT_LEFT).
        Erstes Symbol -> Bits 31:30, nächstes -> 29:28, ...
        """
        out = []
        i = 0
        n = len(symbols)
        while i < n:
            w = 0
            take = min(16, n - i)  # 16 Symbole * 2 Bit = 32 Bits
            for s in range(take):
                val = symbols[i + s] & 0b11
                shift = 30 - 2*s
                w |= (val << shift)
            out.append(w)
            i += take
        return out

    def _rebuild_frame(self):
        # 16 Blöcke -> 1536 T1-Bits -> 1536 2-Bit-Symbole -> 96 Wörter
        t1 = []
        for base in range(16):
            t1 += self._encode_block_bits(base)
        symbols = self._t1bits_to_polarity_symbols(t1, start_polarity=1)
        self._frame_words = self._symbols2_to_words(symbols)
        self._dirty = False

    # ---------- Public API ----------

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
        self._in1.value(0); self._in2.value(0)

    # Hintergrund-Streamer (≈ 96 Wörter pro 76,8 ms)
    def _tx_loop(self):
        while self._run:
            if self._dirty:
                self._rebuild_frame()
            for w in self._frame_words:
                if not self._run:
                    break
                self.sm.put(w)  # PIO verbraucht je 2 Bits/Bitzeit deterministisch
