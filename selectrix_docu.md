# Selectrix (SX1) Gleissignal mit RP2040‑PIO (MicroPython)  
**README / Entwickler‑Dokumentation**

> Dieses Dokument beschreibt die Architektur, das Timing, die Protokoll‑Kodierung und die öffentliche API des MicroPython‑/PIO‑Senders, der das **Selectrix‑Gleissignal** (SX1) auf einem **Zweileiter‑Gleis** erzeugt. Es richtet sich an Entwickler:innen, die den Code warten, erweitern oder in eigene Projekte integrieren möchten.

---

## Inhalt

1. Ziel & Überblick  
2. Protokoll‑Hintergrund (am Gleis)  
3. Systemarchitektur  
4. Zeitverhalten & Timings  
5. Kodierung (Header, Daten, Polarität)  
6. PIO‑Programm & Datenpfad  
7. Modul‑API  
8. Verdrahtung & Sicherheit  
9. Test & Verifikation  
10. Leistung & Grenzen  
11. Beispiele  
12. Wartung, Portierung & Erweiterungen  
13. Quellen & weiterführende Links

---

## Ziel & Überblick

Der Code erzeugt das **originale Selectrix‑Gleissignal (SX1)** auf einem Zweileiter‑Gleis, kompatibel zu gängigen SX‑Lokdecodern. Die **PIO‑State‑Machine** des RP2040 garantiert das harte Timing (**50 µs pro Bit**) und steuert eine **H‑Brücke/Booster** an, so dass die drei erforderlichen Gleiszustände **+V / 0 V / −V** dargestellt werden. Der Host‑Teil (MicroPython) kodiert das Protokoll (Header, Datenbytes, 16 Blöcke, 112 Adressen).  
**Referenzen:** NEM 681 (Datenpaket), NEM‑Überblick & Systemzyklen, D&H Gleissignal (Timing & 3‑Stufigkeit).  
[1](https://www.morop.org/downloads/nem/de/nem681_d.pdf) [2](https://de.wikipedia.org/wiki/Selectrix) [3](https://www.1zu160.net/digital/selectrix.php) [4](https://doehler-haass.de/cms/pages/system-spezifikation/gleis-signale.php)

---

## Protokoll‑Hintergrund (am Gleis)

- **Gleissignal = Bus‑Signal**: Selectrix verwendet **dieselbe Datenstruktur** am Gleis wie auf dem SX‑Bus: **16 Blöcke**, jeder Block **12 Bit Header + 7×12 Bit Daten** ⇒ **112 Adressen** pro Zyklus.  
  [1](https://www.morop.org/downloads/nem/de/nem681_d.pdf) [2](https://de.wikipedia.org/wiki/Selectrix)
- **Zykluszeit**: ca. **76,8 ms** ⇒ alle **112 Adressen** werden **13× pro Sekunde** aktualisiert (deterministisch, lastunabhängig).  
  [2](https://de.wikipedia.org/wiki/Selectrix) [3](https://www.1zu160.net/digital/selectrix.php)
- **Bitzeit**: **50 µs** (≈ 20 kBit/s) mit **10 µs Pause** + **40 µs Spannung**.  
  **Datenkodierung durch Polarität**: **gleiche Polarität** wie beim vorherigen Bit = **‘0’**, **wechselnde Polarität** = **‘1’**.  
  [4](https://doehler-haass.de/cms/pages/system-spezifikation/gleis-signale.php)

---

## Systemarchitektur

```
+-----------------+      2-Bit-Symbole      +------------------+      ±V / 0V     +--------+
| MicroPython Host|  ─────────────────────▶ |   RP2040 PIO     | ───────────────▶ | H-Brücke| ─▶ Gleis
| (Encoder, Frame)|   (je Bit: IN2..IN1)    | (sx_track SM)    |    IN1 / IN2     | Booster |
+-----------------+                         +------------------+                  +--------+
        ↑                                              ↓
   112 Kanäle                                  10 µs 0V + 40 µs ±V
   (16 Blöcke)
```

- **Host** (MicroPython): baut die **16 Blöcke** (Header + 7×Daten) gemäß **NEM 681** auf, wandelt die **T1‑Bitfolge** in **absolute Polaritäts‑Symbole** um (2 Bit pro Gleis‑Bit: `01`=+V, `10`=−V) und füttert 32‑Bit‑Wörter in die PIO‑TX‑FIFO.  
  [1](https://www.morop.org/downloads/nem/de/nem681_d.pdf) [4](https://doehler-haass.de/cms/pages/system-spezifikation/gleis-signale.php)
- **PIO**: setzt pro Datenbit **10 µs 0 V** (beide Eingänge Low), dann **40 µs ±V** (gemäß Symbol) – völlig CPU‑unabhängig (deterministisch).  
  [5](https://docs.micropython.org/en/latest/rp2/tutorial/pio.html) [6](https://docs.micropython.org/en/latest/library/rp2.html)

---

## Zeitverhalten & Timings

- **Bitdauer**: 50 µs = 10 µs „0 V‑Pause“ + 40 µs Energie.  
  *Quelle / Begründung*: D&H beschreibt genau dieses **3‑stufige Codierschema** (Pause = Takt, 40 µs Spannung mit Polari­täts‑Kodierung).  
  [4](https://doehler-haass.de/cms/pages/system-spezifikation/gleis-signale.php)
- **Blocklänge**: 96 Bit → 4,8 ms/Block; **16 Blöcke** → **≈ 76,8 ms**/Zyklus → **13 Hz**.  
  [2](https://de.wikipedia.org/wiki/Selectrix) [3](https://www.1zu160.net/digital/selectrix.php)  
- **PIO‑Takt**: 1 MHz (1 µs/Zyklus) → Delay‑Felder `[9]` (10 µs) und `[39]` (40 µs) pro Bit.  
  [5](https://docs.micropython.org/en/latest/rp2/tutorial/pio.html)

---

## Kodierung (Header, Daten, Polarität)

1. **Header (12 Bit, NEM 681)**  
   `0 0 0 1  Z  1  BA3 BA2 1  BA1 BA0 1`  
   **BA** wird **invertiert** übertragen (BAinv), **Z** signalisiert Gleisspannungszustand.  
   [1](https://www.morop.org/downloads/nem/de/nem681_d.pdf)

2. **Datenbytes (8 → 12 Bit)**  
   Nach **je 2 Datenbits** wird **eine ‘1’** eingefügt (laufende „1“-Einschübe), so dass Sync‑Folgen (`0001`) im Nutzlastbereich **nicht auftreten** können.  
   [7](https://opensx.net/selectrix/sx-bus-signale/) [1](https://www.morop.org/downloads/nem/de/nem681_d.pdf)

3. **Adressierung im Block**  
   Block `base ∈ [0..15]` enthält die Adressen `base + 16*i` mit `i=0..6` ⇒ **7 Kanäle/Block × 16** = **112 Adressen** gesamt.  
   [3](https://www.1zu160.net/digital/selectrix.php) [2](https://de.wikipedia.org/wiki/Selectrix)

4. **Polaritäts‑Regel am Gleis (pro Bit)**  
   **‘0’** = gleiche Polarität wie vorher, **‘1’** = Polarität wechseln (D&H).  
   [4](https://doehler-haass.de/cms/pages/system-spezifikation/gleis-signale.php)

---

## PIO‑Programm & Datenpfad

### PIO‑Kernel (Kernidee)

```python
@asm_pio(set_init=(PIO.OUT_LOW, PIO.OUT_LOW),
         out_init=(PIO.OUT_LOW, PIO.OUT_LOW),
         out_shiftdir=PIO.SHIFT_LEFT, autopull=True, pull_thresh=32)
def sx_track():
    wrap_target()
    set(pins, 0b00) [9]   # 10 µs 0 V (beide Low) → „Pause“ / Takt
    out(pins, 2)          # 2-Bit-Symbol -> (IN2..IN1): 01 = +V, 10 = -V
    nop()           [39]  # 40 µs halten
    wrap()
```

- **Pin‑Gruppe**: `out_base=set_base=IN1` → PIO steuert **zwei GPIOs** (IN1, IN2) parallel (Low/High).  
  [6](https://docs.micropython.org/en/latest/library/rp2.html)
- **Symbolpackung**: Host packt **16 Symbole × 2 Bit = 32 Bit** pro PIO‑`pull` (Autopull).  
  Beispiel für das Packen (MSB‑first) orientiert sich an MicroPython‑Beispielen: **SHIFT_LEFT** + `out(pins, n)` liefert das jeweils **linke** Bit zuerst.  
  [8](https://github.com/micropython/micropython/blob/master/examples/rp2/pio_ws2812.py) [6](https://docs.micropython.org/en/latest/library/rp2.html)

---

## Modul‑API

```python
class SelectrixTrackTX:
    def __init__(self, in1_pin: int, in2_pin: int, sm_id=0, sm_freq=1_000_000): ...
    def set_track_power(self, on: bool): ...
    def set_channel(self, addr: int, value: int): ...
    def start(self): ...
    def stop(self): ...
```

- **`__init__(in1_pin, in2_pin, sm_id, sm_freq)`**  
  Initialisiert die PIO‑State‑Machine und Pufferspeicher. Standard‑SM‑Takt: **1 MHz** (siehe Timing).  
  [5](https://docs.micropython.org/en/latest/rp2/tutorial/pio.html)
- **`set_track_power(on)`**  
  Setzt das **Z‑Bit** im Header (Gleisspannung an/aus) → Frame wird neu aufgebaut.  
  [1](https://www.morop.org/downloads/nem/de/nem681_d.pdf)
- **`set_channel(addr, value)`**  
  Schreibt ein **8‑Bit Datenbyte** für Adresse `0..111` (z. B. Lok‑Byte: Bit 0–4 Speed, Bit 5 Richtung, Bit 6 Licht, Bit 7 Funktion – decoderabhängig).  
  [3](https://www.1zu160.net/digital/selectrix.php)
- **`start()` / `stop()`**  
  Startet/stoppt die kontinuierliche Ausgabe des gesamten **16‑Block‑Frames**. Daten werden **zyklisch** an die PIO gestreamt.

---

## Verdrahtung & Sicherheit

- **H‑Brücke/Booster** zwischen PIO‑Pins (IN1, IN2) und Gleis – **keine Direktverbindung** zum RP2040‑GPIO.  
  Der Booster muss **0 V („Coast“) erlauben**, wenn **IN1=IN2=0** (10 µs‑Pause).  
  [4](https://doehler-haass.de/cms/pages/system-spezifikation/gleis-signale.php)
- **Gleisspannung** je nach Spur (typisch 12–16 V), Kurzschluss‑Schutz & Sicherung einplanen (Zentrale/Booster).  
  [9](http://www.uwe-magnus.de/zentrale/zentranl.html)

> ⚠️ **Warnung:** Das Selectrix‑System nutzt zudem **+20 V** am SX‑Bus (nicht am Gleis) – diese Spannung **niemals** an GPIOs anlegen; Pegelwandler/Trennung sind Pflicht, wenn du später auch den SX‑Bus anbindest.  
> [7](https://opensx.net/selectrix/sx-bus-signale/)

---

## Test & Verifikation

1. **Logic‑Analyzer** an **IN1/IN2** (vor der H‑Brücke):  
   Pro Datenbit **10 µs beide Low** (Pause), dann **40 µs 01** ( +V ) **oder 10** ( −V ).  
   [4](https://doehler-haass.de/cms/pages/system-spezifikation/gleis-signale.php)
2. **Oszilloskop** am **Gleis**: 50 µs Bit‑Raster; **Polari­tätswechsel** bei Daten‑‘1’, **gleichbleibende** Polarität bei ‘0’.  
   [4](https://doehler-haass.de/cms/pages/system-spezifikation/gleis-signale.php)
3. **Zykluszeit** messen: **~76,8 ms** für alle 16 Blöcke.  
   [2](https://de.wikipedia.org/wiki/Selectrix) [3](https://www.1zu160.net/digital/selectrix.php)

---

## Leistung & Grenzen

- **Streaming‑Last**: 1536 Bits/Frame → **768 Symbole** → **48 32‑Bit‑Wörter** (mit dieser Implementierung: 96 Wörter) pro ~76,8 ms. Das ist für MicroPython unkritisch.  
  [5](https://docs.micropython.org/en/latest/rp2/tutorial/pio.html)
- **PIO‑Determinismus**: Bitzeiten werden unabhängig von Python‑Latenzen exakt eingehalten.  
  [5](https://docs.micropython.org/en/latest/rp2/tutorial/pio.html)

---

## Beispiele

### Minimaler Start

```python
from sx_track_tx import SelectrixTrackTX

sx = SelectrixTrackTX(in1_pin=10, in2_pin=11)
sx.set_track_power(True)
sx.set_channel(3,  0b00010111)  # Beispiel: Adresse 3 → Speed/Licht/Funktion (Decoder-spezifisch)
sx.set_channel(16, 0b01011111)  # Beispiel: Adresse 16 → Richtung=1, Speed=31
sx.start()
```

> **Hinweis zu Lok‑Bytes:** Viele SX‑Decoder interpretieren Bits wie folgt: **Bit 0–4** Speed (0–31), **Bit 5** Richtung, **Bit 6** Licht, **Bit 7** Funktion. Details sind **Decoder‑abhängig**.  
> [3](https://www.1zu160.net/digital/selectrix.php)

---

## Wartung, Portierung & Erweiterungen

- **Portierung auf C/C++** (Pico SDK) möglich, z. B. bei DMA‑Feeding. Die PIO‑Kernlogik (10 µs Pause + 40 µs Symbol) bleibt identisch.  
  [5](https://docs.micropython.org/en/latest/rp2/tutorial/pio.html)
- **Rückkanal / D‑Leitung**: Am **Gleis** gibt es keinen separaten D‑Draht; wer die **SX‑Bus‑D‑Leitung** auswerten will, kann eine zweite PIO‑SM einsetzen, die am Bus synchron sampelt (separates Thema).  
  [7](https://opensx.net/selectrix/sx-bus-signale/)
- **Erweiterte Protokolle (SX2, RMX …)** sind **nicht** Teil dieses Projekts (bewusst SX1‑kompatibel).  
  [3](https://www.1zu160.net/digital/selectrix.php)

---

## Quellen & weiterführende Links

**Normen / Protokoll:**
- MOROP **NEM 681**: *Digitales Steuersignal SX – Datenpakete* (Header, Basisadresse, 12‑Bit‑Gruppen)  
  <https://www.morop.org/downloads/nem/de/nem681_d.pdf>  
- Übersicht & Systemverhalten (112 Adressen, 76,8 ms Zyklus, 16×7 Struktur):  
  <https://de.wikipedia.org/wiki/Selectrix> • <https://www.1zu160.net/digital/selectrix.php>

**Gleissignal / Timing / 3‑Stufigkeit:**
- Döhler & Haass: *System‑Spezifikation / Gleis‑Signale* (10 µs Pause + 40 µs Spannung, Polaritäts‑Kodierung, 3 Zustände)  
  <https://doehler-haass.de/cms/pages/system-spezifikation/gleis-signale.php>

**Bus‑Signal (Hintergrund, Sync & 1‑Einschübe):**
- OpenSX: *SX‑Bus‑Signale* (Sync `0001`, 1‑Einschübe, 20 kHz Takt auf dem Bus)  
  <https://opensx.net/selectrix/sx-bus-signale/>

**MicroPython / PIO:**
- MicroPython **PIO‑Tutorial & rp2‑API** (asm_pio, StateMachine, out/set, Autopull, SHIFT_LEFT/RIGHT)  
  <https://docs.micropython.org/en/latest/rp2/tutorial/pio.html> • <https://docs.micropython.org/en/latest/library/rp2.html>  
- Beispiel zu **OUT‑Bitordnung / SHIFT_LEFT** (WS2812‑Treiber in MicroPython)  
  <https://github.com/micropython/micropython/blob/master/examples/rp2/pio_ws2812.py>

**Hintergrund / weiter lesen:**
- MEC Arnsdorf: *Selectrix Protokoll – Struktur & Daten*  
  <https://www.mec-arnsdorf.de/index.php/selectrix/selectrix-protokoll/>  
- Peter Stärz (Allgemeines zu SX, 13×/s, Normen)  
  <https://firma-staerz.de/index.php?sub=selectrix>

**Open‑Source‑Repos (Vergleich/Ideen):**
- OpenSX **SX** (Arduino‑Lib für SX‑Bus)  
  <https://github.com/opensx/SX>  
- OpenSX **PX** (Gleis‑Signal dekodieren, Arduino, BETA)  
  <https://github.com/opensx/PX>

---

### Lizenz

> Bitte füge hier die gewünschte Lizenz (z. B. MIT/BSD/GPL) für deinen Code ein. Die verlinkten Normen/Seiten unterliegen den jeweiligen Urheberrechten.

---

### Changelog (Beispiel)

- **v0.1.0** – Erste öffentlich dokumentierte Version (SX1 Gleissignal, 112 Kanäle, PIO‑Kernel mit 2‑Bit‑Symbolen, Host‑Encoder nach NEM 681).

---

#### Maintainer‑Hinweis

Für Pull‑Requests bitte **Timings** mit LA/Scope beilegen (Screenshots von **IN1/IN2** und **Gleis**). Änderungen an der **Kodierlogik** (NEM 681 / D&H‑Polarität) immer mit Quellen angeben – das bewahrt die **SX‑Kompatibilität**.
