from machine import Pin, UART
import time

uart = UART(
    0,
    baudrate=115200,
    tx=Pin(0),
    rx=Pin(1)
)

led = Pin("LED", Pin.OUT)

print("Camera UART blink test started.")
print("RED -> 1 blink, GREEN -> 2 blinks")
print("If the same color keeps arriving, it will not blink again.")

buffer = b""

last_seen_color = "NONE"
armed = True


def blink(count):
    for _ in range(count):
        led.value(1)
        time.sleep(0.12)
        led.value(0)
        time.sleep(0.12)


def handle_message(msg):
    global last_seen_color, armed

    print("RECEIVED:", msg)

    if msg.startswith("NONE"):
        last_seen_color = "NONE"
        armed = True
        return

    if msg.startswith("RED"):
        color = "RED"
        blink_count = 1

    elif msg.startswith("GREEN"):
        color = "GREEN"
        blink_count = 2

    else:
        return

    # Blink only when a new object is detected.
    if armed or color != last_seen_color:
        print(color, "detected -> blink:", blink_count)
        blink(blink_count)

        last_seen_color = color
        armed = False
    else:
        print(color, "is still visible, no repeated blink.")


while True:
    if uart.any():
        data = uart.read()

        if data:
            buffer += data

            # Keep the buffer from growing too large.
            if len(buffer) > 200:
                buffer = buffer[-100:]

            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)

                try:
                    msg = line.decode("utf-8").strip()
                    handle_message(msg)

                except Exception as e:
                    print("Decode error:", e)
                    print("Raw data:", line)

    time.sleep(0.02)
