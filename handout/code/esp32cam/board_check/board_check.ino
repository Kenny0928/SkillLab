// 範例 1：檢查板子（PSRAM、快閃記憶體、LED）
// 開發板選「AI Thinker ESP32-CAM」，序列埠監控視窗的速率選 115200
// 紅色 LED 在板子背面，接 GPIO 33，輸出 LOW 才會亮
// 閃光燈是正面的白色大 LED，接 GPIO 4，很亮，不要直視

const int RED_LED = 33;    // 板子背面的紅色小 LED
const int FLASH_LED = 4;   // 正面的閃光燈
const int FLASH_MAX = 30;  // 閃光燈亮度上限（0–255），太亮會刺眼又發燙

void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(RED_LED, OUTPUT);
  ledcAttach(FLASH_LED, 5000, 8);  // PWM：5 kHz、8 位元（0–255）

  Serial.println();
  Serial.println("===== ESP32-CAM 檢查 =====");
  Serial.printf("晶片：%s，%d 核心，%d MHz\n", ESP.getChipModel(), ESP.getChipCores(), ESP.getCpuFreqMHz());
  Serial.printf("快閃記憶體：%u MB\n", ESP.getFlashChipSize() / (1024 * 1024));
  if (psramFound()) {
    Serial.printf("PSRAM：%u KB（可以拍高解析度照片）\n", ESP.getPsramSize() / 1024);
  } else {
    Serial.println("PSRAM：找不到。開發板沒選 AI Thinker ESP32-CAM，或板子沒有 PSRAM");
  }
}

void loop() {
  // 紅色 LED 亮，閃光燈慢慢變亮
  digitalWrite(RED_LED, LOW);
  for (int d = 0; d <= FLASH_MAX; d++) {
    ledcWrite(FLASH_LED, d);
    delay(20);
  }
  // 紅色 LED 滅，閃光燈慢慢變暗
  digitalWrite(RED_LED, HIGH);
  for (int d = FLASH_MAX; d >= 0; d--) {
    ledcWrite(FLASH_LED, d);
    delay(20);
  }
  delay(400);
}
