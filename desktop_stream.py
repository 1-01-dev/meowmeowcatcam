"""Stream-friendly launcher for the desktop gesture meme detector.

Keeps the existing gesture detector intact and adds presentation behavior:
- no Poker Cat in the idle state;
- configurable stability/fallback timing;
- subtle meme fade in/out;
- no immediate repeat when a gesture has multiple meme choices.
"""

import time
import random
from pathlib import Path

import cv2
import numpy as np

import gesture_meme as app


SETTINGS = {
    "stable_frames": 5,
    "hide_delay_ms": 600,
    "fade_in_ms": 120,
    "fade_out_ms": 180,
    "avoid_immediate_repeat": True,
}

# Keep these values in one place while reusing the original detector.
app.STABLE_FRAMES_REQUIRED = SETTINGS["stable_frames"]
app.DEFAULT_FALLBACK_MS = SETTINGS["hide_delay_ms"]


_last_choice = {}
_original_choice = random.choice


def non_repeating_choice(seq):
    if not SETTINGS["avoid_immediate_repeat"] or len(seq) < 2:
        return _original_choice(seq)

    key = tuple(seq)
    previous = _last_choice.get(key)
    candidates = [item for item in seq if item != previous]
    chosen = _original_choice(candidates or list(seq))
    _last_choice[key] = chosen
    return chosen


# The original desktop app uses app.random.choice, so replacing it here gives
# all multi-image gestures the no-immediate-repeat behavior without changing
# their detection logic.
app.random.choice = non_repeating_choice


_original_imshow = cv2.imshow
_default = cv2.imread(
    str(Path(app.MEMES) / "pokercat.jpg"), cv2.IMREAD_COLOR
)
_visible = False
_transition_start = 0.0
_transition_direction = "out"
_last_meme = None


def _is_default(img):
    if _default is None or img is None:
        return False

    reference = _default
    if img.shape != reference.shape:
        reference = cv2.resize(
            reference,
            (img.shape[1], img.shape[0]),
            interpolation=cv2.INTER_AREA,
        )

    return bool(np.mean(cv2.absdiff(img, reference)) < 0.5)


def _animate(img, target_visible):
    global _visible, _transition_start, _transition_direction, _last_meme

    now = time.perf_counter()
    if target_visible != _visible:
        _visible = target_visible
        _transition_start = now
        _transition_direction = "in" if target_visible else "out"
        if target_visible:
            _last_meme = img.copy()

    if _last_meme is None:
        return np.zeros_like(img)

    duration_ms = (
        SETTINGS["fade_in_ms"]
        if _transition_direction == "in"
        else SETTINGS["fade_out_ms"]
    )
    duration = duration_ms / 1000.0

    if duration <= 0:
        alpha = 1.0 if target_visible else 0.0
    else:
        progress = min(1.0, (now - _transition_start) / duration)
        alpha = progress if _transition_direction == "in" else 1.0 - progress

    if _visible and alpha >= 1.0:
        return _last_meme
    if not _visible and alpha <= 0.0:
        return np.zeros_like(_last_meme)

    return cv2.addWeighted(
        _last_meme,
        alpha,
        np.zeros_like(_last_meme),
        1.0 - alpha,
        0,
    )


def stream_imshow(window, img):
    if window != "Meme":
        _original_imshow(window, img)
        return

    # The original detector still uses "default" internally. Visually, the
    # default state is now an empty black reaction pane.
    if _is_default(img):
        blank = np.zeros_like(img)
        _original_imshow(window, _animate(blank, False))
        return

    _original_imshow(window, _animate(img, True))


cv2.imshow = stream_imshow


if __name__ == "__main__":
    app.main()
