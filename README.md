# iHand – Hand Gesture-Controlled Input System

iHand is a real-time hand gesture-controlled input system built with Python, Mediapipe, PyQt5, and pynput. The application enables touchless computer interaction and includes a dedicated media mode for controlling system volume via natural finger gestures.

## Demo

Watch the iHand demo in action:  
[![iHand Demo](https://img.youtube.com/vi/J4mUZ11HFb8/maxresdefault.jpg)](https://www.youtube.com/watch?v=J4mUZ11HFb8)

## Features

- **Touchless Interaction:**  
  Convert intuitive hand gestures into computer inputs, eliminating the need for physical contact.
- **Dynamic Media Control:**  
  In Media mode, adjust system volume by touching both index fingers to your thumbs and then moving them apart (to increase volume) or together (to decrease volume).
- **Robust Multithreaded Architecture:**  
  Seamlessly integrates live video capture, real-time gesture recognition, and a responsive GUI.
- **Configurable Presets:**  
  Customize gesture-to-action mappings and UI settings through multiple presets (e.g., Gaming, Media).

---

## Technologies

- **Python 3.x**
- **Mediapipe:** Real-time hand tracking and gesture recognition.
- **PyQt5:** GUI development.
- **pynput:** Simulating keyboard events.
- **Pillow:** Image processing and annotation.
- **NumPy & OpenCV:** Supporting image and video processing.

---

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourusername/iHand.git
   cd iHand

2.	**Create and Activate a Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate   # On Windows: venv\Scripts\activate

3.	**Install Dependencies:**
    ```bash
    pip install -r requirements.txt

Ensure that requirements.txt includes:
	•	mediapipe
	•	pyqt5
	•	pynput
	•	pillow
	•	numpy
	•	opencv-python

## Usage

1.	**Run the Application:**
    ```bash
    python main.py

2.	**Select a Preset:**
Use the UI to choose a preset (e.g., Gaming, Media).

3.	**Control Inputs:**
Use hand gestures to simulate key presses and other interactions.

4.	**Media Mode (Volume Control):**
- 	Initiate Gesture: When the Media preset is active, touch both index fingers to your thumbs.
- 	Increase Volume: Spread your index fingers apart.
- Decrease Volume: Bring your index fingers closer together.

## Project Structure
   
    iHand/
    ├── camera_manager.py        # Handles live video capture, gesture recognition, and action processing
    ├── hand_gesture_processor.py # Processes hand gestures and simulates key events via pynput
    ├── main.py                  # Application entry point
    ├── ui.py                    # PyQt5-based graphical user interface
    ├── resources.py             # Resource paths, fonts, and icon initialization
    ├── fonts/                   # Custom fonts
    ├── icons/                   # GUI icons
    ├── models/                  # Mediapipe task models (e.g., gesture_recognizer.task)
    ├── requirements.txt         # Project dependencies
    └── README.md                # This file

## Contributing

Contributions are welcome! Please fork the repository and open a pull request with enhancements, bug fixes, or new features. For major changes, open an issue first to discuss your ideas.

## License

This project is licensed under the MIT License.

## Acknowledgments

- Mediapipe for cutting-edge hand tracking and gesture recognition.
-	PyQt5 for creating a responsive and intuitive GUI.
-	pynput for facilitating media key simulations.

