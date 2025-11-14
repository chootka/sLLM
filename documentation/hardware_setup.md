# Slime Mold Monitor - Hardware Setup Guide

## Components Needed

### Currently Available:
- Raspberry Pi 4/5
- Microscope with ring light
- Microscope camera
- Macro lens camera
- Slime molds in petri dishes
- Aluminum tape

### Still Needed:
- ADS1115 ADC module (for electrical readings)
- Additional LED for exposure light
- DHT22 temperature/humidity sensor (optional but prepared)
- Resistors (330Ω for LED, 10kΩ for pull-down, 4.7kΩ for DHT22)
- Jumper wires
- Breadboard

## Wiring Diagram

### Aluminum Tape Electrodes:
```
Petri Dish with Slime Mold
    |
    | (Aluminum tape strip 1)
    |
    +----> To ADS1115 A0
    |
    | (Aluminum tape strip 2)
    |
    +----> To ADS1115 A1
```

### Raspberry Pi GPIO Connections:
```
RPi GPIO          Device
--------          ------
GPIO 2 (SDA) ---> ADS1115 SDA
GPIO 3 (SCL) ---> ADS1115 SCL
3.3V ---------> ADS1115 VDD
GND ----------> ADS1115 GND

GPIO 17 -------> Ring Light Control (via relay/transistor)
GPIO 27 -------> Exposure LED (through 330Ω resistor)

GPIO 4 --------> DHT22 Data Pin
3.3V ---------> DHT22 VCC
GND ----------> DHT22 GND
                (4.7kΩ resistor between Data and VCC)

Camera --------> USB or CSI port (depending on camera type)
```

### ADS1115 Configuration:
- A0: Aluminum tape electrode 1
- A1: Aluminum tape electrode 2
- ADDR: Connect to GND for default address 0x48

## Setting Up the Electrodes

1. **Prepare the Petri Dish:**
   - Clean the petri dish thoroughly
   - Let it dry completely

2. **Apply Aluminum Tape:**
   - Cut two strips of aluminum tape, about 1cm wide
   - Place them on opposite sides of the petri dish
   - Leave about 5cm extending outside for connections
   - Ensure the strips don't touch each other

3. **Inoculate with Slime Mold:**
   - Place the slime mold in the center
   - Ensure it has paths to both electrodes
   - Add oat flakes as food sources

4. **Connect to ADC:**
   - Use alligator clips or solder wires to the aluminum tape
   - Connect one strip to A0, the other to A1
   - This creates a differential measurement

## Setting Up the DHT22 Sensor (Optional)

1. **DHT22 Pin Configuration:**
   - Pin 1 (VCC): Connect to 3.3V
   - Pin 2 (Data): Connect to GPIO 4
   - Pin 3 (NC): Not connected
   - Pin 4 (GND): Connect to Ground

2. **Pull-up Resistor:**
   - Place a 4.7kΩ resistor between Data and VCC
   - This ensures reliable communication

3. **Placement:**
   - Mount the sensor inside your enclosure
   - Keep it away from heat sources (lights)
   - Ensure good airflow around the sensor

## Software Configuration

1. **Update the API URL in the frontend:**
   ```javascript
   // In slime_frontend.html, update this line:
   apiUrl: 'http://YOUR_PI_IP:5000',
   ```

2. **Configure the Pi for autostart (optional):**
   ```bash
   # Create systemd service
   sudo nano /etc/systemd/system/slime-monitor.service
   ```

   Add:
   ```ini
   [Unit]
   Description=Slime Mold Monitor API
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi
   Environment="PATH=/home/pi/slime_env/bin"
   ExecStart=/home/pi/slime_env/bin/python /home/pi/slime_api.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Enable the service:
   ```bash
   sudo systemctl enable slime-monitor.service
   sudo systemctl start slime-monitor.service
   ```

## Testing the Setup

1. **Test Electrical Readings:**
   - Run `python slime_api.py`
   - Access `http://YOUR_PI_IP:5000/api/readings`
   - You should see voltage values

2. **Test Camera:**
   - Access `http://YOUR_PI_IP:5000/api/capture-image` with POST request
   - Should return an image

3. **Test Light Control:**
   - POST to `http://YOUR_PI_IP:5000/api/trigger-light` with `{"state": "on"}`
   - LED should turn on

## Troubleshooting

### No Electrical Readings:
- Check I2C is enabled: `sudo raspi-config` > Interface Options > I2C
- Verify ADS1115 connection: `i2cdetect -y 1` (should show 48)
- Check aluminum tape connections

### Camera Issues:
- For USB cameras, check with `ls /dev/video*`
- For Pi Camera, enable in `raspi-config`
- May need to add user to video group: `sudo usermod -a -G video $USER`

### Permission Errors:
- GPIO access requires root or gpio group membership
- Add user to gpio group: `sudo usermod -a -G gpio $USER`
- Logout and login again

### Socket.IO Connection Issues:
- Ensure firewall allows port 5000: `sudo ufw allow 5000`
- Check that the frontend has the correct Pi IP address
- Verify Socket.IO is running: Check console for connection messages

### DHT22 Sensor Issues:
- If sensor not detected, system continues without it
- Common issue: "Unable to set line handle" - reboot Pi
- Check wiring, especially the pull-up resistor
- Try `sudo` if permission errors persist

## Safety Notes

- Keep exposure light duration short to avoid harming the slime mold
- Maintain proper humidity in the enclosure
- Handle the slime mold gently
- Keep the setup away from direct sunlight
