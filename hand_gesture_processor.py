"""
hand_gesture_processor.py
-------------------------
Handles finger-tip-based gesture processing, including detecting touches (thumb to finger),
simulating key presses via pynput, and smoothing positions with a Kalman Filter.

Classes:
    KeyPressHandler
    KalmanFilter3D
    HandGestureProcessor
Functions:
    convert_key(key_str)
"""

import mediapipe as mp
from pynput.keyboard import Key, Controller
import time
from collections import defaultdict
import logging
import numpy as np
import cv2
import threading
import queue
from resources import SPECIAL_KEYS

# ================================
# 1. Special Keys Mapping
# ================================

# Filter out special keys that might be None on the current platform
SPECIAL_KEYS = {k: v for k, v in SPECIAL_KEYS.items() if v is not None}

def convert_key(key_str):
    """
    Converts a string key name to a pynput.keyboard.Key object if it's a special key.
    Supports multi-key combinations separated by '+'.
    Otherwise, returns the string as is for regular keys.

    Args:
        key_str (str): The key name as a string, possibly containing '+' for combinations.

    Returns:
        list or str:
            A list of converted keys if it's a combination, else a single key.
    """
    key_parts = key_str.lower().split('+')
    converted_keys = []
    for part in key_parts:
        part = part.strip()
        if part in SPECIAL_KEYS:
            converted_keys.append(SPECIAL_KEYS[part])
        elif len(part) == 1:
            # Assume single character string is a normal key
            converted_keys.append(part.lower())
        else:
            logging.warning(f"Undefined key '{part}' in combination '{key_str}'. Using as regular key.")
            converted_keys.append(part)
    if len(converted_keys) > 1:
        return converted_keys  # Return list for combinations
    else:
        return converted_keys[0]  # Return single key

class KeyPressHandler(threading.Thread):
    """
    A thread that handles key press and release events using the pynput library.
    Supports single and multiple key presses (e.g., Ctrl+Shift).
    """

    def __init__(self, convert_key_func):
        """
        Initializes the KeyPressHandler thread.

        Args:
            convert_key_func (function):
                Reference to a function that converts string key names to pynput keys.
        """
        super(KeyPressHandler, self).__init__()
        self.daemon = True
        self.queue = queue.Queue()
        self.keyboard_controller = Controller()
        self.convert_key = convert_key_func
        self.active_combinations = set()  # Track active key combos (e.g., Ctrl+Alt)
        self.start()

    def run(self):
        """
        Continuously listens for key press/release instructions from the queue
        and executes them via pynput.
        """
        while True:
            action, key_str = self.queue.get()
            keys = self.convert_key(key_str)
            try:
                if isinstance(keys, list):
                    # Handle multi-key combos
                    if action == 'press':
                        for key in keys:
                            self.keyboard_controller.press(key)
                            logging.debug(f"Key '{key}' pressed.")
                        self.active_combinations.add(tuple(keys))
                    elif action == 'release':
                        for key in reversed(keys):
                            self.keyboard_controller.release(key)
                            logging.debug(f"Key '{key}' released.")
                        self.active_combinations.discard(tuple(keys))
                else:
                    # Single key
                    key = keys
                    if action == 'press':
                        self.keyboard_controller.press(key)
                        logging.debug(f"Key '{key}' pressed.")
                    elif action == 'release':
                        self.keyboard_controller.release(key)
                        logging.debug(f"Key '{key}' released.")
            except Exception as e:
                logging.error(f"Error simulating key '{keys}': {e}")
            finally:
                self.queue.task_done()

    def press_key(self, key_str):
        """
        Simulates pressing a key or key combination down.

        Args:
            key_str (str): The key or combination (e.g., "ctrl+v").
        """
        self.queue.put(('press', key_str))

    def release_key(self, key_str):
        """
        Simulates releasing a key or key combination.

        Args:
            key_str (str): The key or combination (e.g., "ctrl+v").
        """
        self.queue.put(('release', key_str))

class KalmanFilter3D:
    """
    A simple 3D Kalman Filter for smoothing finger tip positions across frames.

    Attributes:
        kf (cv2.KalmanFilter):
            The underlying OpenCV-based KalmanFilter object.
    """

    def __init__(self, process_noise=1e-5, measurement_noise=1e-2):
        """
        Initializes a 3D Kalman Filter.

        Args:
            process_noise (float, optional):
                Covariance of the process noise.
            measurement_noise (float, optional):
                Covariance of the measurement noise.
        """
        self.kf = cv2.KalmanFilter(6, 3)
        self.kf.transitionMatrix = np.array([
            [1, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 1],
            [0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 1]
        ], dtype=np.float32)

        self.kf.measurementMatrix = np.eye(3, 6, dtype=np.float32)
        self.kf.processNoiseCov = np.eye(6, dtype=np.float32) * process_noise
        self.kf.measurementNoiseCov = np.eye(3, dtype=np.float32) * measurement_noise
        self.kf.errorCovPost = np.eye(6, dtype=np.float32)
        self.kf.statePost = np.zeros((6, 1), dtype=np.float32)

    def predict_and_update(self, measurement):
        """
        Runs a prediction step on the Kalman Filter, then corrects
        using the new measurement.

        Args:
            measurement (list or np.array):
                A 3D position measurement [x, y, z].

        Returns:
            np.array: The smoothed state (x, y, z).
        """
        self.kf.predict()
        measurement = np.array(measurement, dtype=np.float32)
        smoothed = self.kf.correct(measurement)
        return smoothed[:3].flatten()

class HandGestureProcessor:
    """
    Processes frames to detect finger touches (thumb to other finger),
    triggering corresponding keypress actions via KeyPressHandler.

    Attributes:
        left_hand_key_map (dict):
            Mapping of finger IDs to key strings (left hand).
        right_hand_key_map (dict):
            Mapping of finger IDs to key strings (right hand).
        finger_thresholds (dict):
            Per-finger ID distance thresholds for "touch" detection.
        press_delay (float):
            Minimum delay between repeats of the same finger press.
        global_last_press_time (collections.defaultdict):
            Tracks the last press time for each key.
        key_pressed_status (collections.defaultdict):
            Tracks whether a key is currently pressed down.
        key_press_handler (KeyPressHandler):
            Thread handling actual key press/release via pynput.
        gesture_event_queue (queue.Queue):
            Queue for non-critical gesture events (not heavily used here).
        action_event_queue (queue.Queue):
            Queue for critical/system-level action events.
        mp_hands (mp.solutions.hands.Hands):
            A MediaPipe Hands instance for hand landmark detection.
        kalman_filters (dict):
            A dictionary of 3D KalmanFilter objects keyed by (hand_label, finger_id).
    """

    def __init__(
        self,
        left_hand_key_map,
        right_hand_key_map,
        finger_thresholds,
        gesture_event_queue,
        action_event_queue,
        press_delay=0.1
    ):
        """
        Initializes the hand gesture processor.

        Args:
            left_hand_key_map (dict):
                Mapping of finger tip IDs to key strings for the left hand.
            right_hand_key_map (dict):
                Mapping of finger tip IDs to key strings for the right hand.
            finger_thresholds (dict):
                Threshold distances for detecting touches.
            gesture_event_queue (queue.Queue):
                Queue for gestural events.
            action_event_queue (queue.Queue):
                Queue for critical/system-level actions (e.g., toggle menu).
            press_delay (float, optional):
                Delay in seconds to prevent rapid repeated presses. Defaults to 0.1.
        """
        self.left_hand_key_map = left_hand_key_map
        self.right_hand_key_map = right_hand_key_map
        self.finger_thresholds = finger_thresholds
        self.press_delay = press_delay
        self.global_last_press_time = defaultdict(float)
        self.key_pressed_status = defaultdict(bool)

        # Create a KeyPressHandler thread
        self.key_press_handler = KeyPressHandler(convert_key_func=convert_key)
        self.gesture_event_queue = gesture_event_queue
        self.action_event_queue = action_event_queue

        # Initialize MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )

        # Initialize a Kalman Filter for each finger in both hands
        self.kalman_filters = {}
        for hand_label, key_map in [('Left', self.left_hand_key_map), ('Right', self.right_hand_key_map)]:
            for finger_id in key_map.keys():
                self.kalman_filters[(hand_label, finger_id)] = KalmanFilter3D(process_noise=1e-4, measurement_noise=1e-2)

    def update_key_maps(self, new_left_map, new_right_map, font, color):
        """
        Updates the key maps for both hands, re-initializing the Kalman Filters.

        Args:
            new_left_map (dict): Updated key map for left hand.
            new_right_map (dict): Updated key map for right hand.
            font (str): The name of the font file (not used here).
            color (str): A hex string representing the new annotation color (not used here).
        """
        self.left_hand_key_map = new_left_map
        self.right_hand_key_map = new_right_map

        # Clear and re-init Kalman Filters for new finger sets
        self.kalman_filters.clear()
        for hand_label, key_map in [('Left', self.left_hand_key_map), ('Right', self.right_hand_key_map)]:
            for finger_id in key_map.keys():
                self.kalman_filters[(hand_label, finger_id)] = KalmanFilter3D(process_noise=1e-4, measurement_noise=1e-2)

        logging.info("HandGestureProcessor key maps updated.")

    def is_touching(self, thumb, finger, threshold, frame_width, frame_height, z_scale=0.9):
        """
        Checks if the thumb is "touching" a given finger tip based on distance.

        Args:
            thumb (NormalizedLandmark): Mediapipe landmark for thumb tip.
            finger (NormalizedLandmark): Mediapipe landmark for any other finger tip.
            threshold (float): Pixel distance threshold for detecting a touch.
            frame_width (int): Width of the frame in pixels.
            frame_height (int): Height of the frame in pixels.
            z_scale (float, optional):
                Scales the Z-axis distance to balance its influence. Defaults to 0.9.

        Returns:
            bool: True if thumb is within the threshold distance to the finger, else False.
        """
        thumb_x = thumb.x * frame_width
        thumb_y = thumb.y * frame_height
        thumb_z = thumb.z * frame_width  # Use frame width for z scaling

        finger_x = finger.x * frame_width
        finger_y = finger.y * frame_height
        finger_z = finger.z * frame_width

        # Weighted Euclidean distance
        distance = np.sqrt(
            ((thumb_x - finger_x) ** 2) +
            ((thumb_y - finger_y) ** 2) +
            (z_scale * (thumb_z - finger_z)) ** 2
        )
        return distance < threshold

    def invert_hex_color(self, hex_color):
        """
        Inverts a given 6-character hex color (e.g., #FFFFFF -> #000000).

        Args:
            hex_color (str): A hex color string (e.g., '#FF0000').

        Returns:
            str: Inverted hex color if valid, otherwise returns original.
        """
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r = 255 - int(hex_color[0:2], 16)
            g = 255 - int(hex_color[2:4], 16)
            b = 255 - int(hex_color[4:6], 16)
            return f'#{r:02X}{g:02X}{b:02X}'
        else:
            return '#' + hex_color  # Return as-is if not valid

    def process_frame(self, frame_rgb, frame_width, frame_height, font, annotation_color):
        """
        Processes a single frame to detect hand(s), identify touches, and trigger key events.

        Args:
            frame_rgb (np.ndarray): The current video frame in RGB format.
            frame_width (int): Width of the frame in pixels.
            frame_height (int): Height of the frame in pixels.
            font (PIL.ImageFont.FreeTypeFont):
                A PIL font for text annotations (not heavily used here).
            annotation_color (str): Hex color for drawing text annotations.

        Returns:
            list: A list of annotations to be drawn (labels, ripples, etc.).
        """
        results = self.hands.process(frame_rgb)
        annotations = []

        # Copy current key maps
        left_hand_key_map = self.left_hand_key_map.copy()
        right_hand_key_map = self.right_hand_key_map.copy()

        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                hand_label = handedness.classification[0].label  # 'Left' or 'Right'
                key_map = left_hand_key_map if hand_label == "Left" else right_hand_key_map
                if not key_map:
                    continue

                thumb_tip = hand_landmarks.landmark[4]

                # Check each mapped finger for possible touch
                for finger_tip_id, key_str in key_map.items():
                    finger_tip = hand_landmarks.landmark[finger_tip_id]
                    threshold = self.finger_thresholds.get(finger_tip_id, 0.07) * frame_width

                    # Determine if thumb is touching this finger
                    touching = self.is_touching(
                        thumb_tip, finger_tip, threshold, frame_width, frame_height, z_scale=0.5
                    )
                    current_time = time.time()

                    # If touching and enough delay has passed, press the key
                    if touching and (current_time - self.global_last_press_time[key_str] >= self.press_delay):
                        if not self.key_pressed_status[key_str]:
                            self.key_press_handler.press_key(key_str)
                            self.key_pressed_status[key_str] = True
                            self.global_last_press_time[key_str] = current_time

                            # Add a ripple effect annotation on the thumb tip
                            annotations.append(('ripple', (
                                int(thumb_tip.x * frame_width),
                                int(thumb_tip.y * frame_height)
                            )))
                            logging.info(f"Touch detected on '{key_str}' key.")

                    # If not touching but currently pressed, release the key
                    elif not touching and self.key_pressed_status[key_str]:
                        self.key_press_handler.release_key(key_str)
                        self.key_pressed_status[key_str] = False

                    # Apply Kalman Filter for smoother finger tracking
                    kalman = self.kalman_filters.get((hand_label, finger_tip_id))
                    if kalman:
                        raw_x = finger_tip.x * frame_width
                        raw_y = finger_tip.y * frame_height
                        raw_z = finger_tip.z * frame_width
                        smoothed = kalman.predict_and_update([raw_x, raw_y, raw_z])
                        smoothed_x, smoothed_y, smoothed_z = smoothed
                        # Clip to frame boundaries
                        smoothed_x = np.clip(smoothed_x, 0, frame_width - 1)
                        smoothed_y = np.clip(smoothed_y, 0, frame_height - 1)
                    else:
                        smoothed_x = finger_tip.x * frame_width
                        smoothed_y = finger_tip.y * frame_height
                        smoothed_z = finger_tip.z * frame_width

                    # Add a text label annotation near the finger tip
                    annotations.append(('label', (
                        int(smoothed_x),
                        int(smoothed_y),
                        smoothed_z,
                        key_str,
                        annotation_color if not self.key_pressed_status[key_str]
                        else self.invert_hex_color(annotation_color)
                    )))

        return annotations