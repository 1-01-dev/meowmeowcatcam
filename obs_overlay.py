"""Transparent Windows overlay for OBS.

Runs the same MediaPipe gesture detector without showing a camera/debug window.
Only the active cat reaction is rendered into a transparent, borderless window.
When no gesture is active, the window is fully transparent.

OBS: add a Window Capture source and select "MeowMeowCatCam OBS Overlay".
Press Q or Esc to stop the overlay.
"""

import ctypes
import ctypes.wintypes as wt
import random
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import gesture_meme as app

# Reuse the same stability and idle timing as the desktop version.
STABLE_FRAMES_REQUIRED = 5
HIDE_DELAY_MS = 600
WINDOW_W = 900
WINDOW_H = 900
FPS = 30

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
ULW_ALPHA = 0x00000002
AC_SRC_ALPHA = 1
BI_RGB = 0
DIB_RGB_COLORS = 0
SW_SHOWNOACTIVATE = 4
WM_DESTROY = 0x0002
WM_KEYDOWN = 0x0100
VK_ESCAPE = 0x1B

class POINT(ctypes.Structure):
    _fields_ = [("x", wt.LONG), ("y", wt.LONG)]

class SIZE(ctypes.Structure):
    _fields_ = [("cx", wt.LONG), ("cy", wt.LONG)]

class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", wt.BYTE), ("BlendFlags", wt.BYTE), ("SourceConstantAlpha", wt.BYTE), ("AlphaFormat", wt.BYTE)]

WNDPROC = ctypes.WINFUNCTYPE(wt.LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
        ("hCursor", wt.HCURSOR), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def _wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    if msg == WM_KEYDOWN and (wparam == VK_ESCAPE or wparam == ord("Q")):
        user32.DestroyWindow(hwnd)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


class TransparentWindow:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self._proc = WNDPROC(_wnd_proc)
        self.hinstance = kernel32.GetModuleHandleW(None)
        self.class_name = "MeowMeowCatCamOBSOverlay"

        wc = WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = self.hinstance
        wc.lpszClassName = self.class_name
        user32.RegisterClassW(ctypes.byref(wc))

        ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self.hwnd = user32.CreateWindowExW(
            ex, self.class_name, "MeowMeowCatCam OBS Overlay", WS_POPUP,
            0, 0, width, height, None, None, self.hinstance, None
        )
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)

    def draw(self, rgba):
        rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
        # Windows layered windows expect premultiplied BGRA.
        bgra = rgba[..., [2, 1, 0, 3]].copy()
        alpha = bgra[..., 3:4].astype(np.uint16)
        bgra[..., :3] = (bgra[..., :3].astype(np.uint16) * alpha // 255).astype(np.uint8)

        hdc_screen = user32.GetDC(None)
        hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.width
        bmi.bmiHeader.biHeight = -self.height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        hbitmap = ctypes.windll.gdi32.CreateDIBSection(
            hdc_mem, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        ctypes.memmove(bits, bgra.ctypes.data, bgra.nbytes)
        old = ctypes.windll.gdi32.SelectObject(hdc_mem, hbitmap)

        pt_src = POINT(0, 0)
        pt_pos = POINT(0, 0)
        size = SIZE(self.width, self.height)
        blend = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(
            self.hwnd, hdc_screen, ctypes.byref(pt_pos), ctypes.byref(size),
            hdc_mem, ctypes.byref(pt_src), 0, ctypes.byref(blend), ULW_ALPHA
        )

        ctypes.windll.gdi32.SelectObject(hdc_mem, old)
        ctypes.windll.gdi32.DeleteObject(hbitmap)
        ctypes.windll.gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)

    def close(self):
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None


def contain_rgba(img_bgr, width, height, alpha=255):
    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    if img_bgr is None:
        return canvas
    h, w = img_bgr.shape[:2]
    scale = min(width / w, height / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    x, y = (width - nw) // 2, (height - nh) // 2
    canvas[y:y+nh, x:x+nw, :3] = resized[..., ::-1]
    canvas[y:y+nh, x:x+nw, 3] = alpha
    return canvas


def main():
    app.STABLE_FRAMES_REQUIRED = STABLE_FRAMES_REQUIRED
    app.DEFAULT_FALLBACK_MS = HIDE_DELAY_MS

    hand_landmarker = app.HandLandmarker.create_from_options(
        app.HandLandmarkerOptions(
            base_options=app.BaseOptions(model_asset_path=str(app.MODELS / "hand_landmarker.task")),
            running_mode=app.RunningMode.VIDEO,
            num_hands=2,
        )
    )
    face_landmarker = app.FaceLandmarker.create_from_options(
        app.FaceLandmarkerOptions(
            base_options=app.BaseOptions(model_asset_path=str(app.MODELS / "face_landmarker.task")),
            running_mode=app.RunningMode.VIDEO,
            num_faces=1,
            output_facial_transformation_matrixes=True,
        )
    )

    memes = app.load_memes()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam (index 0)")

    window = TransparentWindow(WINDOW_W, WINDOW_H)
    state = app.GestureState()
    current_gesture = "default"
    candidate_gesture = "default"
    candidate_streak = 0
    current_meme = None
    last_non_default_at = time.time() * 1000
    prev_flow_gray = None
    start_time = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)

            magnitude, coherence, prev_flow_gray = app.frame_flow_signal(frame, prev_flow_gray)
            state.update_flow(magnitude, coherence)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = app.Image(image_format=app.ImageFormat.SRGB, data=rgb)
            ts_ms = int((time.time() - start_time) * 1000)
            hand_result = hand_landmarker.detect_for_video(mp_image, ts_ms)
            face_result = face_landmarker.detect_for_video(mp_image, ts_ms)
            state.update_face(face_result)
            gesture = state.decide(hand_result)

            now = time.time() * 1000
            if gesture == candidate_gesture:
                candidate_streak += 1
            else:
                candidate_gesture = gesture
                candidate_streak = 1

            if candidate_streak >= STABLE_FRAMES_REQUIRED and gesture != current_gesture:
                current_gesture = gesture
                if gesture != "default" and gesture not in app.VIDEO_GESTURES:
                    choices = memes.get(gesture, [])
                    if choices:
                        previous = current_meme
                        options = [m for m in choices if m is not previous] or choices
                        current_meme = random.choice(options)
                elif gesture == "spinCat":
                    current_meme = None

            if gesture != "default":
                last_non_default_at = now
            elif now - last_non_default_at > HIDE_DELAY_MS:
                current_gesture = "default"
                current_meme = None

            if current_gesture == "default":
                window.draw(np.zeros((WINDOW_H, WINDOW_W, 4), dtype=np.uint8))
            elif current_gesture == "spinCat":
                # Stream the spin video as a normal opaque reaction frame.
                if not hasattr(main, "spin_cap"):
                    main.spin_cap = cv2.VideoCapture(str(app.MEMES / app.GESTURE_MEMES["spinCat"][0]))
                ok_v, vframe = main.spin_cap.read()
                if not ok_v:
                    main.spin_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok_v, vframe = main.spin_cap.read()
                window.draw(contain_rgba(vframe, WINDOW_W, WINDOW_H))
            else:
                window.draw(contain_rgba(current_meme, WINDOW_W, WINDOW_H))

            # Keep processing Windows messages without creating a visible UI.
            msg = wt.MSG()
            while user32.PeekMessageW(ctypes.byref(msg), window.hwnd, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(max(0, 1 / FPS))
    finally:
        cap.release()
        hand_landmarker.close()
        face_landmarker.close()
        if hasattr(main, "spin_cap"):
            main.spin_cap.release()
        window.close()


if __name__ == "__main__":
    main()
