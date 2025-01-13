"""
camera_manager.py
-----------------
Manages the camera feed, performs gesture recognition using MediaPipe,
and relays recognized gestures or events to other parts of the system.

Classes:
    CameraManager
"""

import cv2
import threading
import queue
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python.vision import (
    GestureRecognizerOptions,
    GestureRecognizer,
    RunningMode
)
from mediapipe.tasks.python import BaseOptions
import logging
from PIL import Image, ImageDraw, ImageFont
from resources import FONT_CAMERA, MODEL_PATH
import time
import os
import sys

class CameraManager:
    """
    Manages the camera feed and gesture recognition pipeline using MediaPipe.

    Attributes:
        processor (HandGestureProcessor):
            The object responsible for processing frames to detect finger touches.
        gesture_event_queue (queue.Queue):
            A queue for enqueueing general (non-critical) gesture events.
        action_event_queue (queue.Queue):
            A queue for enqueueing critical or system-level actions.
        camera_width (int): 
            Desired width of the camera feed.
        camera_height (int):
            Desired height of the camera feed.
        paused (bool):
            Flag indicating whether the camera processing is paused.
        frame_queue (queue.Queue):
            Stores the most recent frame(s) for retrieval by the UI.
        stop_event (threading.Event):
            Signals when to stop the camera feed thread.
        ripples (list):
            Stores data about ripple effects to be drawn on the screen.
        max_ripples (int):
            Maximum number of simultaneous ripple effects allowed.
        annotation_color (str):
            Hex color code for text annotations.
        scale_factor (float):
            Scaling factor for dynamically resizing text annotations.
        font_path (str):
            Path to the TrueType (TTF) font file used for annotations.
        font (PIL.ImageFont.FreeTypeFont):
            Loaded font object.
        gesture_recognizer (mediapipe.tasks.python.vision.GestureRecognizer):
            MediaPipe Gesture Recognizer for detecting hand gestures in frames.
        last_left_gesture (str):
            Tracks the last recognized gesture for the left hand.
        last_right_gesture (str):
            Tracks the last recognized gesture for the right hand.
    """

    def __init__(
        self,
        processor,
        gesture_event_queue,
        action_event_queue,
        camera_width=640,
        camera_height=480,
        font_path=FONT_CAMERA,
        font_size=20,
        annotation_color="#FF0000"
    ):
        """
        Initializes a CameraManager instance.

        Args:
            processor (HandGestureProcessor):
                Responsible for processing frames (e.g., detecting finger touches).
            gesture_event_queue (queue.Queue):
                Queue for enqueuing general gesture events.
            action_event_queue (queue.Queue):
                Queue for enqueuing critical/system-level action events.
            camera_width (int, optional):
                Desired camera width. Defaults to 640.
            camera_height (int, optional):
                Desired camera height. Defaults to 480.
            font_path (str, optional):
                Path to a TTF font file. Defaults to FONT_CAMERA from resources.
            font_size (int, optional):
                Font size for text annotations. Defaults to 20.
            annotation_color (str, optional):
                Hex color code for text annotations. Defaults to "#FF0000".
        """
        self.processor = processor
        self.gesture_event_queue = gesture_event_queue
        self.action_event_queue = action_event_queue
        self.camera_width = camera_width
        self.camera_height = camera_height
        self.paused = False
        self.frame_queue = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.ripples = []
        self.max_ripples = 10
        self.annotation_color = annotation_color
        self.scale_factor = 1.0
        self.font_path = font_path

        # Initialize Video Capture with AVFoundation backend for macOS
        self.cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
        if not self.cap.isOpened():
            logging.error("Failed to open the camera.")
            raise ValueError("Camera could not be opened.")
        else:
            logging.info("Camera successfully opened.")

        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)

        # MediaPipe convenience objects
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_hands = mp.solutions.hands

        # Load the specified font or a default font if unavailable
        try:
            self.font = ImageFont.truetype(font_path, font_size)
            logging.debug(f"Loaded font from {font_path} with size {font_size}.")
        except Exception as e:
            logging.error(f"Error loading font {font_path}: {e}")
            self.font = ImageFont.load_default()
            logging.debug("Loaded default font.")

        # Initialize Gesture Recognizer
        base_options = BaseOptions(model_asset_path=MODEL_PATH)
        gesture_recognizer_options = GestureRecognizerOptions(
            base_options=base_options,
            running_mode=RunningMode.VIDEO,
            num_hands=2,  # Adjust as needed
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )

        try:
            self.gesture_recognizer = GestureRecognizer.create_from_options(gesture_recognizer_options)
            logging.info("Gesture Recognizer initialized.")
        except Exception as e:
            logging.error(f"Failed to initialize Gesture Recognizer: {e}")
            raise e

        # Track last recognized gesture for each hand
        self.last_left_gesture = None
        self.last_right_gesture = None

    def start(self):
        """
        Starts the camera capture and processing in a separate thread.
        """
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        logging.info("Camera thread started.")

    def pause(self):
        """
        Pauses the camera processing (no frames are processed).
        """
        self.paused = True
        logging.info("Camera processing paused.")

    def resume(self):
        """
        Resumes the camera processing (frames are processed again).
        """
        self.paused = False
        logging.info("Camera processing resumed.")

    def run(self):
        """
        Continuously captures frames from the camera, performs gesture recognition,
        and processes frames through the HandGestureProcessor.
        """
        while not self.stop_event.is_set():
            success, frame = self.cap.read()
            if not success:
                logging.warning("Failed to read frame from camera.")
                continue

            # Flip the frame horizontally to create a mirror effect
            frame = cv2.flip(frame, 1)
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Resize the frame for gesture recognition to improve performance
            reduced_width, reduced_height = 320, 240
            frame_resized = cv2.resize(frame_rgb, (reduced_width, reduced_height), interpolation=cv2.INTER_AREA)
            frame_height, frame_width = frame_rgb.shape[:2]

            # Convert the frame to PIL for drawing annotations
            frame_pil = Image.fromarray(frame_rgb)
            draw = ImageDraw.Draw(frame_pil)

            # Convert to MediaPipe Image
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_resized)

            # Generate a timestamp in milliseconds
            frame_timestamp_ms = int(time.time() * 1000)

            # Recognize gestures using recognize_for_video
            try:
                result = self.gesture_recognizer.recognize_for_video(mp_image, frame_timestamp_ms)
                if result.gestures and result.handedness:
                    for i, gesture_list in enumerate(result.gestures):
                        # Determine the hand type ("left" or "right")
                        hand_type_categories = result.handedness[i]
                        if hand_type_categories and len(hand_type_categories) > 0:
                            hand_type = hand_type_categories[0].category_name.lower()
                        else:
                            hand_type = "unknown"

                        # Process each recognized gesture for the current hand
                        categories = gesture_list
                        for category in categories:
                            if hasattr(category, 'category_name') and hasattr(category, 'score'):
                                gesture_name = category.category_name
                                score = category.score
                                logging.info(f"Detected gesture: {gesture_name} ({hand_type}) with score {score:.2f}")

                                # Use match-case (Python 3.10+) for gesture-based actions
                                match (gesture_name, hand_type):
                                    case ('Closed_Fist', 'right'):
                                        if self.last_right_gesture != 'Closed_Fist':
                                            self.toggle_pause_state()
                                        self.last_right_gesture = 'Closed_Fist'
                                    case ('Closed_Fist', 'left'):
                                        if self.last_left_gesture != 'Closed_Fist':
                                            self.toggle_pause_state()
                                        self.last_left_gesture = 'Closed_Fist'
                                    case ('Pointing_Up', 'right'):
                                        if self.last_right_gesture != 'Pointing_Up':
                                            self.toggle_preset_sets()
                                        self.last_right_gesture = 'Pointing_Up'
                                    case ('Pointing_Up', 'left'):
                                        if self.last_left_gesture != 'Pointing_Up':
                                            self.toggle_menu()
                                        self.last_left_gesture = 'Pointing_Up'
                                    case (_, 'right'):
                                        # Update right gesture
                                        self.last_right_gesture = gesture_name
                                    case (_, 'left'):
                                        # Update left gesture
                                        self.last_left_gesture = gesture_name
                                    case _:
                                        pass
                            else:
                                logging.warning("Gesture category does not have 'category_name' or 'score' attributes.")

            except Exception as e:
                logging.error(f"Error during gesture recognition: {e}")

            # Only process annotations if not paused
            if not self.paused:
                # Obtain annotations from the processor
                annotations = self.processor.process_frame(
                    frame_rgb,
                    frame_rgb.shape[1],
                    frame_rgb.shape[0],
                    self.font,
                    self.annotation_color
                )

                # Create an overlay image for ripple effects
                overlay = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)

                # Handle any annotations (ripple effects, text labels, etc.)
                self.handle_annotations(annotations, overlay_draw, frame_width, frame_height, draw)

                # Composite the overlay with the base frame
                frame_pil = Image.alpha_composite(frame_pil.convert('RGBA'), overlay)

            # Convert final frame back to RGB and enqueue
            final_frame = frame_pil.convert('RGB')
            self.enqueue_frame(final_frame)

    def toggle_pause_state(self):
        """
        Toggles between paused and resumed states for camera processing.
        """
        if self.paused:
            self.resume()
        else:
            self.pause()
        logging.info(f"Toggled pause state to {'paused' if self.paused else 'resumed'}.")

    def toggle_menu(self):
        """
        Enqueues a 'toggle_menu' action to the action_event_queue (UI toggles the menu).
        """
        self.action_event_queue.put('toggle_menu')
        logging.info("Enqueued 'toggle_menu' event.")

    def toggle_preset_sets(self):
        """
        Enqueues a 'toggle_preset' action to the action_event_queue (UI switches to the next preset).
        """
        self.action_event_queue.put('toggle_preset')
        logging.info("Enqueued 'toggle_preset' event to switch keyboard sets.")

    def enqueue_frame(self, frame_pil):
        """
        Places the latest processed frame in a thread-safe queue for retrieval by the UI.
        """
        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                pass
        self.frame_queue.put(frame_pil)

    def get_latest_frame(self):
        """
        Retrieves the most recent frame if available, else returns None.

        Returns:
            PIL.Image or None: The latest frame from the queue or None if no frame is available.
        """
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None

    def handle_annotations(self, annotations, overlay_draw, frame_width, frame_height, draw):
        """
        Handles drawing annotations (e.g., text labels, ripple effects) onto the frame.

        Args:
            annotations (list): A list of annotation data (tuples) from the processor.
            overlay_draw (PIL.ImageDraw.Draw):
                A drawing interface for a transparent overlay for ripple effects.
            frame_width (int): The width of the current frame in pixels.
            frame_height (int): The height of the current frame in pixels.
            draw (PIL.ImageDraw.Draw):
                A drawing interface for text directly on the camera frame.
        """
        base_font_size = 20  # Base font size for scaling

        for ann_type, data in annotations:
            if ann_type == 'ripple':
                # Handle ripple effect annotations
                x, y, z = data[:3] if len(data) == 3 else (*data[:2], 0)
                base_radius = 5
                scale_factor = max(0.5, min(2.0, 1.0 - z))
                scaled_radius = base_radius * scale_factor

                # Create a new ripple if below the max limit
                if len(self.ripples) < self.max_ripples:
                    self.ripples.append({
                        'x': x,
                        'y': y,
                        'radius': scaled_radius,
                        'opacity': 255,
                        'thickness': 2
                    })
            elif ann_type == 'label':
                # Finger label or key label
                x, y, z, key, color = data
                # Convert hex string to RGB
                text_color = (
                    int(color[1:3], 16),
                    int(color[3:5], 16),
                    int(color[5:7], 16)
                ) if isinstance(color, str) and color.startswith("#") else (0, 0, 0)

                # Dynamic scaling based on Z distance
                scale_factor = max(0.5, min(2.0, 0.2 + 7 * (abs(z) / frame_width)))
                scaled_font_size = int(base_font_size * scale_factor)

                try:
                    scaled_font = ImageFont.truetype(self.font_path, scaled_font_size)
                except Exception as e:
                    logging.warning(f"Failed to load font size {scaled_font_size}: {e}")
                    scaled_font = ImageFont.load_default()

                # Draw the text label
                draw.text((x, y - 30), key, font=scaled_font, fill=text_color)

        # Update and draw each ripple
        for ripple in list(self.ripples):
            ripple_color = (255, 255 - ripple['opacity'], 255 - ripple['opacity'], 255)
            overlay_draw.ellipse([
                (ripple['x'] - ripple['radius'], ripple['y'] - ripple['radius']),
                (ripple['x'] + ripple['radius'], ripple['y'] + ripple['radius'])
            ], outline=ripple_color, width=ripple['thickness'])

            # Increase radius, decrease opacity, reduce thickness
            ripple['radius'] += 6
            ripple['opacity'] = max(0, ripple['opacity'] - 45)
            ripple['thickness'] = max(1, ripple['thickness'] - 1)
            if ripple['opacity'] <= 0:
                self.ripples.remove(ripple)

    def update_font_color(self, left_map, right_map, font, color):
        """
        Dynamically updates the annotation font and color.

        Args:
            left_map (dict): Updated left-hand key mapping (not used here directly).
            right_map (dict): Updated right-hand key mapping (not used here directly).
            font (str): The name of the font file (without extension).
            color (str): A hex string representing the new color for annotations.
        """
        # Update font path
        self.font_path = os.path.join(os.path.dirname(sys.argv[0]), 'fonts', font + ".ttf")
        logging.info(f"Updated font to: {font}")

        # Update annotation color
        self.annotation_color = color
        logging.info(f"Updated annotation color to: {color}")

    def stop(self):
        """
        Signals the camera thread to stop and releases resources.
        """
        self.stop_event.set()
        self.thread.join()
        self.cap.release()
        self.gesture_recognizer.close()
        logging.info("Camera stopped and resources released.")