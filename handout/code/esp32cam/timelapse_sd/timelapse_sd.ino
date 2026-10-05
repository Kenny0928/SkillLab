// 範例 4：定時拍照存到記憶卡
// 開發板選「AI Thinker ESP32-CAM」，序列埠監控視窗的速率選 115200
// 記憶卡：32 GB 以下，先在電腦上格式化成 FAT32，斷電後再插進板子
// 每 INTERVAL_S 秒拍一張，存成 /photo_00001.jpg、/photo_00002.jpg……
// 編號記在板子裡，重新開機會接著往下編

#include "esp_camera.h"
#include "SD_MMC.h"
#include <Preferences.h>

const unsigned long INTERVAL_S = 10;            // 幾秒拍一張
const framesize_t FRAME_SIZE = FRAMESIZE_SVGA;  // 800×600；最大 FRAMESIZE_UXGA（1600×1200）
const int JPEG_QUALITY = 10;                    // 10–63，數字越小畫質越好、檔案越大
const int RED_LED = 33;                         // 背面紅色 LED，LOW 亮：存檔時閃一下
const int FLASH_LED = 4;                        // 閃光燈，保持關閉

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

Preferences prefs;
unsigned long photoNo;   // 下一張照片的編號
unsigned long lastShot;  // 上一次拍照的時間

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
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAME_SIZE;
  c.jpeg_quality = JPEG_QUALITY;
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;  // 拿最新的畫面，不會拿到 10 秒前拍好放著的那張
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("相機啟動失敗：0x%x（排線沒插好，或開發板選錯）\n", err);
    return false;
  }
  return true;
}

void stopHere(const char *why) {
  Serial.println(why);
  while (true) {  // 紅燈快閃，表示出錯
    digitalWrite(RED_LED, !digitalRead(RED_LED));
    delay(150);
  }
}

void takePhoto() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("拍照失敗");
    return;
  }
  char path[24];
  snprintf(path, sizeof(path), "/photo_%05lu.jpg", photoNo);
  File file = SD_MMC.open(path, FILE_WRITE);
  if (!file) {
    Serial.printf("開不了檔案 %s：記憶卡滿了或被拔掉\n", path);
    esp_camera_fb_return(fb);
    return;
  }
  digitalWrite(RED_LED, LOW);
  file.write(fb->buf, fb->len);
  file.close();
  digitalWrite(RED_LED, HIGH);
  Serial.printf("存好 %s（%u KB）\n", path, fb->len / 1024);
  esp_camera_fb_return(fb);

  photoNo++;
  prefs.putULong("next", photoNo);  // 記下編號，重新開機不會蓋掉舊照片
}

void setup() {
  Serial.begin(115200);
  pinMode(RED_LED, OUTPUT);
  digitalWrite(RED_LED, HIGH);

  if (!initCamera()) stopHere("停止");

  // 1-bit 模式只用 GPIO 2、14、15；4-bit 模式會用到 GPIO 4，閃光燈會跟著閃
  if (!SD_MMC.begin("/sdcard", true)) {
    stopHere("讀不到記憶卡：確認有插好、是 FAT32、32 GB 以下");
  }
  pinMode(FLASH_LED, OUTPUT);
  digitalWrite(FLASH_LED, LOW);
  Serial.printf("記憶卡 %llu MB\n", SD_MMC.cardSize() / (1024 * 1024));

  prefs.begin("timelapse", false);
  photoNo = prefs.getULong("next", 1);
  Serial.printf("從第 %lu 張開始，每 %lu 秒拍一張\n", photoNo, INTERVAL_S);

  // 相機剛啟動時自動曝光還沒調好，先丟掉幾張
  for (int i = 0; i < 5; i++) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
    delay(200);
  }
  takePhoto();
  lastShot = millis();
}

void loop() {
  if (millis() - lastShot >= INTERVAL_S * 1000UL) {
    lastShot = millis();
    takePhoto();
  }
}
