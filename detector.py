# detector.py
import time
import numpy as np
import cv2
from collections import deque

# Load cascades (adjust path if needed)
FACE_CASCADE = cv2.CascadeClassifier('haarcascades/haarcascade_frontalface_default.xml')
EYE_CASCADE  = cv2.CascadeClassifier('haarcascades/haarcascade_eye.xml')

# Shared state (updated by streaming loop)
state = {
    "blink_rate": 0.0,
    "head_jitter": 0.0,
    "mouth_motion": 0.0,
    "eye_brightness": 0.0,
    "skin_tone_shift": 0.0,
    "stress_index": 0.0,
    "lie_probability": 0.0,
    "last_update": time.time()
}

# internal history buffers
_frame_history = deque(maxlen=30)   # store recent grayscale face crops
_face_centers = deque(maxlen=30)    # store recent face center positions
_eye_counts = deque(maxlen=30)      # number of open eyes detected per frame (0..2)

def analyze_face_from_frame(frame_bgr):
    """
    Input: full BGR frame from OpenCV
    Updates shared 'state' dict with metrics
    """
    global _frame_history, _face_centers, _eye_counts, state

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # detect faces (scaleFactor/minNeighbors tuned for speed)
    faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80,80))

    if len(faces) == 0:
        # no face - decay state slowly
        # reduce metrics gradually
        for k in ("blink_rate","head_jitter","mouth_motion","eye_brightness","skin_tone_shift"):
            state[k] = max(0.0, state.get(k,0.0) * 0.97)
        state['last_update'] = time.time()
        return

    # pick largest face (assume main subject)
    faces = sorted(faces, key=lambda r: r[2]*r[3], reverse=True)
    x,y,fw,fh = faces[0]
    face_gray = gray[y:y+fh, x:x+fw]
    face_bgr  = frame_bgr[y:y+fh, x:x+fw]

    # store face crop for temporal metrics
    face_small = cv2.resize(face_gray, (96, int(96 * fh/fw))) if fw>0 else face_gray
    _frame_history.append(face_small)

    # eye detection inside face region
    eyes = EYE_CASCADE.detectMultiScale(face_gray, scaleFactor=1.1, minNeighbors=3, minSize=(15,15))
    eye_count = len(eyes)
    _eye_counts.append(eye_count)

    # blink rate estimate:
    # compute moving average of eye counts; rapid drops from 2->0 mean a blink
    if len(_eye_counts) >= 8:
        arr = np.array(_eye_counts)
        # count transitions where previous >=1 and now ==0
        transitions = np.sum((arr[:-1] >= 1) & (arr[1:] == 0))
        blink_rate = (transitions / (len(arr)/8.0)) * 60.0  # rough blinks per minute proxy
    else:
        blink_rate = 0.0

    # head jitter: track center movement
    cx = x + fw/2.0
    cy = y + fh/2.0
    _face_centers.append((cx,cy))
    head_jitter = 0.0
    if len(_face_centers) >= 5:
        pts = np.array(_face_centers)
        diffs = np.sqrt(np.sum(np.diff(pts, axis=0)**2, axis=1))
        head_jitter = float(np.mean(diffs))  # pixels/frame average

    # mouth motion: estimate by comparing lower third intensity changes across history
    mouth_motion = 0.0
    if len(_frame_history) >= 6:
        # compute absolute diffs between successive face crops
        diffs = []
        fh2 = _frame_history[0].shape[0]
        for i in range(len(_frame_history)-1):
            a = _frame_history[i]
            b = _frame_history[i+1]
            # crop bottom quarter region (approx mouth)
            h0 = a.shape[0]
            y0 = int(h0*0.65)
            ra = a[y0:, :]
            rb = b[y0:, :]
            # resize to same shape if mismatch
            if ra.shape != rb.shape:
                rb = cv2.resize(rb, (ra.shape[1], ra.shape[0]))
            diffs.append(np.mean(np.abs(ra.astype(float) - rb.astype(float))))
        mouth_motion = float(np.mean(diffs))

    # eye brightness (avg brightness of eye patches)
    eye_brightness = 0.0
    if eyes is not None and len(eyes) > 0:
        vals = []
        for (ex,ey,ew,eh) in eyes[:2]:
            ey_patch = face_bgr[ey:ey+eh, ex:ex+ew]
            if ey_patch.size == 0: continue
            vals.append(np.mean(cv2.cvtColor(ey_patch, cv2.COLOR_BGR2GRAY)))
        if vals:
            eye_brightness = float(np.mean(vals))

    # skin tone shift: measure redness in face region (R-G)
    b,g,r = cv2.split(face_bgr)
    skin_redness = float(np.mean(r.astype(float) - g.astype(float)))

    # normalize signals to 0..100 scale using heuristics
    blink_norm = np.clip(blink_rate / 30.0 * 100.0, 0, 100)          # expected typical normalized
    jitter_norm = np.clip(head_jitter * 2.5, 0, 100)                 # tweak scale
    mouth_norm = np.clip(mouth_motion / 8.0 * 100.0, 0, 100)
    eye_bright_norm = np.clip((eye_brightness / 255.0) * 100.0, 0, 100)
    skin_shift_norm = np.clip((skin_redness + 20.0) * 2.0, 0, 100)    # baseline shift

    # update shared state with smoothing
    alpha = 0.35
    state['blink_rate'] = (1-alpha)*state.get('blink_rate',0.0) + alpha*blink_norm
    state['head_jitter'] = (1-alpha)*state.get('head_jitter',0.0) + alpha*jitter_norm
    state['mouth_motion'] = (1-alpha)*state.get('mouth_motion',0.0) + alpha*mouth_norm
    state['eye_brightness'] = (1-alpha)*state.get('eye_brightness',0.0) + alpha*eye_bright_norm
    state['skin_tone_shift'] = (1-alpha)*state.get('skin_tone_shift',0.0) + alpha*skin_shift_norm

    # stress index heuristic: weighted sum of signals
    stress = 0.0
    stress += 0.35 * state['head_jitter']
    stress += 0.30 * (100.0 - state['eye_brightness'])   # darker eyes -> stress proxy
    stress += 0.20 * state['mouth_motion']
    stress += 0.15 * state['skin_tone_shift']
    stress = np.clip(stress, 0.0, 100.0)
    state['stress_index'] = float( (1-alpha)*state.get('stress_index',0.0) + alpha*stress )

    # lie probability heuristic: combines stress + low symmetry of blink behavior + sudden jitter
    lie_prob = 0.0
    # base on stress
    lie_prob += 0.6 * state['stress_index']
    # if blink rate too low or too high (extremes) increase suspicion
    if state['blink_rate'] < 10 or state['blink_rate'] > 70:
        lie_prob += 10.0
    # sudden head jitter increases probability
    if jitter_norm > 40:
        lie_prob += 8.0
    # mouth_motion (fake smile tension) impacts
    if state['mouth_motion'] > 30:
        lie_prob += 6.0

    lie_prob = np.clip(lie_prob, 0.0, 100.0)
    state['lie_probability'] = float( (1-alpha)*state.get('lie_probability',0.0) + alpha*lie_prob )

    state['last_update'] = time.time()

    # For diagnostics return the face bounding box and small metrics
    return {
        "face_box": (int(x),int(y),int(fw),int(fh)),
        "blink_rate": state['blink_rate'],
        "head_jitter": state['head_jitter'],
        "mouth_motion": state['mouth_motion'],
        "eye_brightness": state['eye_brightness'],
        "skin_tone_shift": state['skin_tone_shift'],
        "stress_index": state['stress_index'],
        "lie_probability": state['lie_probability']
    }
