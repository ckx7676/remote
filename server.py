import socket
import struct
import threading
import d3dshot
import cv2
import pickle
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key, KeyCode

d3d = d3dshot.create(capture_output="numpy")
mouse_controller = MouseController()
keyboard_controller = KeyboardController()


def capture_screen():
    screenshot = d3d.screenshot()
    _, jpg = cv2.imencode('.jpg', screenshot)
    return jpg.tobytes()


# Function to handle screenshot sending
def handle_screenshot(client_socket):
    while True:
        try:
            img_data = capture_screen()
            img_data_len = len(img_data)
            client_socket.sendall(struct.pack('>I', img_data_len) + img_data)
            # Wait for ACK from client
            ack = client_socket.recv(1)
            if ack != b'\x06':  # ASCII ACK
                raise Exception("Failed to receive ACK from client")
        except Exception as e:
            print(f"Error in handle_screenshot: {e}")
            break


# Function to handle keyboard/mouse events
def handle_events(client_socket):
    screen_width, screen_height = d3d.screenshot().shape[1], d3d.screenshot().shape[0]
    while True:
        try:
            # Receive event data length
            event_data_len = struct.unpack('>I', client_socket.recv(4))[0]
            # Receive event data
            event_data_serialized = b''
            while len(event_data_serialized) < event_data_len:
                event_data_serialized += client_socket.recv(event_data_len - len(event_data_serialized))
            # Send ACK to client
            client_socket.sendall(b'\x06')  # ASCII ACK

            event_data = pickle.loads(event_data_serialized)
            if event_data['event_type'] == 1:  # Mouse click event
                rel_x, rel_y = event_data['rel_x'], event_data['rel_y']
                button_code = event_data['button_code']
                pressed = event_data['pressed']
                abs_x, abs_y = int(rel_x * screen_width), int(rel_y * screen_height)
                mouse_controller.position = (abs_x, abs_y)
                button = Button.left if button_code == 1 else Button.middle if button_code == 2 else Button.right
                if pressed:
                    mouse_controller.press(button)
                else:
                    mouse_controller.release(button)
            elif event_data['event_type'] == 2:  # Key press event
                vk = event_data['vk']
                key = KeyCode.from_vk(vk)
                keyboard_controller.press(key)
            elif event_data['event_type'] == 3:  # Key release event
                vk = event_data['vk']
                key = KeyCode.from_vk(vk)
                keyboard_controller.release(key)
            elif event_data['event_type'] == 4:  # Mouse move event
                rel_x, rel_y = event_data['rel_x'], event_data['rel_y']
                abs_x, abs_y = int(rel_x * screen_width), int(rel_y * screen_height)
                mouse_controller.position = (abs_x, abs_y)
            elif event_data['event_type'] == 5:  # Mouse scroll event
                rel_x, rel_y, dx, dy = event_data['rel_x'], event_data['rel_y'], event_data['dx'], event_data['dy']
                abs_x, abs_y = int(rel_x * screen_width), int(rel_y * screen_height)
                mouse_controller.position = (abs_x, abs_y)
                mouse_controller.scroll(dx, dy)
        except Exception as e:
            print(f"Error in handle_events: {e}")
            break


# Start server and listen for connections
def start_server():
    screenshot_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    screenshot_server.bind(('0.0.0.0', 5000))
    screenshot_server.listen(5)
    print("Screenshot server listening on port 5000...")

    events_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    events_server.bind(('0.0.0.0', 5001))
    events_server.listen(5)
    print("Events server listening on port 5001...")

    while True:
        screenshot_client, _ = screenshot_server.accept()
        events_client, _ = events_server.accept()
        print("Client connected")

        screenshot_thread = threading.Thread(target=handle_screenshot, args=(screenshot_client,))
        events_thread = threading.Thread(target=handle_events, args=(events_client,))

        screenshot_thread.start()
        events_thread.start()


if __name__ == "__main__":
    start_server()
