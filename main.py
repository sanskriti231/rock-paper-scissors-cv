import os
import random
import time
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# 1. download hand landmaker from mediapipe if not already downloaded
MODEL_PATH = "models/hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)


def download_model_if_needed():
    if os.path.exists(MODEL_PATH):
        return
    print("Downloading hand landmark model (one-time setup)...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Model downloaded:", MODEL_PATH)


# 2. Hand landmark indexes
FINGER_TIPS = [8, 12, 16, 20]  # index, middle, ring, pinky tips
FINGER_PIPS = [6, 10, 14, 18]  # index, middle, ring, pinky middle joints
THUMB_TIP = 4
THUMB_IP = 3
INDEX_MCP = 5


HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),          # index finger
    (5, 9), (9, 10), (10, 11), (11, 12),     # middle finger
    (9, 13), (13, 14), (14, 15), (15, 16),   # ring finger
    (13, 17), (17, 18), (18, 19), (19, 20),  # pinky finger
    (0, 17),                                 # palm base
]

GESTURES = {
    (0, 0, 0, 0, 0): "Rock",
    (1, 1, 1, 1, 1): "Paper",
    (0, 1, 1, 0, 0): "Scissors",
}

MOVES = ["Rock", "Paper", "Scissors"]

# Game states
STATE_WAITING = "WAITING"
STATE_COUNTDOWN = "COUNTDOWN"
STATE_RESULT = "RESULT"

COUNTDOWN_SECONDS = 3


# 3. Gesture detection by pure geometry
def _distance(point_a, point_b):
    """Straight-line distance between two landmarks (x, y only)."""
    return ((point_a.x - point_b.x) ** 2 + (point_a.y - point_b.y) ** 2) ** 0.5


def detect_gesture(hand_landmarks):
    """
    Returns:
        gesture (str): "Rock", "Paper", "Scissors", or "Unknown"
        finger_states (list[int]): [thumb, index, middle, ring, pinky],
            where 1 means "extended" and 0 means "folded down".
    """
    finger_states = []

    thumb_tip = hand_landmarks[THUMB_TIP]
    thumb_ip = hand_landmarks[THUMB_IP]
    index_mcp = hand_landmarks[INDEX_MCP]
    thumb_extended = _distance(thumb_tip, index_mcp) > _distance(thumb_ip, index_mcp)
    finger_states.append(1 if thumb_extended else 0)

    for tip_idx, pip_idx in zip(FINGER_TIPS, FINGER_PIPS):
        tip = hand_landmarks[tip_idx]
        pip = hand_landmarks[pip_idx]
        extended = tip.y < pip.y
        finger_states.append(1 if extended else 0)

    gesture = GESTURES.get(tuple(finger_states), "Unknown")
    return gesture, finger_states


# 4. GAME LOGIC

def get_computer_move():
    """Randomly pick the computer's move."""
    return random.choice(MOVES)


def determine_winner(user_move, computer_move):
    """Decide the outcome of a round."""
    if user_move == "Unknown":
        return "No clear gesture detected - try again!"
    if user_move == computer_move:
        return "It's a Tie!"

    beats = {"Rock": "Scissors", "Paper": "Rock", "Scissors": "Paper"}
    if beats[user_move] == computer_move:
        return "You Win!"
    return "Computer Wins!"



# 5. DRAWING HELPERS

def draw_landmarks(frame, hand_landmarks):
    """Draw the 21 hand points and the connecting skeleton lines."""
    h, w, _ = frame.shape
    points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]

    for start_idx, end_idx in HAND_CONNECTIONS:
        cv2.line(frame, points[start_idx], points[end_idx], (0, 255, 0), 2)

    for point in points:
        cv2.circle(frame, point, 5, (0, 0, 255), -1)


def draw_game_ui(frame, state, user_move=None, computer_move=None,
                  result=None, countdown_value=None):
    """Draw all the on-screen text for the current game state."""
    h, w, _ = frame.shape

    # Semi-transparent banner behind the text
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 110), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    if state == STATE_WAITING:
        cv2.putText(frame, "Rock Paper Scissors", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.putText(frame, "Press SPACE to play, Q to quit", (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    elif state == STATE_COUNTDOWN:
        text = str(countdown_value) if countdown_value > 0 else "Show your hand!"
        cv2.putText(frame, text, (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)

    elif state == STATE_RESULT:
        cv2.putText(frame, f"You: {user_move}   Computer: {computer_move}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame, result, (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.putText(frame, "SPACE = play again, Q = quit", (20, 105),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)



# 6. MAIN GAME LOOP
def main():
    download_model_if_needed()

    # Create the MediaPipe HandLandmarker
    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = mp_vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    landmarker = mp_vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return

    state = STATE_WAITING
    countdown_start_time = None
    last_user_move = "Unknown"
    computer_move = None
    result_text = None
    frame_timestamp_ms = 0

    print("Controls: SPACE = start round, Q = quit")

    while True:
        success, frame = cap.read()
        if not success:
            print("Failed to read from webcam.")
            break

        # Flip so the video feels like a mirror
        frame = cv2.flip(frame, 1)

        # Run MediaPipe hand detection on this frame
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        frame_timestamp_ms += 33  # roughly matches ~30 fps
        detection_result = landmarker.detect_for_video(mp_image, frame_timestamp_ms)

        current_gesture = "Unknown"
        if detection_result.hand_landmarks:
            hand_landmarks = detection_result.hand_landmarks[0]
            draw_landmarks(frame, hand_landmarks)
            current_gesture, _ = detect_gesture(hand_landmarks)

        # Game state machine 
        if state == STATE_COUNTDOWN:
            elapsed = time.time() - countdown_start_time
            remaining = COUNTDOWN_SECONDS - int(elapsed)

            if remaining > 0:
                draw_game_ui(frame, state, countdown_value=remaining)
            else:
                # Countdown finished this frame: capture the gesture now.
                last_user_move = current_gesture
                computer_move = get_computer_move()
                result_text = determine_winner(last_user_move, computer_move)
                state = STATE_RESULT

        elif state == STATE_RESULT:
            draw_game_ui(frame, state, user_move=last_user_move,
                         computer_move=computer_move, result=result_text)

        else:  # STATE_WAITING
            draw_game_ui(frame, state)

        cv2.imshow("Rock Paper Scissors", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):
            state = STATE_COUNTDOWN
            countdown_start_time = time.time()

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()


if __name__ == "__main__":
    main()
