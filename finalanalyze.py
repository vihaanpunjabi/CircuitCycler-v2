#!/usr/bin/env python3
"""
================================================================================
INTEGRATED ML SORTING SYSTEM
================================================================================
Combines your E-waste analyzer with real-time phone camera input and Arduino
servo control for automated sorting.

Flow: Phone Camera → Python ML Analysis → Arduino Servo Control
================================================================================
"""

import os
import sys
import json
import time
import serial
import logging
import base64
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from threading import Thread, Lock
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Google's AI library
try:
    import google.generativeai as genai
except ImportError:
    print("Error: Please install required libraries:")
    print("   pip install google-generativeai flask python-dotenv pyserial")
    sys.exit(1)

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# Google API Configuration
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("\nERROR: No Google API key found!")
    print("Create a .env file with: GOOGLE_API_KEY=your_actual_key_here")
    sys.exit(1)

genai.configure(api_key=API_KEY)

# Arduino Configuration
ARDUINO_PORT = 'COM3'  # Windows. For Mac/Linux: '/dev/ttyUSB0' or '/dev/ttyACM0'
ARDUINO_BAUD = 115200

# Flask Configuration
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000

# File Storage
UPLOAD_FOLDER = 'received_images'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ml_sorting_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__)

# Global variables
arduino_connection = None
arduino_lock = Lock()
ml_analyzer = None

# Statistics
stats = {
    'total_processed': 0,
    'safe_to_shred': 0,
    'requires_preprocessing': 0,
    'do_not_shred': 0,
    'discard_items': 0,
    'left_movements': 0,
    'right_movements': 0,
    'errors': 0,
    'start_time': datetime.now()
}

# ============================================================================
# ARDUINO CONTROLLER
# ============================================================================

class ArduinoController:
    def __init__(self, port: str, baud_rate: int):
        self.port = port
        self.baud_rate = baud_rate
        self.connection = None
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to Arduino with retry logic"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self.connection = serial.Serial(self.port, self.baud_rate, timeout=3)
                time.sleep(3)  # Wait for Arduino to initialize
                
                # Test connection
                response = self.send_command("STATUS", wait_for_ready=True)
                if response and "OK" in response:
                    self.connected = True
                    logger.info(f"Arduino connected successfully on {self.port}")
                    return True
                    
            except serial.SerialException as e:
                logger.warning(f"Arduino connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        logger.error("Failed to connect to Arduino after all retries")
        return False
    
    def send_command(self, command: str, wait_for_ready: bool = True) -> Optional[str]:
        """Send command to Arduino and get response"""
        if not self.connected or not self.connection:
            logger.error("Arduino not connected")
            return None
        
        try:
            with arduino_lock:
                # Send command
                command_bytes = (command + '\n').encode('utf-8')
                self.connection.write(command_bytes)
                self.connection.flush()
                
                logger.info(f"Sent to Arduino: {command}")
                
                # Read response
                response_lines = []
                timeout_start = time.time()
                
                while time.time() - timeout_start < 8:  # 8 second timeout
                    if self.connection.in_waiting:
                        line = self.connection.readline().decode('utf-8').strip()
                        if line:
                            response_lines.append(line)
                            logger.info(f"Arduino: {line}")
                            
                            # Check if Arduino is ready
                            if wait_for_ready and line == "READY":
                                break
                    time.sleep(0.1)
                
                return '\n'.join(response_lines)
                
        except Exception as e:
            logger.error(f"Error communicating with Arduino: {e}")
            self.connected = False
            return None
    
    def move_servo(self, direction: str) -> bool:
        """Move servo to specified direction"""
        direction = direction.upper()
        if direction not in ['LEFT', 'RIGHT', 'CENTER']:
            logger.error(f"Invalid servo direction: {direction}")
            return False
        
        response = self.send_command(direction, wait_for_ready=True)
        success = response is not None and "ERROR" not in response
        
        if success:
            logger.info(f"Servo moved to {direction} successfully")
            # Update movement statistics
            if direction == 'LEFT':
                stats['left_movements'] += 1
            elif direction == 'RIGHT':
                stats['right_movements'] += 1
        else:
            logger.error(f"Failed to move servo to {direction}")
            stats['errors'] += 1
            
        return success
    
    def test_servo(self) -> bool:
        """Test servo movement"""
        logger.info("Testing Arduino servo...")
        response = self.send_command("TEST", wait_for_ready=True)
        return response is not None and "ERROR" not in response
    
    def disconnect(self):
        """Disconnect from Arduino"""
        if self.connection:
            try:
                self.connection.close()
                self.connected = False
                logger.info("Arduino disconnected")
            except:
                pass

# ============================================================================
# ML ANALYZER (Your existing code adapted)
# ============================================================================

class MLSortingAnalyzer:
    """Enhanced version of your E-waste analyzer for real-time sorting"""
    
    def __init__(self):
        self.ai_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Load your existing prompt
        try:
            with open("prompt.md", 'r') as f:
                self.instructions = f.read()
        except FileNotFoundError:
            # Fallback prompt if file doesn't exist
            self.instructions = """
            Analyze this electronic waste image and determine:
            1. What type of electronic item this is
            2. Whether it's safe to shred or requires special handling
            3. Any hazardous components present
            4. Processing recommendations
            """
        
        # Response format for sorting decisions
        self.response_format = {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "What is this item?"
                },
                "safety_level": {
                    "type": "string",
                    "enum": ["Safe to Shred", "Requires Preprocessing", "Do Not Shred", "Discard"],
                    "description": "Can we shred it?"
                },
                "sorting_direction": {
                    "type": "string",
                    "enum": ["left", "right"],
                    "description": "Which direction to sort: left for safe items, right for dangerous/special handling items"
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confidence in the decision (0.0 to 1.0)"
                },
                "hazards": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of dangerous parts"
                },
                "notes": {
                    "type": "string",
                    "description": "Any warnings or special instructions"
                }
            },
            "required": ["item_name", "safety_level", "sorting_direction", "confidence", "hazards", "notes"]
        }
    
    def analyze_image_for_sorting(self, image_path: str) -> Dict:
        """
        Analyze image and return sorting decision
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with ML analysis and sorting decision
        """
        result = {
            "filename": os.path.basename(image_path),
            "timestamp": datetime.now().isoformat(),
            "item_name": "Unknown",
            "safety_level": "Do Not Shred",  # Default to safe option
            "sorting_direction": "right",    # Default to careful handling
            "confidence": 0.0,
            "hazards": [],
            "notes": "Analysis failed",
            "error": None
        }
        
        try:
            logger.info(f"Analyzing image: {image_path}")
            
            # Upload image to Google AI
            uploaded_image = genai.upload_file(image_path)
            
            # Enhanced prompt for sorting decisions
            sorting_prompt = f"""
            {self.instructions}
            
            IMPORTANT: Based on your analysis, decide sorting direction:
            - LEFT: Safe items that can be shredded normally (Safe to Shred)
            - RIGHT: Items needing special handling (Requires Preprocessing, Do Not Shred, or Discard)
            
            Consider safety as the top priority. When in doubt, choose RIGHT for safer handling.
            """
            
            # Generate analysis
            response = self.ai_model.generate_content(
                [sorting_prompt, uploaded_image],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=self.response_format,
                    temperature=0.1
                )
            )
            
            # Parse response
            ai_result = json.loads(response.text)
            result.update(ai_result)
            
            logger.info(f"ML Analysis complete: {result['item_name']} -> {result['sorting_direction']} (confidence: {result['confidence']:.2f})")
            
            # Update statistics
            stats['total_processed'] += 1
            safety_level = result['safety_level']
            if safety_level == "Safe to Shred":
                stats['safe_to_shred'] += 1
            elif safety_level == "Requires Preprocessing":
                stats['requires_preprocessing'] += 1
            elif safety_level == "Do Not Shred":
                stats['do_not_shred'] += 1
            elif safety_level == "Discard":
                stats['discard_items'] += 1
            
        except Exception as error:
            result["error"] = str(error)
            logger.error(f"ML analysis failed for {image_path}: {error}")
            stats['errors'] += 1
        
        return result

# ============================================================================
# FLASK WEB API
# ============================================================================

@app.route('/api/upload_image', methods=['POST'])
def upload_image():
    """Main endpoint for phone to upload images"""
    try:
        # Check Arduino connection
        if not arduino_connection or not arduino_connection.connected:
            return jsonify({
                'status': 'error',
                'message': 'Arduino not connected'
            }), 503
        
        # Check for image in request
        if 'image' not in request.files:
            return jsonify({
                'status': 'error', 
                'message': 'No image provided'
            }), 400
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No image selected'
            }), 400
        
        # Save uploaded image
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # milliseconds
        filename = f"ewaste_{timestamp}_{image_file.filename}"
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        
        image_file.save(image_path)
        logger.info(f"Image saved: {filename}")
        
        # Analyze with ML
        ml_result = ml_analyzer.analyze_image_for_sorting(image_path)
        
        if ml_result.get('error'):
            return jsonify({
                'status': 'error',
                'message': f"ML analysis failed: {ml_result['error']}",
                'filename': filename
            }), 500
        
        # Execute servo movement based on ML decision
        direction = ml_result['sorting_direction'].upper()
        servo_success = arduino_connection.move_servo(direction)
        
        if servo_success:
            response = {
                'status': 'success',
                'filename': filename,
                'ml_analysis': {
                    'item_name': ml_result['item_name'],
                    'safety_level': ml_result['safety_level'],
                    'sorting_direction': ml_result['sorting_direction'],
                    'confidence': ml_result['confidence'],
                    'hazards': ml_result['hazards'],
                    'notes': ml_result['notes']
                },
                'servo_action': f"Moved servo {direction}",
                'timestamp': ml_result['timestamp'],
                'stats': stats.copy()
            }
            
            logger.info(f"Complete sorting cycle successful: {ml_result['item_name']} -> {direction}")
            return jsonify(response), 200
        else:
            stats['errors'] += 1
            return jsonify({
                'status': 'partial_success',
                'message': 'ML analysis completed but servo movement failed',
                'ml_analysis': ml_result,
                'filename': filename
            }), 207  # Multi-status
            
    except Exception as e:
        logger.error(f"Error in upload_image: {e}")
        stats['errors'] += 1
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status and statistics"""
    uptime = datetime.now() - stats['start_time']
    
    return jsonify({
        'status': 'online',
        'arduino_connected': arduino_connection.connected if arduino_connection else False,
        'uptime_seconds': uptime.total_seconds(),
        'ml_analyzer_ready': ml_analyzer is not None,
        'stats': stats,
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/manual_sort', methods=['POST'])
def manual_sort():
    """Manual servo control for testing"""
    try:
        data = request.get_json()
        direction = data.get('direction', '').upper()
        
        if direction not in ['LEFT', 'RIGHT', 'CENTER']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid direction. Use LEFT, RIGHT, or CENTER'
            }), 400
        
        if not arduino_connection or not arduino_connection.connected:
            return jsonify({
                'status': 'error',
                'message': 'Arduino not connected'
            }), 503
        
        success = arduino_connection.move_servo(direction)
        
        return jsonify({
            'status': 'success' if success else 'error',
            'direction': direction,
            'message': f"Servo {'moved' if success else 'failed to move'} {direction}"
        }), 200 if success else 500
        
    except Exception as e:
        logger.error(f"Error in manual_sort: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/test_system', methods=['POST'])
def test_system():
    """Test complete system functionality"""
    try:
        results = []
        
        # Test Arduino connection
        if arduino_connection and arduino_connection.connected:
            servo_test = arduino_connection.test_servo()
            results.append(f"Arduino servo test: {'PASSED' if servo_test else 'FAILED'}")
        else:
            results.append("Arduino: NOT CONNECTED")
        
        # Test ML analyzer
        if ml_analyzer:
            results.append("ML Analyzer: READY")
        else:
            results.append("ML Analyzer: NOT READY")
        
        return jsonify({
            'status': 'success',
            'test_results': results,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error in test_system: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/', methods=['GET'])
def index():
    """Simple web interface showing system info"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>ML E-Waste Sorting System</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .status {{ padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .online {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .offline {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
            .stat-box {{ background: #e9ecef; padding: 15px; border-radius: 8px; text-align: center; }}
            .endpoint {{ background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 5px; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 ML E-Waste Sorting System</h1>
            <p>Automated electronic waste sorting using AI analysis and servo control</p>
            
            <div class="status {'online' if arduino_connection and arduino_connection.connected else 'offline'}">
                Arduino Status: {'Connected ✅' if arduino_connection and arduino_connection.connected else 'Disconnected ❌'}
            </div>
            
            <div class="status {'online' if ml_analyzer else 'offline'}">
                ML Analyzer Status: {'Ready ✅' if ml_analyzer else 'Not Ready ❌'}
            </div>
            
            <h3>📊 Statistics</h3>
            <div class="stats">
                <div class="stat-box">
                    <h4>Total Processed</h4>
                    <p>{stats['total_processed']}</p>
                </div>
                <div class="stat-box">
                    <h4>Safe to Shred</h4>
                    <p>{stats['safe_to_shred']}</p>
                </div>
                <div class="stat-box">
                    <h4>Special Handling</h4>
                    <p>{stats['requires_preprocessing'] + stats['do_not_shred']}</p>
                </div>
                <div class="stat-box">
                    <h4>Errors</h4>
                    <p>{stats['errors']}</p>
                </div>
            </div>
            
            <h3>📱 Phone App Endpoints</h3>
            <div class="endpoint">POST /api/upload_image - Upload image for analysis and sorting</div>
            <div class="endpoint">GET /api/status - Get system status</div>
            <div class="endpoint">POST /api/manual_sort - Manual servo control</div>
            <div class="endpoint">POST /api/test_system - Test all components</div>
            
            <h3>🔧 Setup Instructions</h3>
            <ol>
                <li>Ensure Arduino is connected and running the servo control code</li>
                <li>Verify your .env file contains GOOGLE_API_KEY</li>
                <li>Update ARDUINO_PORT in this file for your system</li>
                <li>Use your phone to send images to: <strong>http://YOUR_COMPUTER_IP:5000/api/upload_image</strong></li>
            </ol>
        </div>
    </body>
    </html>
    '''

# ============================================================================
# MAIN SYSTEM INITIALIZATION
# ============================================================================

def initialize_system():
    """Initialize all system components"""
    global arduino_connection, ml_analyzer
    
    logger.info("Initializing ML E-Waste Sorting System...")
    
    # Initialize ML Analyzer
    try:
        ml_analyzer = MLSortingAnalyzer()
        logger.info("ML Analyzer initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize ML Analyzer: {e}")
        return False
    
    # Initialize Arduino
    try:
        arduino_connection = ArduinoController(ARDUINO_PORT, ARDUINO_BAUD)
        if arduino_connection.connect():
            # Test the servo
            if arduino_connection.test_servo():
                logger.info("Arduino servo system ready")
            else:
                logger.warning("Arduino connected but servo test failed")
        else:
            logger.error("Failed to connect to Arduino")
            return False
    except Exception as e:
        logger.error(f"Arduino initialization error: {e}")
        return False
    
    return True

def main():
    """Main application entry point"""
    logger.info("=" * 70)
    logger.info("ML E-WASTE SORTING SYSTEM STARTING...")
    logger.info("=" * 70)
    
    # Initialize all components
    if not initialize_system():
        logger.error("System initialization failed. Exiting.")
        return 1
    
    try:
        # Get local IP for phone connection
        import socket
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname + ".local")
        except:
            local_ip = socket.gethostbyname(hostname)
        
        logger.info("System initialized successfully!")
        logger.info(f"Web interface: http://{local_ip}:{FLASK_PORT}")
        logger.info(f"Phone endpoint: http://{local_ip}:{FLASK_PORT}/api/upload_image")
        logger.info("System ready for phone camera input...")
        
        # Start Flask server
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    finally:
        # Cleanup
        if arduino_connection:
            arduino_connection.disconnect()
        logger.info("System shutdown complete")
    
    return 0

if __name__ == "__main__":
    exit(main())
