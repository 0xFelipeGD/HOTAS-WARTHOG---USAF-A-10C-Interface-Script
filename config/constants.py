# =============================================================================
# config/constants.py
# Visual, layout, USB, and timing constants for the HOTAS Warthog Dashboard.
# All magic numbers live here — no hardcoded values in the main scripts.
# =============================================================================

# ---------------------------------------------------------------------------
# Window / display
# ---------------------------------------------------------------------------
WINDOW_WIDTH  = 1280
WINDOW_HEIGHT = 900
WINDOW_TITLE  = "HOTAS Warthog A-10C Dashboard"

# ---------------------------------------------------------------------------
# Colors  (R, G, B)
# ---------------------------------------------------------------------------
COLOR_BG          = (18,  20,  28)   # Very dark blue-gray background
COLOR_PANEL_BG    = (30,  32,  44)   # Slightly lighter panel surfaces
COLOR_TEXT        = (220, 220, 230)  # Primary text (near-white)
COLOR_TEXT_DIM    = (130, 130, 145)  # Secondary / label text
COLOR_TEXT_HEADER = (255, 210,  60)  # Section headers (amber)

COLOR_GREEN       = (40,  210,  80)  # Button pressed / connected indicator
COLOR_GREEN_DIM   = (20,   90,  35)  # Pressed LED glow outline
COLOR_RED         = (220,  50,  50)  # Disconnected / error
COLOR_AMBER       = (255, 176,   0)  # Warning messages
COLOR_BLUE        = (50,  130, 255)  # Axis bar fill (bipolar)
COLOR_BLUE_TROT   = (50,  190, 160)  # Axis bar fill (throttle / unipolar)
COLOR_DARK_GRAY   = (55,   55,  65)  # Inactive button LED
COLOR_BORDER      = (70,   72,  90)  # Panel outlines
COLOR_CENTER_LINE = (160, 160, 175)  # Axis center marker

# ---------------------------------------------------------------------------
# Layout — axis bars
# ---------------------------------------------------------------------------
AXIS_BAR_WIDTH    = 260   # pixel width of the progress-bar track
AXIS_BAR_HEIGHT   = 14    # pixel height of the bar
AXIS_LABEL_W      = 160   # pixel width reserved for axis name label

# ---------------------------------------------------------------------------
# Layout — button LEDs
# ---------------------------------------------------------------------------
BUTTON_LED_RADIUS   = 7    # circle radius in pixels
BUTTON_LABEL_OFFSET = 11   # horizontal gap between LED centre and label start
BUTTON_COL_W        = 110  # horizontal spacing between LED columns
BUTTON_ROW_H        = 26   # vertical spacing between LED rows

# ---------------------------------------------------------------------------
# Layout — hat indicators
# ---------------------------------------------------------------------------
HAT_BOX_SIZE  = 60   # width & height of the hat-indicator bounding box
HAT_ARROW_LEN = 16   # length of each directional arrow

# ---------------------------------------------------------------------------
# Layout — section padding
# ---------------------------------------------------------------------------
SECTION_PAD  = 14   # internal padding inside each panel
SECTION_GAP  = 10   # gap between adjacent panels

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
TARGET_FPS         = 60     # render loop target
RECONNECT_INTERVAL = 2.0    # seconds between reconnect attempts when device lost

# ---------------------------------------------------------------------------
# USB identification — Thrustmaster HOTAS Warthog
# ---------------------------------------------------------------------------
VENDOR_THRUSTMASTER  = 0x044F
PID_WARTHOG_STICK    = 0x0402
PID_WARTHOG_THROTTLE = 0x0404
