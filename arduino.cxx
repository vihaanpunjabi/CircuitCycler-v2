/*
 * ============================================================================
 * ARDUINO DUAL SERVO CONTROL FOR ML SORTING SYSTEM
 * ============================================================================
 * Controls TWO servos based on ML analysis results from Python
 * Servo 1 (Pin 12): Primary sorting servo
 * Servo 2 (Pin 13): Secondary servo or conveyor control
 * ============================================================================
 */

#include <Servo.h>

// ============================================================================
// CONFIGURATION
// ============================================================================

// Pin definitions
const int SERVO1_PIN = 12;       // Primary sorting servo
const int SERVO2_PIN = 13;       // Secondary servo
const int LED_PIN = LED_BUILTIN; // Built-in LED (pin 13 conflict - using software control)

// Servo positions (adjust these for your physical setup)
const int LEFT_POSITION = 0;     // 0 degrees - for "safe to shred" items
const int RIGHT_POSITION = 180;  // 180 degrees - for "special handling" items  
const int CENTER_POSITION = 90;  // 90 degrees - neutral/home position

// Secondary servo positions (customize based on your needs)
const int SERVO2_ACTIVE = 90;    // Active position for servo 2
const int SERVO2_IDLE = 0;       // Idle position for servo 2

// Timing settings
const int MOVE_TIME = 800;        // Time to complete movement (milliseconds)
const int HOLD_TIME = 600;       // Time to hold position (milliseconds)
const int STEP_DELAY = 15;       // Delay between servo steps for smooth movement

// Serial settings
const long BAUD_RATE = 115200;
const int SERIAL_TIMEOUT = 2000;

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

Servo servo1;                    // Primary sorting servo
Servo servo2;                    // Secondary servo
String inputBuffer = "";         // Buffer for serial input
int currentPosition1 = CENTER_POSITION;  // Track servo1 position
int currentPosition2 = SERVO2_IDLE;      // Track servo2 position
bool systemReady = false;        // System ready flag

// Statistics
unsigned long totalMoves = 0;
unsigned long leftMoves = 0;
unsigned long rightMoves = 0;
unsigned long startTime = 0;

// ============================================================================
// SETUP FUNCTION
// ============================================================================

void setup() {
  // Initialize serial communication
  Serial.begin(BAUD_RATE);
  Serial.setTimeout(SERIAL_TIMEOUT);
  
  // Startup sequence
  performStartupSequence();
  
  // Initialize servos
  if (initializeServos()) {
    systemReady = true;
    startTime = millis();
    
    // Send startup message
    Serial.println("============================================");
    Serial.println("Arduino Dual Servo ML Sorting Controller");
    Serial.println("Servo 1 (Pin 12): Primary sorting");
    Serial.println("Servo 2 (Pin 13): Secondary control");
    Serial.println("Commands: LEFT, RIGHT, CENTER, TEST, STATUS");
    Serial.println("============================================");
    Serial.println("System initialized successfully");
    Serial.println("READY");
  } else {
    Serial.println("ERROR: Servo initialization failed!");
    performErrorSequence();
  }
  
  // Reserve string space for efficiency
  inputBuffer.reserve(100);
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // Process serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    processCommand(command);
  }
  
  // Small delay to prevent overwhelming the processor
  delay(10);
}

// ============================================================================
// SERVO CONTROL FUNCTIONS
// ============================================================================

bool initializeServos() {
  Serial.println("Initializing servos...");
  
  try {
    // Attach servos to pins
    servo1.attach(SERVO1_PIN);
    servo2.attach(SERVO2_PIN);
    delay(500);  // Allow servos to initialize
    
    // Move to initial positions
    servo1.write(CENTER_POSITION);
    servo2.write(SERVO2_IDLE);
    currentPosition1 = CENTER_POSITION;
    currentPosition2 = SERVO2_IDLE;
    delay(1000);
    
    Serial.println("Both servos initialized and positioned");
    return true;
    
  } catch (...) {
    Serial.println("ERROR: Servo initialization failed");
    return false;
  }
}

bool executeSortingMovement(String direction) {
  if (!systemReady) {
    Serial.println("ERROR: System not ready");
    return false;
  }
  
  direction.toUpperCase();
  direction.trim();
  
  int targetPosition = CENTER_POSITION;
  
  // Determine target position
  if (direction == "LEFT") {
    targetPosition = LEFT_POSITION;
  } else if (direction == "RIGHT") {
    targetPosition = RIGHT_POSITION;
  } else if (direction == "CENTER") {
    targetPosition = CENTER_POSITION;
  } else {
    Serial.println("ERROR: Invalid direction - " + direction);
    return false;
  }
  
  Serial.print("Executing sorting movement: ");
  Serial.println(direction);
  
  try {
    // Activate secondary servo (optional - for item feeding/conveyor)
    if (direction != "CENTER") {
      servo2.write(SERVO2_ACTIVE);
      delay(200);
    }
    
    // Move primary sorting servo smoothly
    moveServoSmoothly(servo1, currentPosition1, targetPosition);
    currentPosition1 = targetPosition;
    
    // Hold position
    delay(HOLD_TIME);
    
    // Return primary servo to center (unless already there)
    if (targetPosition != CENTER_POSITION) {
      Serial.println("Returning to center position");
      moveServoSmoothly(servo1, currentPosition1, CENTER_POSITION);
      currentPosition1 = CENTER_POSITION;
    }
    
    // Return secondary servo to idle
    servo2.write(SERVO2_IDLE);
    currentPosition2 = SERVO2_IDLE;
    
    // Update statistics
    totalMoves++;
    if (direction == "LEFT") {
      leftMoves++;
    } else if (direction == "RIGHT") {
      rightMoves++;
    }
    
    Serial.println("Sorting movement completed successfully");
    return true;
    
  } catch (...) {
    Serial.println("ERROR: Servo movement failed");
    return false;
  }
}

void moveServoSmoothly(Servo &servo, int fromPos, int toPos) {
  if (fromPos == toPos) return;
  
  int step = (toPos > fromPos) ? 2 : -2;
  
  for (int pos = fromPos; 
       (step > 0 ? pos <= toPos : pos >= toPos); 
       pos += step) {
    servo.write(pos);
    delay(STEP_DELAY);
  }
  
  // Ensure exact final position
  servo.write(toPos);
  delay(MOVE_TIME);
}

// ============================================================================
// COMMAND PROCESSING
// ============================================================================

void processCommand(String command) {
  command.toUpperCase();
  command.trim();
  
  Serial.println("Received command: " + command);
  
  if (command == "LEFT") {
    if (executeSortingMovement("LEFT")) {
      Serial.println("LEFT movement completed");
    } else {
      Serial.println("ERROR: LEFT movement failed");
    }
    
  } else if (command == "RIGHT") {
    if (executeSortingMovement("RIGHT")) {
      Serial.println("RIGHT movement completed");
    } else {
      Serial.println("ERROR: RIGHT movement failed");
    }
    
  } else if (command == "CENTER") {
    if (executeSortingMovement("CENTER")) {
      Serial.println("CENTER movement completed");
    } else {
      Serial.println("ERROR: CENTER movement failed");
    }
    
  } else if (command == "TEST") {
    runCompleteTest();
    
  } else if (command == "STATUS") {
    printSystemStatus();
    
  } else {
    Serial.println("ERROR: Unknown command - " + command);
    Serial.println("Valid commands: LEFT, RIGHT, CENTER, TEST, STATUS");
  }
  
  // Always send ready signal after processing
  Serial.println("READY");
}

void runCompleteTest() {
  Serial.println("Starting complete system test...");
  
  // Test sequence: CENTER -> LEFT -> CENTER -> RIGHT -> CENTER
  String testSequence[] = {"CENTER", "LEFT", "CENTER", "RIGHT", "CENTER"};
  
  for (int i = 0; i < 5; i++) {
    Serial.println("Testing position: " + testSequence[i]);
    executeSortingMovement(testSequence[i]);
    delay(500);
  }
  
  Serial.println("Complete system test finished");
}

void printSystemStatus() {
  unsigned long uptime = millis() - startTime;
  
  Serial.println("=== ARDUINO SYSTEM STATUS ===");
  Serial.println("System Ready: " + String(systemReady ? "YES" : "NO"));
  Serial.println("Uptime: " + String(uptime / 1000) + " seconds");
  Serial.println("Total Movements: " + String(totalMoves));
  Serial.println("Left Movements: " + String(leftMoves));
  Serial.println("Right Movements: " + String(rightMoves));
  Serial.println("Servo 1 Position: " + String(currentPosition1));
  Serial.println("Servo 2 Position: " + String(currentPosition2));
  Serial.println("Free Memory: " + String(freeMemory()) + " bytes");
  Serial.println("============================");
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

void performStartupSequence() {
  // Flash built-in LED to indicate startup
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(200);
    digitalWrite(LED_BUILTIN, LOW);
    delay(200);
  }
}

void performErrorSequence() {
  // Flash error pattern
  for (int i = 0; i < 10; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);
  }
}

int freeMemory() {
  char top;
  return &top - reinterpret_cast<char*>(malloc(4));
}
