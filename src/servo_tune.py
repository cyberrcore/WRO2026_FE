from machine import I2C, PWM, Pin
import time

# =====================================================
# Pins
# =====================================================

SERVO_PIN = 14

SDA_PIN = 4
SCL_PIN = 5


# =====================================================
# Servo tune settings
# =====================================================

SERVO_MIN = 30
SERVO_MAX = 100
SERVO_CENTER = 65

SERVO_REVERSE = True

# How long should PID run?
PID_START_TIME_MS = 3000

# Servo angle to test after PID finishes.
TEST_SERVO_ANGLE = 80

# Keep the servo at the test angle.
HOLD_AFTER_TEST = True


# =====================================================
# PID settings
# =====================================================

KP = 1.8
KI = 0.00
KD = 0.25


# =====================================================
# Servo
# =====================================================

servo = PWM(Pin(SERVO_PIN))
servo.freq(50)


def set_servo_angle(angle):
    angle = max(SERVO_MIN, min(SERVO_MAX, angle))

    min_us = 500
    max_us = 2500

    pulse_us = min_us + (angle / 180) * (max_us - min_us)
    duty = int((pulse_us / 20000) * 65535)

    servo.duty_u16(duty)


def servo_center():
    set_servo_angle(SERVO_CENTER)


def set_servo_pid(correction):
    if SERVO_REVERSE:
        servo_angle = SERVO_CENTER - correction
    else:
        servo_angle = SERVO_CENTER + correction

    servo_angle = max(SERVO_MIN, min(SERVO_MAX, servo_angle))
    set_servo_angle(servo_angle)

    return servo_angle


# =====================================================
# MPU9250
# =====================================================

i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)

devices = i2c.scan()
print("I2C devices:", devices)

MPU_ADDR = 0x68

if MPU_ADDR not in devices:
    print("0x68 not found, trying 0x69...")
    MPU_ADDR = 0x69

if MPU_ADDR not in devices:
    print("MPU9250 not found. Check the wiring.")
    while True:
        servo_center()
        time.sleep(1)

# MPU wake up
i2c.writeto_mem(MPU_ADDR, 0x6B, b"\x00")
time.sleep(0.05)

# Gyro +-250 dps
i2c.writeto_mem(MPU_ADDR, 0x1B, b"\x00")

# Accel +-2g
i2c.writeto_mem(MPU_ADDR, 0x1C, b"\x00")


def read_word(reg):
    high = i2c.readfrom_mem(MPU_ADDR, reg, 1)[0]
    low = i2c.readfrom_mem(MPU_ADDR, reg + 1, 1)[0]

    value = (high << 8) | low

    if value > 32767:
        value -= 65536

    return value


def read_gyro():
    gx_raw = read_word(0x43)
    gy_raw = read_word(0x45)
    gz_raw = read_word(0x47)

    gx = gx_raw / 131.0
    gy = gy_raw / 131.0
    gz = gz_raw / 131.0

    return gx, gy, gz


def calibrate_gyro(samples=400):
    print("Gyro calibration starting. Keep the robot still...")

    gx_sum = 0
    gy_sum = 0
    gz_sum = 0

    for _ in range(samples):
        gx, gy, gz = read_gyro()

        gx_sum += gx
        gy_sum += gy
        gz_sum += gz

        time.sleep(0.004)

    print("Calibration complete.")

    return gx_sum / samples, gy_sum / samples, gz_sum / samples


# =====================================================
# PID
# =====================================================

integral = 0.0
last_error = 0.0


def pid_control(error, dt):
    global integral, last_error

    integral += error * dt
    integral = max(-50, min(50, integral))

    derivative = (error - last_error) / dt if dt > 0 else 0

    output = (KP * error) + (KI * integral) + (KD * derivative)

    last_error = error

    return output


def reset_pid():
    global integral, last_error

    integral = 0.0
    last_error = 0.0


# =====================================================
# Main program
# =====================================================

yaw = 0.0
target_yaw = 0.0

try:
    servo_center()
    time.sleep(0.5)

    gx_bias, gy_bias, gz_bias = calibrate_gyro()

    print("SERVO TUNE MODE STARTED")
    print("First it will hold straight with PID.")
    print("Then it will move to TEST_SERVO_ANGLE.")
    print("SERVO_MIN:", SERVO_MIN)
    print("SERVO_MAX:", SERVO_MAX)
    print("SERVO_CENTER:", SERVO_CENTER)
    print("TEST_SERVO_ANGLE:", TEST_SERVO_ANGLE)

    start_ms = time.ticks_ms()
    last_time = time.ticks_us()

    mode = "PID"

    while True:
        now_us = time.ticks_us()
        dt = time.ticks_diff(now_us, last_time) / 1000000.0
        last_time = now_us

        if dt <= 0:
            dt = 0.001

        gx, gy, gz = read_gyro()
        gz_corrected = gz - gz_bias

        if abs(gz_corrected) < 0.4:
            gz_corrected = 0

        yaw += gz_corrected * dt

        if mode == "PID":
            error = target_yaw - yaw
            correction = pid_control(error, dt)

            servo_angle = set_servo_pid(correction)

            if time.ticks_diff(time.ticks_ms(), start_ms) >= PID_START_TIME_MS:
                print("PID complete.")
                print("Switching to fixed servo angle:", TEST_SERVO_ANGLE)

                reset_pid()
                mode = "TEST_ANGLE"

        elif mode == "TEST_ANGLE":
            set_servo_angle(TEST_SERVO_ANGLE)

            if HOLD_AFTER_TEST:
                pass

        print(
            "Mode:", mode,
            "| Yaw:", round(yaw, 2),
            "| TestAngle:", TEST_SERVO_ANGLE
        )

        time.sleep_ms(50)

except KeyboardInterrupt:
    print("Program stopped.")

finally:
    servo_center()
