"""
Level-shifter and data-line diagnostic. Run with sudo.

matrix-text.py exercises the whole chain at WS2812 speed, which is useless for
debugging with a multimeter. This holds GPIO 18 at a steady DC level instead,
so each stage of the chain can be measured with nothing more than a meter.

    sudo python3 gpio/matrix_diag.py high     # hold 3.3V out of the Pi
    sudo python3 gpio/matrix_diag.py low      # hold 0V
    sudo python3 gpio/matrix_diag.py toggle   # 1Hz square wave

Where to put the probe, black lead on any common ground:

    Pi header pin 12 ............ GPIO 18 itself.       high -> ~3.3V
    74AHCT125 pin 2 ............. shifter input (1A).   high -> ~3.3V
    74AHCT125 pin 3 ............. shifter output (1Y).  high -> ~4.5-5V
    74AHCT125 pin 14 ............ shifter VCC.          always ~5V
    74AHCT125 pin 1 ............. output enable (1OE).  always ~0V
    Matrix DIN pad .............. what the panel sees.  high -> ~4.5-5V
    Matrix 5V / GND terminals ... panel supply.         always ~5V

The first place the expected voltage fails to appear is the fault.
"""

import sys
import time

from gpiozero import LED

PIN = 18  # BCM 18 == physical header pin 12, NOT physical pin 18

MODES = ("high", "low", "toggle")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "toggle"
    if mode not in MODES:
        print(f"usage: sudo python3 {sys.argv[0]} [{'|'.join(MODES)}]")
        return 1

    line = LED(PIN)
    print(f"GPIO {PIN} (physical header pin 12) -> {mode}")
    print("ctrl-c to stop and release the pin\n")

    try:
        if mode == "high":
            line.on()
            print("held HIGH. Expect ~3.3V at the Pi and shifter input,")
            print("and ~5V at the shifter output and matrix DIN.")
            while True:
                time.sleep(1)
        elif mode == "low":
            line.off()
            print("held LOW. Expect ~0V everywhere along the data path.")
            while True:
                time.sleep(1)
        else:
            print("toggling at 1Hz. A meter will swing between the two levels;")
            print("if you have a scope or a logic probe, use that instead.")
            while True:
                line.on()
                time.sleep(0.5)
                line.off()
                time.sleep(0.5)
    except KeyboardInterrupt:
        line.off()
        line.close()
        print("\nreleased")
    return 0


if __name__ == "__main__":
    sys.exit(main())
