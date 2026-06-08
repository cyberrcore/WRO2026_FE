#include <Arduino.h>
#include "esp_camera.h"

// =====================================================
// AI Thinker ESP32-CAM pins
// =====================================================

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5

#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// =====================================================
// Camera settings
// =====================================================

#define CAM_W 160
#define CAM_H 120

#define RED_MIN_AREA 35
#define GREEN_MIN_AREA 35

// Scan only the lower-middle area instead of the full image.
#define ROI_Y_START 30

// Skip every other pixel for faster processing.
#define STEP_X 2
#define STEP_Y 2

// =====================================================
// RGB565 -> RGB888
// =====================================================

void rgb565_to_rgb(uint16_t pixel, int &r, int &g, int &b) {
  r = ((pixel >> 11) & 0x1F) << 3;
  g = ((pixel >> 5) & 0x3F) << 2;
  b = (pixel & 0x1F) << 3;
}

// =====================================================
// Color filters
// =====================================================

bool isRed(int r, int g, int b) {
  return (
    r > 100 &&
    g < 90 &&
    b < 90 &&
    r > g * 1.5 &&
    r > b * 1.5
  );
}

bool isGreen(int r, int g, int b) {
  return (
    g > 95 &&
    r < 120 &&
    b < 120 &&
    g > r * 1.25 &&
    g > b * 1.15
  );
}

// =====================================================
// Setup
// =====================================================

void setup() {
  Serial.begin(115200);
  delay(500);

  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;

  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;

  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_RGB565;

  config.frame_size = FRAMESIZE_QQVGA;

  config.jpeg_quality = 12;
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {
    Serial.println("CAMERA_ERROR");
    delay(1000);
    ESP.restart();
  }

  sensor_t *s = esp_camera_sensor_get();

  if (s) {
    s->set_brightness(s, 0);
    s->set_contrast(s, 1);
    s->set_saturation(s, 1);

    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_gain_ctrl(s, 1);
  }

  delay(500);
  Serial.println("ESP32_CAM_READY");
}

// =====================================================
// Loop
// =====================================================

void loop() {
  camera_fb_t *fb = esp_camera_fb_get();

  if (!fb) {
    Serial.println("NONE");
    delay(40);
    return;
  }

  long red_sum_x = 0;
  long green_sum_x = 0;

  int red_count = 0;
  int green_count = 0;

  for (int y = ROI_Y_START; y < CAM_H; y += STEP_Y) {
    for (int x = 0; x < CAM_W; x += STEP_X) {
      int idx = (y * CAM_W + x) * 2;

      if (idx + 1 >= fb->len) {
        continue;
      }

      uint16_t pixel = ((uint16_t)fb->buf[idx] << 8) | fb->buf[idx + 1];

      int r, g, b;
      rgb565_to_rgb(pixel, r, g, b);

      if (isRed(r, g, b)) {
        red_sum_x += x;
        red_count++;
      }

      if (isGreen(r, g, b)) {
        green_sum_x += x;
        green_count++;
      }
    }
  }

  esp_camera_fb_return(fb);

  if (red_count > RED_MIN_AREA && red_count >= green_count) {
    int red_x = red_sum_x / red_count;

    Serial.print("RED,");
    Serial.print(red_x);
    Serial.print(",");
    Serial.println(red_count);
  } else if (green_count > GREEN_MIN_AREA) {
    int green_x = green_sum_x / green_count;

    Serial.print("GREEN,");
    Serial.print(green_x);
    Serial.print(",");
    Serial.println(green_count);
  } else {
    Serial.println("NONE");
  }

  delay(35);
}
