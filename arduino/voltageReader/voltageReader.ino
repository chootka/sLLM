#include <SPI.h>

const int slaveSelectPin = 10;

void setup() {
  pinMode(slaveSelectPin, OUTPUT);
  Serial.begin(1200); //10800

  // Set up and start the SPI serial interface
  SPI.begin();
  SPI.setBitOrder(MSBFIRST); // Most significant bit first
  SPI.setClockDivider(SPI_CLOCK_DIV2); // Step down the arduino clock by 8
  SPI.setDataMode(SPI_MODE1); //Serial interface timing
}

void loop()
{ 
  //readRaw();
  readVoltage();
  //delay(200);
}

/* Allows the caller to read the raw value from the ADS1118 */
int readRaw(void) {
  byte newMSB;
  byte newLSB;
  uint16_t rawValue; // Raw value received back from the ADS1118
  byte MSB, LSB; //The most and least significant bits read from the ADS1118
  byte MSBConf=B00001110; // Most Significant Bit configuration register
  //11010001
  byte LSBConf=B01101011; // Least Significant Bit configuration register
  //10000010
  digitalWrite(slaveSelectPin,LOW);
  // Read the ADS1118's channel's A0 and A1 as voltage in single-shot mode
  MSB = SPI.transfer(MSBConf);
  //Serial.println(MSB,BIN);
  LSB = SPI.transfer(LSBConf);
  // Serial.println(LSB,BIN);
  //SPI.transfer(MSBConf);
  //SPI.transfer(LSBConf);
   digitalWrite(slaveSelectPin,HIGH);
  // Build the raw value from the most and least significant bits
  rawValue = (MSB << 8) | LSB;
  //newMSB=MSB;
  newLSB=LSB;
  //Serial.println(rawValue);
 // Serial.println(newLSB,2);
  return rawValue;
}

/* Allows the caller to read the raw voltage */
float readVoltage(void) {
  int rawValue; // Raw value received back from the ADS1118
  float volts; // Converted voltage from the raw value
  const float amp = 0.256; // FS multiplier in register (check data sheet)

  // Get the raw value so that we can convert it to a voltage
  rawValue = readRaw();
  //Serial.println(rawValue);
  // Convert the raw value to the corresponding voltage (16 bits = 0 to 32767)
  volts = (256.0/32768.0)*rawValue;//(rawValue / 32768.0);

  
  Serial.println(volts);
  return volts;
}
