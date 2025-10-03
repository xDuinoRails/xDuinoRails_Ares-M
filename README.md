# xDuinoRails_Ares-M

A little trilingual central to provide DCC, MärklinMotorola and Selectrix signals.

# Overview
This project is "work in progress" to implement a triprotocol central using RP2040-PIO. 

Check out the lovely Wokwi for working samples:

| Method | Description | Example Filename | Wokwi |
| :--- | :--- | :--- | :--- |
| DCC-Railcom | Tx-DCC signal with Cut-Outs for Rx-RailCom | pio_dcc_railcom_cutout.py | [Wokwi DCC-Railcom](https://wokwi.com/projects/410567170220693505) |
| MM | Generate the Märklin Motorola 2 from the '90s | pio_maerklin_motorola.py | [Wokwi MM](https://wokwi.com/projects/443738742791247873) |
| SX | Manual timing via GPIO and delays | pio_selectrix.py | [Wokwi Selectrix](https://wokwi.com/projects/443741787827934209) |

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
