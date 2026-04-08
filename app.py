# app.py
from flask import Flask, Response, render_template, jsonify
import threading, time
import cv2
from detector import analyze_face_from_frame, state

app = Flask(__name__)

# Global video capture (0 = default webcam)
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Could not open webcam. Make sure your camera is free and available.")

# frame processing thread lock
lock = threading.Lock()

def gen_frames():
    """
    Generator that yields MJPEG frames for Flask streaming.
    Also calls analyze_face_from_frame on each frame (or every Nth frame).
    """
    frame_counter = 0
    while True:
        success, frame = cap.read()
        if not success:
            break
        # optionally resize for speed
        frame_small = cv2.resize(frame, (640, int(frame.shape[0] * 640/frame.shape[1])))
        # analyze every 3rd frame for performance
        if frame_counter % 3 == 0:
            try:
                analyze_face_from_frame(frame_small)
            except Exception as e:
                # don't crash streaming on analyze errors
                print("analyze error:", e)
        frame_counter += 1

        # overlay simple HUD: show lie_probability
        prob = state.get('lie_probability', 0.0)
        text = f"LieProb: {prob:.1f}%  Stress: {state.get('stress_index',0.0):.1f}%"
        cv2.putText(frame_small, text, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)
        # encode JPEG
        ret, buffer = cv2.imencode('.jpg', frame_small)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    # return latest metrics
    return jsonify({
        'blink_rate': round(state.get('blink_rate',0.0),1),
        'head_jitter': round(state.get('head_jitter',0.0),2),
        'mouth_motion': round(state.get('mouth_motion',0.0),2),
        'eye_brightness': round(state.get('eye_brightness',0.0),1),
        'skin_tone_shift': round(state.get('skin_tone_shift',0.0),1),
        'stress_index': round(state.get('stress_index',0.0),1),
        'lie_probability': round(state.get('lie_probability',0.0),1),
        'last_update': state.get('last_update', 0.0)
    })

def cleanup():
    try:
        cap.release()
    except:
        pass

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    finally:
        cleanup()