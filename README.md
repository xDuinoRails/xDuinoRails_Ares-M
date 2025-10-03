# xDuinoRails_Ares-M

A little trilingual central to provide DCC, MärklinMotorola and Selectrix signals.

## Current features
- Written in MicroPython allow "compiler-less" modification & hacking.
- Provide PIO engines for:
  * DCC protocol
  * Märklin Motorola protocol
  * Selectrix protocol

## Planned features
- Integrated 3in1 engine with protocol changes compliant to [RCN-200](https://normen.railcommunity.de/RCN-200.pdf).

## Limitations:
- Requieres a Raspberry PIO engine to run, mostly RP2040/RP235x.
- Maybe porting to Raspberry 5 using the RP1 is an option: https://github.com/MichaelBell/rp1-hacking/blob/main/PIO.md
