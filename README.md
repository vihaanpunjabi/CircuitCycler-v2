# CircuitCyclers
_________________

Final Code of E-Waste Manager

Project part of AAASE Stanford Program

By Vihaan, Yash, Alan, Selena and William

# Get it working
__________________

📋 COMPLETE SETUP CHECKLIST
1. Python Environment Setup
bash# Install required Python packages
pip install google-generativeai flask python-dotenv pyserial opencv-python numpy

## Create project folder
mkdir ml_sorting_system
cd ml_sorting_system

## Create required folders
mkdir received_images
mkdir images
2. Environment Configuration
Create a .env file in your project folder:
envGOOGLE_API_KEY=your_actual_google_api_key_here
Get your Google API key from: https://makersuite.google.com/app/apikey


## 3. Create Your prompt.md File

Create a file called prompt.md with your ML instructions:

In the files

For sorting decisions:
- LEFT: Safe items that can be shredded normally
- RIGHT: Items needing special handling or containing hazardous materials

Consider safety as the top priority. When in doubt, choose RIGHT.
## 4. Arduino Setup

Upload the Arduino code I provided above to your Arduino Mega
Connect your servos:

Servo 1 (primary sorting): Pin 12
Servo 2 (secondary/conveyor): Pin 13
Both servos: 5V and GND from Arduino



## 5. Python Code Configuration

In the Python code, update this line for your system:
python# Windows:
ARDUINO_PORT = 'COM3'  # Check Device Manager for correct port

## Mac:
ARDUINO_PORT = '/dev/tty.usbmodem14101'  # Check: ls /dev/tty.usb*

## Linux:
ARDUINO_PORT = '/dev/ttyUSB0'  # Check: ls /dev/ttyUSB*
6. Phone Setup Options
Option A: Simple HTTP POST App (Recommended)
Use any HTTP client app on your phone:
For Android:

Install "HTTP Request Shortcuts" from Play Store
Create a shortcut with:

URL: http://YOUR_COMPUTER_IP:5000/api/upload_image
Method: POST
File parameter name: image



## For iPhone:

Install "Shortcuts" app
Create shortcut to take photo and POST to your server

Option B: Simple Web Interface
Access http://YOUR_COMPUTER_IP:5000 on your phone's browser for manual testing.
Option C: Camera App with Auto-Upload
Use "IP Webcam" (Android) or similar apps that can auto-upload images.
7. File Structure
Your project should look like this:
ml_sorting_system/
├── .env                          # Your API key
├── prompt.md                     # ML analysis instructions
├── ml_sorting_system.py          # Main Python code
├── arduino_servo_control.ino     # Arduino code
├── received_images/              # Uploaded photos folder
└── ml_sorting_system.log         # System log file
🚀 STARTUP SEQUENCE
Step 1: Start Arduino

Connect Arduino via USB
Open Arduino Serial Monitor (115200 baud)
Verify you see "READY" message

Step 2: Find Your Computer's IP Address
bash# Windows
ipconfig

## Mac/Linux  
hostname -I
Step 3: Start Python System
bashpython ml_sorting_system.py
You should see:
ML E-WASTE SORTING SYSTEM STARTING...
Arduino connected successfully on COM3
ML Analyzer initialized successfully
System ready for phone camera input...
Phone endpoint: http://192.168.1.100:5000/api/upload_image
Step 4: Test the System

Test Arduino manually:

Send "TEST" in Arduino Serial Monitor
Both servos should move through test sequence


Test via web interface:

Go to http://YOUR_IP:5000 in browser
Should show system status


Test with phone:

Take a photo of electronic waste
POST it to /api/upload_image
Watch Arduino servos move based on ML decision



## 📱 Phone App Quick Setup
Simplest Method - Use Postman Mobile:

Install Postman app
Create new POST request
URL: http://YOUR_COMPUTER_IP:5000/api/upload_image
Body: Form-data, key="image", value=select photo
Send!

🔧 Troubleshooting
Arduino not connecting?

Check COM port in Device Manager (Windows)
Try different USB cable
Ensure Arduino IDE can upload to the board

Python errors?

Check your .env file has the correct API key
Verify all pip packages installed
Check Arduino port name in code

Servos not moving?

Verify power connections (5V, GND)
Check servo wiring to pins 12 and 13
Test servos individually in Arduino Serial Monitor

Phone can't connect?

Ensure phone and computer on same WiFi network
Check firewall isn't blocking port 5000
Try the computer's IP address in phone browser first

That's everything you need! The system will automatically analyze photos from your phone and control the Arduino servos based on the ML decision. 🎉
