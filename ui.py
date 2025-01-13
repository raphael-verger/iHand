"""
ui.py
-----
Implements the PyQt5 UI layer, including the main application window,
menu panel for customization, camera feed display, and interactions.

Classes:
    CenteredComboBox
    MainWindow
"""

import logging
import os
from PyQt5.QtCore import Qt, QTimer, QRect, pyqtSlot, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QImage, QIcon, QColor, QFont, QFontDatabase
import queue
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton,
    QLabel, QLineEdit, QGridLayout, QSizePolicy, QColorDialog, QMessageBox
)

from resources import (
    MENU_WIDTH, COLOR_PALETTE_LIGHT,
    LABEL_FONT, ENTRY_FONT, BUTTON_FONT,
    GEAR_ICON, PAUSE_ICON, PLAY_ICON
)

# Custom QComboBox that centers text
from PyQt5.QtWidgets import QComboBox

class CenteredComboBox(QComboBox):
    """
    A custom QComboBox that centers the text and ignores keyboard events.
    Useful for a neat, uniform design in the UI.
    """
    def __init__(self, parent=None):
        super(CenteredComboBox, self).__init__(parent)
        self.setEditable(True)
        self.lineEdit().setAlignment(Qt.AlignCenter)
        self.lineEdit().setReadOnly(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def mousePressEvent(self, event):
        """
        Override to ensure the combo box opens on click anywhere.
        """
        if event.button() == Qt.LeftButton:
            self.showPopup()
        super(CenteredComboBox, self).mousePressEvent(event)

    def keyPressEvent(self, event):
        """
        Ignore keyboard events to prevent text editing.
        """
        event.ignore()

class MainWindow(QMainWindow):
    """
    The main application window containing:
    - Camera feed display
    - Side menu panel for customizing key maps
    - Preset selector, pause button, settings button
    """

    # Signal emitted when a preset changes,
    # carrying new left/right maps, font, and color
    preset_changed = pyqtSignal(dict, dict, str, str)

    def __init__(
        self,
        camera_manager,
        gesture_event_queue,
        action_event_queue,
        left_hand_key_map,
        right_hand_key_map,
        camera_width,
        camera_height,
        presets,
        current_preset_name,
        parent=None
    ):
        """
        Initializes the main application window.

        Args:
            camera_manager (CameraManager):
                The manager responsible for capturing and processing camera frames.
            gesture_event_queue (queue.Queue):
                A queue for less critical gesture events (unused in UI).
            action_event_queue (queue.Queue):
                A queue for critical or system-level actions.
            left_hand_key_map (dict):
                Initial mapping of left-hand finger IDs to key strings.
            right_hand_key_map (dict):
                Initial mapping of right-hand finger IDs to key strings.
            camera_width (int):
                The actual width of the camera feed (determined at runtime).
            camera_height (int):
                The actual height of the camera feed (determined at runtime).
            presets (dict):
                Dictionary of available presets, each containing left_map, right_map, font, color.
            current_preset_name (str):
                The name of the preset to load initially.
            parent (QWidget, optional):
                The parent widget. Defaults to None.
        """
        super(MainWindow, self).__init__(parent)
        self.camera_manager = camera_manager
        self.gesture_event_queue = gesture_event_queue
        self.action_event_queue = action_event_queue
        self.left_hand_key_map = left_hand_key_map
        self.right_hand_key_map = right_hand_key_map
        self.presets = presets
        self.current_preset_name = current_preset_name
        self.menu_visible = True
        self.pause_state = False
        self.camera_width = camera_width
        self.camera_height = camera_height
        self.color_palette = COLOR_PALETTE_LIGHT

        self.setWindowTitle("iHand")

        # Main layout setup
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Camera feed frame
        self.camera_frame = self.create_camera_feed_frame()
        main_layout.addWidget(self.camera_frame, 0)

        # Menu frame
        self.menu_frame = self.create_menu_frame()
        main_layout.addWidget(self.menu_frame, 1)

        # Update UI from the loaded preset
        self.update_font_and_color_from_preset()

        # Window size constraints
        self.resize(self.camera_width + MENU_WIDTH, self.camera_height)
        self.setMinimumSize(self.camera_width + MENU_WIDTH, self.camera_height)
        self.setMaximumSize(self.camera_width + MENU_WIDTH, self.camera_height)

        # Timer to update camera feed
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_camera_feed)
        self.update_timer.start(75)  # ~13 FPS update

        # Apply custom styles
        self.apply_styles()

        # Keep track of all preset names in a list
        self.preset_names = list(self.presets.keys())
        if not self.preset_names:
            logging.error("No presets available. Please add presets to 'DEFAULT_PRESETS'.")
            raise ValueError("Presets dictionary is empty.")

        # Force color picker to show no text initially
        self.color_picker_button.setText("")

        self.show()

    def create_menu_frame(self):
        """
        Creates the vertical menu panel with finger key mappings, customization options, etc.

        Returns:
            QFrame: The configured menu frame widget.
        """
        frame = QFrame(self)
        frame.setFixedWidth(MENU_WIDTH)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # ----------- Left Hand Mapping -----------
        left_label = QLabel("Left Hand", frame)
        bold_font = QFont(LABEL_FONT)
        bold_font.setBold(True)
        left_label.setFont(bold_font)
        left_label.setStyleSheet("color: black;")
        layout.addWidget(left_label, alignment=Qt.AlignLeft)

        self.left_entries = {}
        left_grid = QGridLayout()
        left_grid.setContentsMargins(0, 0, 0, 0)
        left_grid.setHorizontalSpacing(10)
        left_grid.setVerticalSpacing(10)
        left_grid.setColumnStretch(1, 1)

        left_fingers = [(8, "Index"), (12, "Middle"), (16, "Ring"), (20, "Pinky")]
        for row, (finger_id, finger_name) in enumerate(left_fingers):
            lbl = QLabel(f"{finger_name}:", frame)
            lbl.setFont(ENTRY_FONT)
            lbl.setStyleSheet("color: black;")

            entry = QLineEdit(frame)
            entry.setText(self.left_hand_key_map.get(finger_id, ''))
            entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            entry.setFixedHeight(25)

            left_grid.addWidget(lbl, row, 0)
            left_grid.addWidget(entry, row, 1)
            self.left_entries[finger_id] = entry

        layout.addLayout(left_grid)
        layout.addSpacing(10)

        # ----------- Right Hand Mapping -----------
        right_label = QLabel("Right Hand", frame)
        bold_font.setBold(True)
        right_label.setFont(bold_font)
        right_label.setStyleSheet("color: black;")
        layout.addWidget(right_label, alignment=Qt.AlignLeft)

        self.right_entries = {}
        right_grid = QGridLayout()
        right_grid.setContentsMargins(0, 0, 0, 0)
        right_grid.setHorizontalSpacing(10)
        right_grid.setVerticalSpacing(10)
        right_grid.setColumnStretch(1, 1)

        right_fingers = [(8, "Index"), (12, "Middle"), (16, "Ring"), (20, "Pinky")]
        for row, (finger_id, finger_name) in enumerate(right_fingers):
            lbl = QLabel(f"{finger_name}:", frame)
            lbl.setFont(ENTRY_FONT)
            lbl.setStyleSheet("color: black;")

            entry = QLineEdit(frame)
            entry.setText(self.right_hand_key_map.get(finger_id, ''))
            entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            entry.setFixedHeight(25)

            right_grid.addWidget(lbl, row, 0)
            right_grid.addWidget(entry, row, 1)
            self.right_entries[finger_id] = entry

        layout.addLayout(right_grid)
        layout.addSpacing(10)

        # ----------- Customization Section -----------
        customization_label = QLabel("Customization", frame)
        customization_label.setFont(bold_font)
        customization_label.setStyleSheet("color: black;")
        layout.addWidget(customization_label, alignment=Qt.AlignLeft)

        customization_layout = QHBoxLayout()
        customization_layout.setSpacing(10)

        # Background frame for font selector
        font_selector_bg = QFrame(frame)
        font_selector_bg.setStyleSheet("""
            QFrame {
                background-color: #F0F0F0;
                border-radius: 8px;
            }
        """)
        font_selector_bg.setFixedHeight(25)
        font_selector_layout = QHBoxLayout(font_selector_bg)
        font_selector_layout.setContentsMargins(10, 5, 5, 5)

        self.font_selector = CenteredComboBox(font_selector_bg)
        self.font_selector.setFixedWidth(100)
        self.font_selector.setFixedHeight(15)
        self.load_fonts_from_directory(os.path.join(os.path.dirname(sys.argv[0]), 'fonts'))
        font_selector_layout.addWidget(self.font_selector)
        customization_layout.addWidget(font_selector_bg)

        # Color picker
        self.color_picker_button = QPushButton("", frame)
        self.color_picker_button.setFixedWidth(100)
        self.color_picker_button.setFixedHeight(25)
        self.color_picker_button.clicked.connect(self.open_color_dialog)
        customization_layout.addWidget(self.color_picker_button)

        layout.addLayout(customization_layout)
        layout.addSpacing(10)

        # Apply button
        apply_button = QPushButton("Apply", frame)
        apply_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        apply_button.setFixedHeight(30)
        apply_button.clicked.connect(self.save_mappings)
        layout.addWidget(apply_button)

        layout.addStretch(1)
        return frame

    def load_fonts_from_directory(self, fonts_dir):
        """
        Loads available font files (TTF, OTF) from a directory into the font selector combo box.

        Args:
            fonts_dir (str): The directory containing font files.
        """
        if not os.path.isdir(fonts_dir):
            logging.error(f"Fonts directory '{fonts_dir}' does not exist.")
            QMessageBox.critical(self, "Error", f"Fonts directory '{fonts_dir}' does not exist.")
            return

        fonts_dir = os.path.abspath(fonts_dir)
        for file in os.listdir(fonts_dir):
            if file.lower().endswith(('.ttf', '.otf')):
                font_path = os.path.join(fonts_dir, file)
                font_id = QFontDatabase.addApplicationFont(font_path)
                families = QFontDatabase.applicationFontFamilies(font_id)
                base_name = os.path.splitext(file)[0]
                for family in families:
                    index = self.font_selector.count()
                    self.font_selector.addItem(base_name)
                    self.font_selector.setItemData(index, base_name, Qt.DisplayRole)
                    self.font_selector.setItemData(index, QFont(family), Qt.FontRole)

    def open_color_dialog(self):
        """
        Opens a color picker dialog for choosing a new annotation color.
        """
        initial_color = getattr(self, 'selected_color', QColor('#d3d3d3'))
        color = QColorDialog.getColor(initial_color, self, "Select Annotation Color")

        if color.isValid():
            self.selected_color = color
            self.color_picker_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color.name()};
                    color: black;
                    border: 1px solid #d3d3d3;
                    border-radius: 8px;
                    padding: 4px;
                    font: 12px 'San Francisco';
                }}
                QPushButton:hover {{
                    background-color: {color.lighter(110).name()};
                }}
            """)
            logging.info(f"Selected color: {color.name()}")
        else:
            logging.info("Color selection canceled.")

    def create_camera_feed_frame(self):
        """
        Creates the camera feed panel that also hosts overlay controls (preset selector, pause button, gear button).

        Returns:
            QFrame: The camera feed container.
        """
        frame = QFrame(self)
        frame.setMinimumSize(self.camera_width, self.camera_height)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        self.camera_label = QLabel(frame)
        self.camera_label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.camera_label)

        # Overlay frame for controls
        self.overlay_frame = QFrame(frame)
        self.overlay_frame.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.overlay_frame.setGeometry(QRect(0, 0, self.camera_width, self.camera_height))
        self.overlay_frame.setStyleSheet("background: transparent;")
        self.overlay_frame.setParent(frame)
        self.overlay_frame.raise_()

        # White pill-shaped background for preset combo
        preset_background = QFrame(self.overlay_frame)
        preset_background.setFixedSize(130, 40)
        preset_background.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 20px;
            }
        """)
        preset_background.move(self.camera_width - 240, 10)
        preset_background.raise_()

        # Preset selector
        self.preset_selector = CenteredComboBox(self.overlay_frame)
        self.preset_selector.setFixedSize(100, 40)
        for preset_name in self.presets.keys():
            self.preset_selector.addItem(preset_name)
        index = self.preset_selector.findText(self.current_preset_name)
        if index >= 0:
            self.preset_selector.setCurrentIndex(index)
        self.preset_selector.currentTextChanged.connect(self.on_preset_changed)
        self.preset_selector.move(self.camera_width - 220, 10)
        self.preset_selector.raise_()

        # Play/Pause button
        if not PAUSE_ICON.isNull() and not PLAY_ICON.isNull():
            self.play_button = QPushButton("", self.overlay_frame)
            self.play_button.setIcon(QIcon(PLAY_ICON))
            self.play_button.setFixedSize(40, 40)
            self.play_button.setIconSize(QSize(20, 20))
            self.play_button.move(self.camera_width - 100, 10)
            self.play_button.clicked.connect(self.toggle_pause)
            self.play_button.raise_()

        # Gear (settings) button
        if not GEAR_ICON.isNull():
            self.gear_button = QPushButton("", self.overlay_frame)
            self.gear_button.setIcon(QIcon(GEAR_ICON))
            self.gear_button.setFixedSize(40, 40)
            self.gear_button.setIconSize(QSize(20, 20))
            self.gear_button.move(self.camera_width - 50, 10)
            self.gear_button.clicked.connect(self.toggle_menu)
            self.gear_button.raise_()

        return frame

    def on_preset_changed(self, new_preset_name):
        """
        Triggered when the user selects a different preset from the combo box.

        Args:
            new_preset_name (str): The name of the newly selected preset.
        """
        self.current_preset_name = new_preset_name
        preset_data = self.presets[new_preset_name]

        if len(preset_data) == 4:
            left_map, right_map, selected_font, selected_color = preset_data
        else:
            left_map, right_map = preset_data
            selected_font = 'Default'
            selected_color = '#d3d3d3'

        self.left_hand_key_map = left_map.copy()
        self.right_hand_key_map = right_map.copy()

        # Update the UI entries to match the selected preset
        for f_id, entry in self.left_entries.items():
            entry.setText(self.left_hand_key_map.get(f_id, ''))
        for f_id, entry in self.right_entries.items():
            entry.setText(self.right_hand_key_map.get(f_id, ''))

        # Update font selector
        if selected_font in [self.font_selector.itemText(i) for i in range(self.font_selector.count())]:
            self.font_selector.setCurrentText(selected_font)
        else:
            logging.warning(f"Selected font '{selected_font}' not found in list.")
            if self.font_selector.count() > 0:
                self.font_selector.setCurrentIndex(0)

        # Update color picker
        self.selected_color = QColor(selected_color)
        self.color_picker_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {selected_color};
                color: black;
                border: 1px solid #d3d3d3;
                border-radius: 8px;
                padding: 4px;
                font: 12px 'San Francisco';
            }}
            QPushButton:hover {{
                background-color: {self.selected_color.lighter(110).name()};
            }}
        """)
        self.color_picker_button.setText("")

        logging.info(f"Preset changed to: {new_preset_name}")
        self.preset_changed.emit(self.left_hand_key_map, self.right_hand_key_map, selected_font, selected_color)

    def switch_to_next_preset(self):
        """
        Cycles to the next preset in the self.presets list.
        """
        current_index = self.preset_names.index(self.current_preset_name)
        next_index = (current_index + 1) % len(self.preset_names)
        next_preset_name = self.preset_names[next_index]
        logging.info(f"Switching preset from '{self.current_preset_name}' to '{next_preset_name}'.")
        self.preset_selector.setCurrentIndex(next_index)

    def update_font_and_color_from_preset(self):
        """
        Updates the UI controls for font selector and color picker from the current preset.
        """
        preset_data = self.presets.get(self.current_preset_name, ({}, {}, 'Default', '#d3d3d3'))
        _, _, selected_font, selected_color = preset_data

        # Update font selector
        if selected_font in [self.font_selector.itemText(i) for i in range(self.font_selector.count())]:
            self.font_selector.setCurrentText(selected_font)
        else:
            logging.warning(f"Font '{selected_font}' not found.")
            if self.font_selector.count() > 0:
                self.font_selector.setCurrentIndex(0)

        # Update color picker
        self.selected_color = QColor(selected_color)
        self.color_picker_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {selected_color};
                color: black;
                border: 1px solid #d3d3d3;
                border-radius: 8px;
                padding: 4px;
                font: 12px 'San Francisco';
            }}
            QPushButton:hover {{
                background-color: {self.selected_color.lighter(110).name()};
            }}
        """)
        logging.info(f"Font and color updated to preset '{self.current_preset_name}'.")

    def apply_styles(self):
        """
        Applies a consistent stylesheet to UI elements.
        """
        bg_color = self.color_palette["MENU_BG_COLOR"]
        label_color = "black"
        entry_bg = self.color_palette["ENTRY_BG_COLOR"]
        entry_text = "black"
        button_fg = self.color_palette["BUTTON_FG_COLOR"]
        button_hover = self.color_palette["BUTTON_HOVER_COLOR"]
        button_hover2 = self.color_palette["BUTTON_HOVER_COLOR_2"]
        button_text = self.color_palette["BUTTON_TEXT_COLOR"]
        canvas_bg = self.color_palette["CANVAS_BG_COLOR"]

        self.menu_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 8px;
            }}
            QLabel {{
                color: {label_color};
                font: 14px 'San Francisco';
            }}
            QLineEdit {{
                background-color: {entry_bg};
                color: {entry_text};
                border: 1px solid {entry_bg};
                border-radius: 8px;
                padding: 4px;
                font: 12px 'San Francisco';
            }}
            QPushButton {{
                background-color: {button_fg};
                color: {button_text};
                font: bold 14px 'San Francisco';
                border-radius: 8px;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: {button_hover2};
            }}
            QComboBox {{
                background-color: transparent;
                color: black;
                border: none;
                padding: 0px;
                font: 12px 'San Francisco';
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
                right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {bg_color};
                color: {entry_text};
                border: 1px solid {entry_bg};
                border-radius: 10px;
            }}
            QComboBox::item {{
                padding: 10px;
            }}
            QComboBox::item:hover {{
                background-color: {button_hover};
            }}
            QComboBox::item:selected {{
                background-color: {button_hover2};
                color: {button_text};
            }}
        """)
        self.camera_frame.setStyleSheet(f"QFrame {{ background-color: {canvas_bg}; }}")

        # Gear button style
        if hasattr(self, 'gear_button'):
            self.gear_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    border-radius: 20px;
                }}
                QPushButton:hover {{
                    background-color: {button_hover};
                }}
            """)

        # Play/Pause button style
        if hasattr(self, 'play_button'):
            self.play_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    border-radius: 20px;
                }}
                QPushButton:hover {{
                    background-color: {button_hover};
                }}
            """)

        # Color picker button style
        if hasattr(self, 'color_picker_button'):
            self.color_picker_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {entry_bg};
                    color: {entry_text};
                    border: 1px solid {entry_bg};
                    border-radius: 8px;
                    padding: 4px;
                    font: 12px 'San Francisco';
                }}
                QPushButton:hover {{
                    background-color: {button_hover};
                }}
            """)

        # Font selector style
        if hasattr(self, 'font_selector'):
            self.font_selector.setStyleSheet(f"""
                QComboBox {{
                    background-color: transparent;
                    color: black;
                    border: none;
                    padding: 0px;
                    font: 12px 'San Francisco';
                }}
                QComboBox::drop-down {{
                    border: none;
                }}
                QComboBox::down-arrow {{
                    width: 12px;
                    height: 12px;
                    right: 8px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {bg_color};
                    color: {entry_text};
                    border: 1px solid {entry_bg};
                    border-radius: 10px;
                }}
                QComboBox::item {{
                    padding: 10px;
                }}
                QComboBox::item:hover {{
                    background-color: {button_hover};
                }}
                QComboBox::item:selected {{
                    background-color: {button_hover2};
                    color: {button_text};
                }}
            """)

    def toggle_menu(self):
        """
        Shows or hides the menu panel.
        """
        self.menu_visible = not self.menu_visible
        if self.menu_visible:
            self.menu_frame.show()
            self.setMinimumSize(self.camera_width + MENU_WIDTH, self.camera_height)
            self.setMaximumSize(self.camera_width + MENU_WIDTH, self.camera_height)
            self.resize(self.camera_width + MENU_WIDTH, self.camera_height)
            logging.info("Menu toggled ON.")
        else:
            self.menu_frame.hide()
            self.setMinimumSize(self.camera_width, self.camera_height)
            self.setMaximumSize(self.camera_width, self.camera_height)
            self.resize(self.camera_width, self.camera_height)
            logging.info("Menu toggled OFF.")

    def toggle_pause(self):
        """
        Toggles the pause state of the camera feed.
        """
        self.pause_state = not self.pause_state
        if self.pause_state:
            if not PLAY_ICON.isNull():
                self.play_button.setIcon(QIcon(PLAY_ICON))
                self.play_button.setIconSize(QSize(20, 20))
            self.camera_manager.pause()
            logging.info("Camera processing paused.")
        else:
            if not PAUSE_ICON.isNull():
                self.play_button.setIcon(QIcon(PAUSE_ICON))
                self.play_button.setIconSize(QSize(20, 20))
            self.camera_manager.resume()
            logging.info("Camera processing resumed.")

    def save_mappings(self):
        """
        Gathers the current mappings from UI entries and updates the active preset.
        """
        for f_id, entry in self.left_entries.items():
            self.left_hand_key_map[f_id] = entry.text()
        for f_id, entry in self.right_entries.items():
            self.right_hand_key_map[f_id] = entry.text()

        # Get font and color from UI
        selected_font = self.font_selector.currentText()
        selected_color = getattr(self, 'selected_color', QColor('d3d3d3')).name()

        # Update the current preset
        self.presets[self.current_preset_name] = (
            self.left_hand_key_map.copy(),
            self.right_hand_key_map.copy(),
            selected_font,
            selected_color
        )

        logging.info("Mappings updated:")
        logging.info(f"Left Hand: {self.left_hand_key_map}")
        logging.info(f"Right Hand: {self.right_hand_key_map}")
        logging.info(f"Selected Font: {selected_font}")
        logging.info(f"Selected Color: {selected_color}")

        self.preset_changed.emit(
            self.left_hand_key_map,
            self.right_hand_key_map,
            selected_font,
            selected_color
        )

    def update_camera_feed(self):
        """
        Periodically called by QTimer to fetch the latest frame and display it.
        Also processes action events from the action_event_queue.
        """
        frame_pil = self.camera_manager.get_latest_frame()
        if frame_pil is not None:
            frame_rgb = frame_pil.convert('RGB')
            w, h = frame_rgb.size
            data = frame_rgb.tobytes("raw", "RGB")
            qimage = QImage(data, w, h, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
            self.camera_label.setScaledContents(False)
            self.camera_label.setPixmap(pixmap)

        # Process action events from the queue
        while True:
            try:
                event = self.action_event_queue.get_nowait()
                if event == 'toggle_menu':
                    self.toggle_menu()
                elif event == 'toggle_preset':
                    self.switch_to_next_preset()
                elif event == 'toggle_pause':
                    self.toggle_pause()
                else:
                    logging.debug(f"Unhandled action event: {event}")
                self.action_event_queue.task_done()
            except queue.Empty:
                break

        # Sync pause button icon with actual paused state
        if self.pause_state != self.camera_manager.paused:
            self.pause_state = self.camera_manager.paused
            if self.pause_state:
                if not PLAY_ICON.isNull():
                    self.play_button.setIcon(QIcon(PLAY_ICON))
                    self.play_button.setIconSize(QSize(20, 20))
                logging.info("UI updated: Camera paused (Play icon).")
            else:
                if not PAUSE_ICON.isNull():
                    self.play_button.setIcon(QIcon(PAUSE_ICON))
                    self.play_button.setIconSize(QSize(20, 20))
                logging.info("UI updated: Camera resumed (Pause icon).")

    def closeEvent(self, event):
        """
        Called when the user closes the main window. Stops the camera manager.
        """
        logging.info("Closing application. Stopping camera manager...")
        self.camera_manager.stop()
        event.accept()