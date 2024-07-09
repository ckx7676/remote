import socket
import struct
import threading
import cv2
import numpy as np
import pickle
from pynput import mouse, keyboard
import win32gui
import time

server_ip = '192.168.229.135'  # Replace with actual server IP address
screenshot_port = 5000
events_port = 5001
stop = False

# Setup client sockets
screenshot_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
screenshot_socket.connect((server_ip, screenshot_port))

events_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
events_socket.connect((server_ip, events_port))
pre_rel_x, pre_rel_y = 0, 0


# Function to receive and display image data
def receive_data(sock):
    global stop
    while True:
        try:
            img_data_len = struct.unpack('>I', sock.recv(4))[0]
            # print(img_data_len)
            img_data = b''
            while len(img_data) < img_data_len:
                img_data += sock.recv(img_data_len - len(img_data))
            # Send ACK to server
            sock.sendall(b'\x06')  # ASCII ACK
            img_array = np.frombuffer(img_data, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            cv2.imshow("Screen", img)
            cv2.waitKey(100)
            if cv2.getWindowProperty("Screen", cv2.WND_PROP_VISIBLE) < 1:
                break
        except Exception as e:
            print(f"Error in receive_data: {e}")
            break
    stop = True


# Function to send event data to server
def send_event(sock, event_data):
    try:
        # print(event_data)
        event_data_serialized = pickle.dumps(event_data)
        event_data_len = struct.pack('>I', len(event_data_serialized))
        sock.sendall(event_data_len + event_data_serialized)
        # Wait for ACK from server
        ack = sock.recv(1)
        if ack != b'\x06':  # ASCII ACK
            raise Exception("Failed to receive ACK from server")
    except Exception as e:
        print(f"Error in send_event: {e}")


# Get the position and size of the "HighGUI class" child window
def get_child_window_info(parent_window_name, child_window_class):
    hwnd_parent = win32gui.FindWindow(None, parent_window_name)
    hwnd_child = None
    if hwnd_parent:
        def callback(hwnd, hwnds):
            if win32gui.GetClassName(hwnd) == child_window_class:
                hwnds.append(hwnd)
            return True

        hwnds = []
        win32gui.EnumChildWindows(hwnd_parent, callback, hwnds)
        if hwnds:
            hwnd_child = hwnds[0]
    if hwnd_child:
        rect = win32gui.GetWindowRect(hwnd_child)
        x, y, w, h = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
        return x, y, w, h
    return None, None, None, None


# Check if "screen" window is in the foreground
def is_screen_window_active():
    hwnd_foreground = win32gui.GetForegroundWindow()
    hwnd_screen = win32gui.FindWindow(None, "Screen")
    return hwnd_foreground == hwnd_screen


# Listener functions for mouse and keyboard events
def on_click(x, y, button, pressed):
    if is_screen_window_active():
        screen_x, screen_y, screen_width, screen_height = get_child_window_info("Screen", "HighGUI class")
        if screen_x is not None and screen_y is not None:
            rel_x = round((x - screen_x) / screen_width, 4)
            rel_y = round((y - screen_y) / screen_height, 4)
            if 0 <= rel_x <= 1 and 0 <= rel_y <= 1:
                button_code = 1 if button == mouse.Button.left else 2 if button == mouse.Button.middle else 3
                event_data = {'event_type': 1, 'rel_x': rel_x, 'rel_y': rel_y, 'button_code': button_code,
                              'pressed': pressed}
                send_event(events_socket, event_data)


def on_move(x, y):
    global pre_rel_x, pre_rel_y
    if is_screen_window_active():
        screen_x, screen_y, screen_width, screen_height = get_child_window_info("Screen", "HighGUI class")
        if screen_x is not None and screen_y is not None:
            rel_x = round((x - screen_x) / screen_width, 4)
            rel_y = round((y - screen_y) / screen_height, 4)
            if 0 <= rel_x <= 1 and 0 <= rel_y <= 1:
                if abs(rel_x - pre_rel_x) > 0.005 or abs(rel_y - pre_rel_y) > 0.01:
                    pre_rel_x = rel_x
                    pre_rel_y = rel_y
                    event_data = {'event_type': 4, 'rel_x': rel_x, 'rel_y': rel_y}
                    send_event(events_socket, event_data)


def on_scroll(x, y, dx, dy):
    if is_screen_window_active():
        screen_x, screen_y, screen_width, screen_height = get_child_window_info("Screen", "HighGUI class")
        if screen_x is not None and screen_y is not None:
            rel_x = round((x - screen_x) / screen_width, 4)
            rel_y = round((y - screen_y) / screen_height, 4)
            if 0 <= rel_x <= 1 and 0 <= rel_y <= 1:
                event_data = {'event_type': 5, 'rel_x': rel_x, 'rel_y': rel_y, 'dx': dx, 'dy': dy}
                send_event(events_socket, event_data)


def on_key_press(key):
    if is_screen_window_active():
        try:
            event_data = {'event_type': 2, 'vk': key.vk} if hasattr(key, 'vk') else {'event_type': 2,
                                                                                     'vk': key.value.vk}
            send_event(events_socket, event_data)
        except Exception as e:
            print(f"Error in on_key_press: {e}")


def on_key_release(key):
    if is_screen_window_active():
        try:
            event_data = {'event_type': 3, 'vk': key.vk} if hasattr(key, 'vk') else {'event_type': 3,
                                                                                     'vk': key.value.vk}
            send_event(events_socket, event_data)
        except Exception as e:
            print(f"Error in on_key_release: {e}")


# Start threads for receiving data and listening to events
receive_thread = threading.Thread(target=receive_data, args=(screenshot_socket,))
receive_thread.start()
mouse_listener = mouse.Listener(on_click=on_click, on_move=on_move, on_scroll=on_scroll)
keyboard_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
mouse_listener.start()
keyboard_listener.start()
while not stop:
    time.sleep(0.1)
mouse_listener.stop()
keyboard_listener.stop()
screenshot_socket.close()
events_socket.close()
