import cv2
import torch
import numpy as np
import asyncio
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod

# YOLOv5 Configuration
MODEL_PATH = 'yolov5s.pt'  # Path to YOLOv5 model (use yolov5s.pt for a small pre-trained model)
CONFIDENCE_THRESHOLD = 0.5  # Confidence threshold for object detection
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# Initialize YOLOv5 model
model = torch.hub.load('ultralytics/yolov5', 'custom', path=MODEL_PATH).to(DEVICE)

# Initialize WebRTC connection (for robotic commands)
conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)

# Function to process detections and respond to commands
def process_detections(detections, frame):
    for detection in detections:
        x_min, y_min, x_max, y_max, confidence, class_id = detection
        class_name = model.names[int(class_id)]

        # Draw bounding box and label on the frame
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        cv2.putText(frame, f'{class_name} {confidence:.2f}', (x_min, y_min - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Respond to specific object detections
        if class_name == "person":
            asyncio.run(send_command_to_robot("WaveHand"))
        elif class_name == "cup":
            asyncio.run(send_command_to_robot("PickUpCup"))

# Function to send commands to the robot
async def send_command_to_robot(command):
    print(f"Sending command: {command}")
    await conn.datachannel.pub_sub.publish_request_new(
        "rt/api/sport/request",
        {"header": {"identity": {"api_id": 1008}}, "parameter": {"action": command}}
    )

# Video processing loop
def video_processing():
    cap = cv2.VideoCapture(0)  # Open default camera

    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Convert frame to RGB and process with YOLOv5
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = model(frame_rgb)

        # Extract detections
        detections = []
        for *box, confidence, class_id in results.xyxy[0].cpu().numpy():
            if confidence >= CONFIDENCE_THRESHOLD:
                detections.append((*map(int, box), confidence, class_id))

        # Process detections and display results
        process_detections(detections, frame)
        cv2.imshow('Object Recognition', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

# Main function to connect to the robot and start video processing
async def main():
    await conn.connect()
    print("Connected to robot. Starting video processing...")
    video_processing()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user.")
