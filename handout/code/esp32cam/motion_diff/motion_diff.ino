// 範例 5：畫面變化偵測（不用 AI）
// 開發板選「AI Thinker ESP32-CAM」，序列埠監控視窗的速率選 115200
// 每 0.1 秒拍一張 160×120 的灰階畫面，和上一張逐點比較，算出有幾 % 的像素變了
// 超過門檻就亮紅色 LED，序列埠印出「偵測到畫面變化」
// 打開序列繪圖家，可以看到「變化」和「門檻」兩條線

#include "esp_camera.h"

const int PIXEL_DIFF = 25;            // 一個像素的亮度差超過這個值（0–255），才算「變了」
const float TRIGGER_PERCENT = 5.0;    // 變了的像素超過幾 %，才算畫面有動靜
const unsigned long HOLD_MS = 1000;   // 偵測到之後，紅燈至少亮多久
const unsigned long WARMUP_MS = 3000; // 開機後先等自動曝光穩定
const int RED_LED = 33;               // 背面紅色 LED，LOW 亮
const int FLASH_LED = 4;              // 閃光燈，保持關閉

const int W = 160;
const int H = 120;

// AI Thinker ESP32-CAM 的相機腳位（和官方範例 camera_pins.h 的 CAMERA_MODEL_AI_THINKER 相同）
#define PWDN_GPIO_NUM  32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  0
#define SIOD_GPIO_NUM  26
#define SIOC_GPIO_NUM  27
#define Y9_GPIO_NUM    35
#define Y8_GPIO_NUM    34
#define Y7_GPIO_NUM    39
#define Y6_GPIO_NUM    36
#define Y5_GPIO_NUM    21
#define Y4_GPIO_NUM    19
#define Y3_GPIO_NUM    18
#define Y2_GPIO_NUM    5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM  23
#define PCLK_GPIO_NUM  22

uint8_t *prevFrame;          // 上一張畫面
bool hasPrev = false;
bool moving = false;         // 現在是不是「有動靜」
unsigned long lastMotion = 0;

bool initCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM;
  c.pin_d1 = Y3_GPIO_NUM;
  c.pin_d2 = Y4_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM;
  c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM;
  c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM;
  c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM;
  c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM;
  c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM;
  c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_GRAYSCALE;  // 灰階：每個像素一個位元組，0 黑、255 白
  c.frame_size = FRAMESIZE_QQVGA;        // 160×120，小張才算得快
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("相機啟動失敗：0x%x（排線沒插好，或開發板選錯）\n", err);
    return false;
  }
  return true;
}

void setup() {
  Serial.begin(115200);
  pinMode(RED_LED, OUTPUT);
  digitalWrite(RED_LED, HIGH);
  pinMode(FLASH_LED, OUTPUT);
  digitalWrite(FLASH_LED, LOW);

  prevFrame = (uint8_t *)malloc(W * H);
  if (!prevFrame || !initCamera()) {
    while (true) delay(1000);
  }
}

void loop() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) return;
  if (fb->len != W * H) {  // 不是預期的大小就跳過
    esp_camera_fb_return(fb);
    return;
  }

  // 逐點比較：亮度差超過 PIXEL_DIFF 的像素有幾個
  int changed = 0;
  if (hasPrev) {
    for (int i = 0; i < W * H; i++) {
      if (abs((int)fb->buf[i] - (int)prevFrame[i]) > PIXEL_DIFF) changed++;
    }
  }
  memcpy(prevFrame, fb->buf, W * H);  // 這一張變成下一輪的「上一張」
  esp_camera_fb_return(fb);

  if (!hasPrev || millis() < WARMUP_MS) {
    hasPrev = true;
    delay(100);
    return;
  }

  float percent = changed * 100.0 / (W * H);
  Serial.printf("變化:%.1f 門檻:%.1f\n", percent, TRIGGER_PERCENT);  // 單位是 %

  if (percent > TRIGGER_PERCENT) {
    if (!moving) Serial.println("偵測到畫面變化");
    moving = true;
    lastMotion = millis();
  } else if (moving && millis() - lastMotion > HOLD_MS) {
    moving = false;
  }
  digitalWrite(RED_LED, moving ? LOW : HIGH);
  delay(100);
}
