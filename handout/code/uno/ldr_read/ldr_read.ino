// 步驟 1：讀取光敏電阻模組
// 接線：模組 AO → A0、VCC → 5V、GND → GND（DO 不用接）
// 常見的模組越亮讀值越小，有些模組相反

const int LDR_PIN = A0;        // 光敏電阻模組 AO
const int INTERVAL_MS = 200;   // 每隔多久讀一次

void setup() {
  Serial.begin(9600);
}

void loop() {
  int value = analogRead(LDR_PIN);  // 0～1023
  // 格式「名稱:數值」，序列繪圖家也能直接畫成曲線
  Serial.print(F("亮度:"));
  Serial.println(value);
  delay(INTERVAL_MS);
}
