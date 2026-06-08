from machine import Pin, PWM, I2C, UART, time_pulse_us
import time

# =====================================================
# LOG SİSTEMİ
# =====================================================

LOG_ENABLED = True
LOG_FILE = "run_log.txt"

last_logged_mode = ""
last_snapshot_log_time = 0


def reset_log():
    if not LOG_ENABLED:
        return

    try:
        with open(LOG_FILE, "w") as f:
            f.write("=== WRO RUN LOG START ===\n")
            f.write("time_ms, event\n")
    except Exception as e:
        print("LOG reset hata:", e)


def log_event(text):
    if not LOG_ENABLED:
        return

    try:
        with open(LOG_FILE, "a") as f:
            f.write(str(time.ticks_ms()) + ", " + str(text) + "\n")
    except Exception as e:
        print("LOG hata:", e)


def log_mode_change(new_mode, extra=""):
    global last_logged_mode

    if new_mode != last_logged_mode:
        last_logged_mode = new_mode

        if extra:
            log_event("MODE -> " + str(new_mode) + " | " + str(extra))
        else:
            log_event("MODE -> " + str(new_mode))


def log_debug_snapshot(mode, lap_count, corner_count, cam_type, cam_x, cam_bottom, cam_count, distance, yaw, active_color):
    dist_text = "None" if distance is None else str(round(distance, 1))

    text = (
        "SNAPSHOT"
        + " | Mode=" + str(mode)
        + " | Lap=" + str(lap_count)
        + " | Corner=" + str(corner_count)
        + " | Cam=" + str(cam_type)
        + " | X=" + str(cam_x)
        + " | Bottom=" + str(cam_bottom)
        + " | Count=" + str(cam_count)
        + " | Dist=" + dist_text
        + " | Yaw=" + str(round(yaw, 2))
        + " | Active=" + str(active_color)
    )

    log_event(text)


# =====================================================
# PINLER
# =====================================================

SERVO_PIN = 15

PWMA_PIN = 16
AIN2_PIN = 17
AIN1_PIN = 18
STBY_PIN = 19

SDA_PIN = 4
SCL_PIN = 5

TRIG_PIN = 10
ECHO_PIN = 11

UART_ID = 0
UART_TX_PIN = 0
UART_RX_PIN = 1

# =====================================================
# AYARLAR
# =====================================================

SERVO_MIN = 50
SERVO_MAX = 80
SERVO_CENTER = 65

# Eğer LEFT yazınca sağa dönüyorsa bu ikisini ters çevir:
# SERVO_LEFT = SERVO_MIN
# SERVO_RIGHT = SERVO_MAX
SERVO_LEFT = SERVO_MAX
SERVO_RIGHT = SERVO_MIN

# Eğer renk takip yönü tersse True yap
CAMERA_STEER_REVERSE = False

# Eğer düz gitme PID yönü tersse bunu True/False değiştir
GYRO_STEER_REVERSE = False

# Köşelerde dönüş yönü
CORNER_DIRECTION = "LEFT"   # "RIGHT" veya "LEFT"

# Tur sayma
REQUIRED_LAPS = 3
CORNERS_PER_LAP = 4

# Hızlar
MOTOR_SPEED_FOLLOW = 65
MOTOR_SPEED_COLOR = 48
MOTOR_SPEED_LOST = 43
MOTOR_SPEED_PASS = 42
MOTOR_SPEED_RECOVER = 40
MOTOR_SPEED_SLOW = 40
MOTOR_SPEED_TURN = 57

# US100
SLOW_DISTANCE_CM = 60
TURN_DISTANCE_CM = 45

# Çok yakın güvenlik filtresi
STOP_DISTANCE_CM = 6
VERY_CLOSE_COUNT_LIMIT = 5
START_DISTANCE_IGNORE_MS = 1500

# 3.5 cm gibi sahte okumaları çöpe at
MIN_VALID_DISTANCE_CM = 5
MAX_VALID_DISTANCE_CM = 450

# Köşe dönüşü
TURN_ANGLE = 90
TURN_TOLERANCE = 5

# Kamera bilgisi
CAM_W = 160
CAM_CENTER = 80

# RED sağından geçilecek:
# Kırmızıyı görüntüde solda tutarsak robot sağından geçer.
RED_TARGET_X = 48

# GREEN solundan geçilecek:
# Yeşili görüntüde sağda tutarsak robot solundan geçer.
GREEN_TARGET_X = 112

# Kamera filtreleri
CAM_BOTTOM_NEAR = 50
CAM_COUNT_MIN = 18

# Obstacle state geçişleri
FOLLOW_COLOR_MIN_TIME_MS = 450
FOLLOW_COLOR_MAX_TIME_MS = 1600

LOST_COLOR_FRAMES_TO_ENTER = 3
LOST_COLOR_FRAMES_TO_PASS = 8
LOST_COLOR_MAX_TIME_MS = 650

PASS_COLOR_TIME_MS = 520
RECOVER_MAX_TIME_MS = 1300

# Bileşik parkur
CHAIN_TIME_WINDOW_MS = 3200
CHAIN_PASS_EXTRA_MS = 180
CHAIN_PASS_BONUS = 0.18

# US100 renk gördükten sonra bir süre köşe tetiklemesin
TURN_IGNORE_AFTER_COLOR_MS = 1800
TURN_IGNORE_AFTER_TURN_MS = 700
COLOR_IGNORE_AFTER_RECOVER_MS = 250

# Ana düz gitme PID
KP_HEADING = 2.4
KI_HEADING = 0.00
KD_HEADING = 0.35

# Düz giderken servo hareketini güçlendirir
HEADING_CORRECTION_DIVIDER = 14.0

# Küçük correction varsa servo aktif merkeze döner
MIN_STEER_DEADBAND = 0.03

# Renk takip kontrol ağırlıkları
K_CAM_FOLLOW = 0.018
K_HEADING_IN_COLOR = 0.018

# Renk kaybolunca son renge göre hafif arama biası
LOST_BIAS_RED = 0.28
LOST_BIAS_GREEN = -0.28

# Pass sırasında daha büyük geçiş biası
PASS_BIAS_RED = 0.58
PASS_BIAS_GREEN = -0.58

# Recover heading
RECOVER_TOLERANCE = 5
RECOVER_HEADING_GAIN = 0.045

# =====================================================
# UART - ESP32-CAM
# =====================================================

uart = UART(
    UART_ID,
    baudrate=115200,
    tx=Pin(UART_TX_PIN),
    rx=Pin(UART_RX_PIN)
)

buffer = b""

last_cam_type = "NONE"
last_cam_x = -1
last_cam_bottom = -1
last_cam_count = 0
last_cam_time = time.ticks_ms()


def clear_uart_buffer():
    global buffer
    buffer = b""
    while uart.any():
        uart.read()


def read_camera_data():
    """
    ESP32-CAM format:
    RED,cx,bottomY,count
    GREEN,cx,bottomY,count
    NONE
    """
    global buffer
    global last_cam_type, last_cam_x, last_cam_bottom, last_cam_count, last_cam_time

    detected = "NONE"

    while uart.any():
        data = uart.read()

        if data:
            buffer += data

            if len(buffer) > 500:
                buffer = buffer[-250:]

            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)

                try:
                    msg = line.decode("utf-8").strip()

                    if msg.startswith("RED"):
                        parts = msg.split(",")

                        color = "RED"
                        cx = int(parts[1]) if len(parts) > 1 else -1
                        bottom = int(parts[2]) if len(parts) > 2 else -1
                        count = int(parts[3]) if len(parts) > 3 else 0

                        last_cam_type = color
                        last_cam_x = cx
                        last_cam_bottom = bottom
                        last_cam_count = count
                        last_cam_time = time.ticks_ms()

                        if bottom >= CAM_BOTTOM_NEAR and count >= CAM_COUNT_MIN:
                            detected = color

                    elif msg.startswith("GREEN"):
                        parts = msg.split(",")

                        color = "GREEN"
                        cx = int(parts[1]) if len(parts) > 1 else -1
                        bottom = int(parts[2]) if len(parts) > 2 else -1
                        count = int(parts[3]) if len(parts) > 3 else 0

                        last_cam_type = color
                        last_cam_x = cx
                        last_cam_bottom = bottom
                        last_cam_count = count
                        last_cam_time = time.ticks_ms()

                        if bottom >= CAM_BOTTOM_NEAR and count >= CAM_COUNT_MIN:
                            detected = color

                    elif msg.startswith("NONE"):
                        last_cam_type = "NONE"
                        last_cam_x = -1
                        last_cam_bottom = -1
                        last_cam_count = 0
                        last_cam_time = time.ticks_ms()

                    elif msg.startswith("ESP32_CAM_READY"):
                        print("ESP32-CAM hazir")
                        log_event("ESP32-CAM hazir")

                except Exception as e:
                    print("UART parse hata:", e)
                    log_event("UART parse hata: " + str(e))

    return detected


# =====================================================
# SERVO
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


def servo_left(strength=1.0):
    strength = max(0.0, min(1.0, strength))
    angle = SERVO_CENTER + (SERVO_LEFT - SERVO_CENTER) * strength
    set_servo_angle(angle)


def servo_right(strength=1.0):
    strength = max(0.0, min(1.0, strength))
    angle = SERVO_CENTER + (SERVO_RIGHT - SERVO_CENTER) * strength
    set_servo_angle(angle)


def set_steering_correction(correction):
    """
    correction:
        + değer = sağa direksiyon
        - değer = sola direksiyon
    """
    correction = max(-1.0, min(1.0, correction))

    # Çok küçük hata varsa servo aktif merkeze dönsün
    if abs(correction) < MIN_STEER_DEADBAND:
        servo_center()
        return

    if correction > 0:
        servo_right(correction)
    else:
        servo_left(-correction)


def steer_corner():
    if CORNER_DIRECTION == "RIGHT":
        servo_right(1.0)
    else:
        servo_left(1.0)


# =====================================================
# MOTOR - TB6612FNG
# =====================================================

pwma = PWM(Pin(PWMA_PIN))
pwma.freq(1000)

ain2 = Pin(AIN2_PIN, Pin.OUT)
ain1 = Pin(AIN1_PIN, Pin.OUT)
stby = Pin(STBY_PIN, Pin.OUT)


def motor_forward(speed):
    speed = max(0, min(100, speed))

    stby.value(1)
    ain1.value(1)
    ain2.value(0)

    duty = int((speed / 100) * 65535)
    pwma.duty_u16(duty)


def motor_stop():
    pwma.duty_u16(0)
    ain1.value(0)
    ain2.value(0)
    stby.value(0)


# =====================================================
# US100
# =====================================================

trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)

trig.value(0)
time.sleep(0.05)


def read_distance_once():
    trig.value(0)
    time.sleep_us(2)

    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    try:
        duration = time_pulse_us(echo, 1, 30000)
    except OSError:
        return None

    if duration <= 0:
        return None

    distance_cm = duration / 58.0

    if distance_cm < MIN_VALID_DISTANCE_CM or distance_cm > MAX_VALID_DISTANCE_CM:
        return None

    return distance_cm


def read_distance_cm(samples=3):
    values = []

    for _ in range(samples):
        d = read_distance_once()
        if d is not None:
            values.append(d)
        time.sleep(0.004)

    if len(values) == 0:
        return None

    values.sort()
    return values[len(values) // 2]


# =====================================================
# MPU9250
# =====================================================

i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=400000)

devices = i2c.scan()
print("I2C cihazlari:", devices)

MPU_ADDR = 0x68

if MPU_ADDR not in devices:
    print("0x68 bulunamadi, 0x69 deneniyor...")
    MPU_ADDR = 0x69

i2c.writeto_mem(MPU_ADDR, 0x6B, b'\x00')
time.sleep(0.05)

# Gyro +-250 deg/s
i2c.writeto_mem(MPU_ADDR, 0x1B, b'\x00')

# Accel +-2g
i2c.writeto_mem(MPU_ADDR, 0x1C, b'\x00')


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
    print("Gyro kalibrasyonu basliyor. Robotu oynatma...")
    log_event("Gyro kalibrasyonu basladi")

    gx_sum = 0
    gy_sum = 0
    gz_sum = 0

    for _ in range(samples):
        gx, gy, gz = read_gyro()
        gx_sum += gx
        gy_sum += gy
        gz_sum += gz
        time.sleep(0.004)

    print("Kalibrasyon bitti.")
    log_event("Gyro kalibrasyonu bitti")

    return gx_sum / samples, gy_sum / samples, gz_sum / samples


# =====================================================
# PID - ANA HEADING
# =====================================================

integral = 0.0
last_error = 0.0


def pid_heading(error, dt):
    global integral, last_error

    integral += error * dt
    integral = max(-50, min(50, integral))

    derivative = (error - last_error) / dt if dt > 0 else 0

    output = (KP_HEADING * error) + (KI_HEADING * integral) + (KD_HEADING * derivative)

    last_error = error

    return output


def reset_pid():
    global integral, last_error
    integral = 0.0
    last_error = 0.0


def heading_error_to_target(target, current):
    return target - current


def compute_color_correction(color, cam_x, yaw_error, chain=False):
    """
    Repo mantığı:
    error = camera_error + heading_error karışımı.

    RED:
        kırmızıyı görüntüde solda tut.
    GREEN:
        yeşili görüntüde sağda tut.
    """

    if color == "RED":
        target_x = RED_TARGET_X
    elif color == "GREEN":
        target_x = GREEN_TARGET_X
    else:
        return 0.0

    cam_error = cam_x - target_x

    correction = cam_error * K_CAM_FOLLOW

    if GYRO_STEER_REVERSE:
        correction -= yaw_error * K_HEADING_IN_COLOR
    else:
        correction += yaw_error * K_HEADING_IN_COLOR

    if CAMERA_STEER_REVERSE:
        correction = -correction

    if chain:
        correction *= 1.15

    return max(-1.0, min(1.0, correction))


# =====================================================
# ANA PROGRAM DEĞİŞKENLERİ
# =====================================================

yaw = 0.0
target_yaw = 0.0
turn_start_yaw = 0.0

mode = "FOLLOW"

active_color = "NONE"
last_color = "NONE"

color_start_yaw = 0.0
color_start_time = 0
lost_start_time = 0
pass_start_time = 0
recover_start_time = 0

no_color_count = 0

last_obstacle_color = "NONE"
last_obstacle_time = 0
chain_active = False
pass_duration = PASS_COLOR_TIME_MS

color_ignore_until = 0
turn_ignore_until = 0

corner_count = 0
lap_count = 0
loop_count = 0

very_close_count = 0
program_start_ms = 0

# =====================================================
# ANA PROGRAM
# =====================================================

try:
    motor_stop()
    servo_center()
    time.sleep(0.2)

    reset_log()
    log_event("Program basladi")

    gx_bias, gy_bias, gz_bias = calibrate_gyro()

    clear_uart_buffer()

    last_time = time.ticks_us()
    program_start_ms = time.ticks_ms()

    print("REPO MANTIGI WRO OBSTACLE MODU BASLADI")
    print("RED -> sagindan gec: red hedef x =", RED_TARGET_X)
    print("GREEN -> solundan gec: green hedef x =", GREEN_TARGET_X)
    print("Kose yonu:", CORNER_DIRECTION)

    log_event("Repo mantigi obstacle modu basladi")
    log_event("RED_TARGET_X=" + str(RED_TARGET_X) + " GREEN_TARGET_X=" + str(GREEN_TARGET_X))
    log_event("CORNER_DIRECTION=" + str(CORNER_DIRECTION))
    log_event(
        "US100 FILTER | MIN_VALID="
        + str(MIN_VALID_DISTANCE_CM)
        + " STOP="
        + str(STOP_DISTANCE_CM)
        + " COUNT_LIMIT="
        + str(VERY_CLOSE_COUNT_LIMIT)
        + " START_IGNORE_MS="
        + str(START_DISTANCE_IGNORE_MS)
    )
    log_event(
        "PID | KP="
        + str(KP_HEADING)
        + " KD="
        + str(KD_HEADING)
        + " DIV="
        + str(HEADING_CORRECTION_DIVIDER)
        + " GYRO_REVERSE="
        + str(GYRO_STEER_REVERSE)
    )

    log_mode_change("FOLLOW", "Init")

    while True:
        now_us = time.ticks_us()
        dt = time.ticks_diff(now_us, last_time) / 1000000.0
        last_time = now_us

        now_ms = time.ticks_ms()

        detected_color = read_camera_data()

        gx, gy, gz = read_gyro()
        gz_corrected = gz - gz_bias

        if abs(gz_corrected) < 0.4:
            gz_corrected = 0

        yaw += gz_corrected * dt

        distance = read_distance_cm(samples=3)

        yaw_error = heading_error_to_target(target_yaw, yaw)

        color_allowed = time.ticks_diff(now_ms, color_ignore_until) >= 0
        turn_allowed = time.ticks_diff(now_ms, turn_ignore_until) >= 0

        # =================================================
        # 3 TUR BİTİRME
        # =================================================

        if lap_count >= REQUIRED_LAPS:
            motor_stop()
            servo_center()
            print("BITTI! 3 TUR TAMAMLANDI.")
            log_event("BITTI | 3 TUR TAMAMLANDI")
            break

        # =================================================
        # ÇOK YAKIN GÜVENLİK - FİLTRELİ
        # =================================================

        startup_finished = time.ticks_diff(now_ms, program_start_ms) > START_DISTANCE_IGNORE_MS

        if distance is not None and distance < STOP_DISTANCE_CM and mode not in ("TURN", "FOLLOW_COLOR", "LOST_COLOR", "PASS_COLOR"):
            very_close_count += 1
        else:
            very_close_count = 0

        if startup_finished and very_close_count >= VERY_CLOSE_COUNT_LIMIT:
            motor_stop()
            servo_center()

            print("COK YAKIN! Filtreli guvenlik durusu.")
            log_event(
                "COK YAKIN DURUS FILTERED | Dist="
                + str(round(distance, 1))
                + " Count="
                + str(very_close_count)
                + " Mode="
                + str(mode)
            )

            time.sleep(0.08)
            continue

        # =================================================
        # FOLLOW - NORMAL ANA ROTA
        # =================================================

        if mode == "FOLLOW":

            # Öncelik 1: renkli obstacle
            if color_allowed and detected_color in ("RED", "GREEN"):
                active_color = detected_color
                last_color = detected_color
                color_start_yaw = yaw
                color_start_time = now_ms
                no_color_count = 0

                chain_active = (
                    last_obstacle_color != "NONE" and
                    last_obstacle_color != active_color and
                    time.ticks_diff(now_ms, last_obstacle_time) < CHAIN_TIME_WINDOW_MS
                )

                if chain_active:
                    pass_duration = PASS_COLOR_TIME_MS + CHAIN_PASS_EXTRA_MS
                else:
                    pass_duration = PASS_COLOR_TIME_MS

                turn_ignore_until = time.ticks_add(now_ms, TURN_IGNORE_AFTER_COLOR_MS)

                reset_pid()

                print("MODE -> FOLLOW_COLOR | Color:", active_color)
                log_mode_change(
                    "FOLLOW_COLOR",
                    "Color=" + str(active_color)
                    + " X=" + str(last_cam_x)
                    + " Bottom=" + str(last_cam_bottom)
                    + " Count=" + str(last_cam_count)
                    + " Chain=" + str(chain_active)
                )

                if chain_active:
                    print("BILESIK PARKUR AKTIF")
                    log_event("CHAIN ACTIVE | Last=" + str(last_obstacle_color) + " New=" + str(active_color))

                mode = "FOLLOW_COLOR"

            # Öncelik 2: köşe
            elif distance is not None and distance < TURN_DISTANCE_CM and turn_allowed:
                mode = "TURN"
                turn_start_yaw = yaw

                reset_pid()

                print("MODE -> TURN | Kose algilandi")
                print("Baslangic yaw:", round(turn_start_yaw, 2))
                log_mode_change("TURN", "Dist=" + str(round(distance, 1)) + " StartYaw=" + str(round(turn_start_yaw, 2)))

                steer_corner()
                motor_forward(MOTOR_SPEED_TURN)

            # Normal düz git
            else:
                if distance is not None and distance < SLOW_DISTANCE_CM and turn_allowed:
                    motor_speed = MOTOR_SPEED_SLOW
                else:
                    motor_speed = MOTOR_SPEED_FOLLOW

                motor_forward(motor_speed)

                correction = pid_heading(yaw_error, dt)

                if GYRO_STEER_REVERSE:
                    correction = -correction

                correction_norm = correction / HEADING_CORRECTION_DIVIDER

                # Servo her loopta aktif kontrol edilir
                set_steering_correction(correction_norm)

                if loop_count % 20 == 0:
                    print(
                        "FOLLOW PID",
                        "| yaw:", round(yaw, 2),
                        "| err:", round(yaw_error, 2),
                        "| corr:", round(correction_norm, 2)
                    )

        # =================================================
        # FOLLOW_COLOR - RENGİ KAMERADA HEDEFTE TUT
        # =================================================

        elif mode == "FOLLOW_COLOR":
            motor_forward(MOTOR_SPEED_COLOR)

            elapsed = time.ticks_diff(now_ms, color_start_time)

            same_color_visible = detected_color == active_color

            if same_color_visible:
                no_color_count = 0

                correction = compute_color_correction(
                    active_color,
                    last_cam_x,
                    yaw_error,
                    chain=chain_active
                )

                set_steering_correction(correction)

            else:
                no_color_count += 1

                if active_color == "RED":
                    set_steering_correction(0.28)
                elif active_color == "GREEN":
                    set_steering_correction(-0.28)

            if elapsed >= FOLLOW_COLOR_MIN_TIME_MS and no_color_count >= LOST_COLOR_FRAMES_TO_ENTER:
                lost_start_time = now_ms
                print("MODE -> LOST_COLOR | Color lost:", active_color)
                log_mode_change("LOST_COLOR", "Color=" + str(active_color) + " NoColor=" + str(no_color_count))
                mode = "LOST_COLOR"

            elif elapsed >= FOLLOW_COLOR_MAX_TIME_MS:
                pass_start_time = now_ms
                print("MODE -> PASS_COLOR | Timeout")
                log_mode_change("PASS_COLOR", "Timeout Color=" + str(active_color))
                mode = "PASS_COLOR"

        # =================================================
        # LOST_COLOR - RENK KAYBOLDU AMA HEMEN TERS KIRMA
        # =================================================

        elif mode == "LOST_COLOR":
            motor_forward(MOTOR_SPEED_LOST)

            lost_elapsed = time.ticks_diff(now_ms, lost_start_time)

            if detected_color == active_color:
                print("MODE -> FOLLOW_COLOR | Color found again")
                log_mode_change("FOLLOW_COLOR", "Color found again=" + str(active_color))
                no_color_count = 0
                mode = "FOLLOW_COLOR"

            else:
                no_color_count += 1

                if active_color == "RED":
                    correction = LOST_BIAS_RED
                elif active_color == "GREEN":
                    correction = LOST_BIAS_GREEN
                else:
                    correction = 0.0

                correction -= yaw_error * K_HEADING_IN_COLOR

                if CAMERA_STEER_REVERSE:
                    correction = -correction

                set_steering_correction(correction)

                if no_color_count >= LOST_COLOR_FRAMES_TO_PASS or lost_elapsed >= LOST_COLOR_MAX_TIME_MS:
                    print("MODE -> PASS_COLOR | Lost tamam, engel geciliyor")
                    log_mode_change("PASS_COLOR", "Lost tamam Color=" + str(active_color) + " NoColor=" + str(no_color_count))
                    pass_start_time = now_ms
                    mode = "PASS_COLOR"

        # =================================================
        # PASS_COLOR - ENGELİN YANINDAN GEÇİŞİ TAMAMLA
        # =================================================

        elif mode == "PASS_COLOR":
            motor_forward(MOTOR_SPEED_PASS)

            pass_elapsed = time.ticks_diff(now_ms, pass_start_time)

            if active_color == "RED":
                correction = PASS_BIAS_RED
            elif active_color == "GREEN":
                correction = PASS_BIAS_GREEN
            else:
                correction = 0.0

            if chain_active:
                if correction > 0:
                    correction += CHAIN_PASS_BONUS
                elif correction < 0:
                    correction -= CHAIN_PASS_BONUS

            correction -= yaw_error * 0.010

            if CAMERA_STEER_REVERSE:
                correction = -correction

            set_steering_correction(correction)

            if pass_elapsed >= pass_duration:
                print("MODE -> RECOVER_HEADING | Ana aciya donuluyor")
                log_mode_change(
                    "RECOVER_HEADING",
                    "Color=" + str(active_color)
                    + " Yaw=" + str(round(yaw, 2))
                    + " PassElapsed=" + str(pass_elapsed)
                )

                last_obstacle_color = active_color
                last_obstacle_time = now_ms

                recover_start_time = now_ms
                clear_uart_buffer()

                color_ignore_until = time.ticks_add(now_ms, COLOR_IGNORE_AFTER_RECOVER_MS)
                turn_ignore_until = time.ticks_add(now_ms, 500)

                mode = "RECOVER_HEADING"
                reset_pid()

        # =================================================
        # RECOVER_HEADING - ANA YAW'A DÖN
        # =================================================

        elif mode == "RECOVER_HEADING":
            motor_forward(MOTOR_SPEED_RECOVER)

            recover_elapsed = time.ticks_diff(now_ms, recover_start_time)
            yaw_error_to_start = color_start_yaw - yaw

            if abs(yaw_error_to_start) <= RECOVER_TOLERANCE:
                print("RECOVER bitti. MODE -> FOLLOW")
                log_mode_change("FOLLOW", "Recover bitti YawErr=" + str(round(yaw_error_to_start, 2)))

                servo_center()
                time.sleep(0.12)

                yaw = 0.0
                target_yaw = 0.0
                color_start_yaw = 0.0
                turn_start_yaw = 0.0
                active_color = "NONE"
                no_color_count = 0
                chain_active = False

                clear_uart_buffer()

                color_ignore_until = time.ticks_add(now_ms, COLOR_IGNORE_AFTER_RECOVER_MS)
                turn_ignore_until = time.ticks_add(now_ms, 600)

                reset_pid()
                mode = "FOLLOW"
                motor_forward(MOTOR_SPEED_FOLLOW)

            elif recover_elapsed >= RECOVER_MAX_TIME_MS:
                print("RECOVER timeout. MODE -> FOLLOW")
                log_mode_change("FOLLOW", "Recover timeout YawErr=" + str(round(yaw_error_to_start, 2)))

                servo_center()
                time.sleep(0.12)

                yaw = 0.0
                target_yaw = 0.0
                active_color = "NONE"
                no_color_count = 0
                chain_active = False

                clear_uart_buffer()

                color_ignore_until = time.ticks_add(now_ms, COLOR_IGNORE_AFTER_RECOVER_MS)
                turn_ignore_until = time.ticks_add(now_ms, 600)

                reset_pid()
                mode = "FOLLOW"

            else:
                correction = yaw_error_to_start * RECOVER_HEADING_GAIN

                if GYRO_STEER_REVERSE:
                    correction = -correction

                set_steering_correction(correction)

        # =================================================
        # TURN - KÖŞE DÖNÜŞÜ
        # =================================================

        elif mode == "TURN":
            motor_forward(MOTOR_SPEED_TURN)
            steer_corner()

            turned_angle = abs(yaw - turn_start_yaw)

            if turned_angle >= (TURN_ANGLE - TURN_TOLERANCE):
                corner_count += 1

                if corner_count >= CORNERS_PER_LAP:
                    lap_count += 1
                    corner_count = 0
                    print("TUR TAMAMLANDI:", lap_count, "/", REQUIRED_LAPS)
                    log_event("TUR TAMAMLANDI | Lap=" + str(lap_count) + "/" + str(REQUIRED_LAPS))

                print("TURN bitti. Donulen aci:", round(turned_angle, 2))
                print("Gyro/Yaw sifirlaniyor. MODE -> FOLLOW")
                log_event(
                    "TURN bitti | Angle=" + str(round(turned_angle, 2))
                    + " Corner=" + str(corner_count)
                    + " Lap=" + str(lap_count)
                )
                log_mode_change("FOLLOW", "Turn bitti")

                servo_center()
                time.sleep(0.12)

                yaw = 0.0
                target_yaw = 0.0
                turn_start_yaw = 0.0
                color_start_yaw = 0.0
                active_color = "NONE"
                no_color_count = 0
                chain_active = False

                clear_uart_buffer()

                color_ignore_until = time.ticks_add(now_ms, 300)
                turn_ignore_until = time.ticks_add(now_ms, TURN_IGNORE_AFTER_TURN_MS)

                reset_pid()

                mode = "FOLLOW"
                motor_forward(MOTOR_SPEED_FOLLOW)

        # =================================================
        # DEBUG PRINT + LOG SNAPSHOT
        # =================================================

        loop_count += 1

        if loop_count % 10 == 0:
            print(
                "Mode:", mode,
                "| Lap:", lap_count,
                "| Corner:", corner_count,
                "| Cam:", last_cam_type,
                "| X:", last_cam_x,
                "| Bottom:", last_cam_bottom,
                "| Count:", last_cam_count,
                "| Dist:", None if distance is None else round(distance, 1),
                "| Yaw:", round(yaw, 2),
                "| Active:", active_color,
                "| NoColor:", no_color_count,
                "| Chain:", chain_active,
                "| CloseCnt:", very_close_count
            )

        if time.ticks_diff(now_ms, last_snapshot_log_time) >= 1000:
            last_snapshot_log_time = now_ms

            log_debug_snapshot(
                mode,
                lap_count,
                corner_count,
                last_cam_type,
                last_cam_x,
                last_cam_bottom,
                last_cam_count,
                distance,
                yaw,
                active_color
            )

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Program durduruldu.")
    log_event("KeyboardInterrupt | Program durduruldu")

except Exception as e:
    print("HATA:", e)
    log_event("EXCEPTION | " + str(e))

finally:
    motor_stop()
    servo_center()
    log_event("Program bitti | Motor durdu, servo merkez")
    print("Motor durdu, servo merkeze alindi.")
