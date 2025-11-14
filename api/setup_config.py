#!/usr/bin/env python3
"""
Configuration setup helper for Slime Mold Monitor
Creates config.py from template with user customization
"""

import os
import shutil

def setup_config():
    """Interactive configuration setup"""
    print("Slime Mold Monitor Configuration Setup")
    print("=" * 40)
    
    # Check if config.py already exists
    if os.path.exists('config.py'):
        response = input("\nconfig.py already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Configuration setup cancelled.")
            return
    
    # Copy template
    shutil.copy('config_template.py', 'config.py')
    print("\nCreated config.py from template.")
    
    # Optional: Interactive customization
    print("\nWould you like to customize some common settings? (y/N): ")
    if input().lower() == 'y':
        print("\nLeave blank to keep default values.\n")
        
        # Server port
        port = input(f"Server port [5000]: ")
        if port:
            update_config_value('SERVER_PORT', port)
        
        # Image capture interval
        interval = input(f"Image capture interval in seconds [300]: ")
        if interval:
            update_config_value('IMAGE_CAPTURE_INTERVAL', interval)
        
        # Max exposure duration
        max_exposure = input(f"Max exposure light duration in seconds [30]: ")
        if max_exposure:
            update_config_value('MAX_EXPOSURE_DURATION', max_exposure)
        
        # DHT sensor
        use_dht = input(f"Enable DHT sensor? (y/N): ")
        if use_dht.lower() == 'y':
            update_config_value('ENABLE_DHT_SENSOR', 'True')
            dht_pin = input(f"DHT GPIO pin [4]: ")
            if dht_pin:
                update_config_value('DHT_PIN', dht_pin)
        
        print("\nConfiguration updated!")
    
    print("\nSetup complete! You can edit config.py directly for more options.")
    print("Run 'python slime_api.py' to start the server.")

def update_config_value(key, value):
    """Update a value in config.py"""
    with open('config.py', 'r') as f:
        lines = f.readlines()
    
    with open('config.py', 'w') as f:
        for line in lines:
            if line.strip().startswith(f'{key} ='):
                # Preserve formatting and comments
                parts = line.split('=', 1)
                if '#' in parts[1]:
                    comment_parts = parts[1].split('#', 1)
                    f.write(f"{parts[0]}= {value} #{comment_parts[1]}")
                else:
                    f.write(f"{parts[0]}= {value}\n")
            else:
                f.write(line)

if __name__ == "__main__":
    setup_config()
