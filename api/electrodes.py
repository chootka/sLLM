#!/usr/bin/env python3
"""
Simple test script for aluminum tape electrodes
Tests the electrical reading setup before running the full API
"""

import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

def test_electrodes():
    print("Aluminum Tape Electrode Test")
    print("=" * 40)
    
    try:
        # Initialize I2C and ADC
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c)
        
        # Set gain to ±4.096V range (for higher sensitivity with small signals)
        ads.gain = 1
        
        # Create differential input between A0 and A1
        chan = AnalogIn(ads, ADS.P0, ADS.P1)
        
        print("ADC initialized successfully!")
        print(f"Measuring differential voltage between A0 and A1")
        print(f"Press Ctrl+C to stop\n")
        
        # Take continuous readings
        while True:
            voltage = chan.voltage
            raw_value = chan.value
            
            print(f"Voltage: {voltage:>6.4f} V | Raw ADC: {raw_value:>6d} | ", end='')
            
            # Simple visualization
            bar_length = int(abs(voltage) * 10)
            bar = '█' * min(bar_length, 50)
            print(f"|{bar}")
            
            time.sleep(0.5)
            
    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. Check I2C is enabled: sudo raspi-config")
        print("2. Verify wiring to ADS1115")
        print("3. Run 'i2cdetect -y 1' to check if device is detected")

if __name__ == "__main__":
    test_electrodes()
