"""
main.py
-------
Entry point for the application. Initializes the PyQt5 UI, loads presets,
starts the CameraManager and HandGestureProcessor, and launches the main window.

Functions:
    load_presets() -> dict
    save_presets(presets: dict)
    main()
"""

import sys
import time
import logging
from PyQt5.QtWidgets import QApplication
from hand_gesture_processor import HandGestureProcessor
from camera_manager import CameraManager
import queue
import json
import os
from PyQt5.QtCore import Qt
from resources import DEFAULT_PRESETS

PRESETS_FILE = 'presets.json'

def load_presets():
    """
    Loads presets from a JSON file or initializes them to DEFAULT_PRESETS if not found.
    Ensures the correct data structure is returned (e.g., integer keys for finger IDs).

    Returns:
        dict: A dictionary of presets keyed by preset name.
    """
    if not os.path.exists(PRESETS_FILE):
        save_presets(DEFAULT_PRESETS)
        return DEFAULT_PRESETS
    else:
        with open(PRESETS_FILE, 'r') as f:
            presets = json.load(f)
        # Convert keys back to integers and ensure font & color are present
        for preset_name, key_maps in presets.items():
            left_map = {int(k): v for k, v in key_maps[0].items()}
            right_map = {int(k): v for k, v in key_maps[1].items()}
            selected_font = key_maps[2]
            selected_color = key_maps[3]
            presets[preset_name] = (left_map, right_map, selected_font, selected_color)
        return presets

def save_presets(presets):
    """
    Saves the given presets dictionary to a JSON file, converting finger ID keys to strings.

    Args:
        presets (dict): A dictionary of presets keyed by preset name.
    """
    serializable_presets = {}
    for preset_name, key_maps in presets.items():
        serializable_presets[preset_name] = (
            {str(k): v for k, v in key_maps[0].items()},
            {str(k): v for k, v in key_maps[1].items()},
            key_maps[2],  # font
            key_maps[3]   # color
        )
    with open(PRESETS_FILE, 'w') as f:
        json.dump(serializable_presets, f, indent=4)

def main():
    """
    The main entry point of the application. Sets up the QApplication,
    initializes the gesture processor and camera manager, and starts the UI.
    """
    app = QApplication(sys.argv)

    # Must be called after QApplication is created
    from resources import init_icons
    init_icons()

    # Enable High DPI scaling if supported
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Initialize separate event queues
    action_event_queue = queue.Queue()
    gesture_event_queue = queue.Queue()

    # Load or initialize presets
    presets = load_presets()
    default_preset_name = "Gaming"  # Choose a default preset name
    left_hand_key_map, right_hand_key_map, selected_font, selected_color = presets[default_preset_name]
    finger_thresholds = {8: 0.06, 12: 0.06, 16: 0.06, 20: 0.07}  # Example thresholds

    # Create the processor and camera manager
    processor = HandGestureProcessor(
        left_hand_key_map.copy(),
        right_hand_key_map.copy(),
        finger_thresholds,
        gesture_event_queue,
        action_event_queue
    )
    camera_manager = CameraManager(
        processor,
        gesture_event_queue,
        action_event_queue,
        camera_width=640,
        camera_height=480,
        font_path=os.path.join(os.path.dirname(sys.argv[0]), 'fonts', selected_font + ".ttf"),
        font_size=20,
        annotation_color=selected_color
    )
    camera_manager.start()

    # Attempt to retrieve an initial frame to determine actual camera size
    start_time = time.time()
    initial_frame = None
    while initial_frame is None and (time.time() - start_time) < 5:
        initial_frame = camera_manager.get_latest_frame()
        time.sleep(0.1)

    if initial_frame is not None:
        actual_camera_width, actual_camera_height = initial_frame.size
    else:
        logging.warning("No initial frame retrieved. Using default size.")
        actual_camera_width, actual_camera_height = 640, 480

    # Import and instantiate the main window from ui.py
    from ui import MainWindow
    window = MainWindow(
        camera_manager=camera_manager,
        gesture_event_queue=gesture_event_queue,
        action_event_queue=action_event_queue,
        left_hand_key_map=left_hand_key_map.copy(),
        right_hand_key_map=right_hand_key_map.copy(),
        camera_width=actual_camera_width,
        camera_height=actual_camera_height,
        presets=presets,
        current_preset_name=default_preset_name
    )

    # Connect signals for preset changes
    window.preset_changed.connect(processor.update_key_maps)
    window.preset_changed.connect(lambda left, right, font, color: camera_manager.update_font_color(left, right, font, color))

    window.show()
    exit_code = app.exec_()

    # Save presets before exit
    save_presets(presets)

    # Stop the camera before shutting down
    camera_manager.stop()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()