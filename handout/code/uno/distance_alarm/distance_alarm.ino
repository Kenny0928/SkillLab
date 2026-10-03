// 步驟 3：距離太近就響蜂鳴器、亮紅燈
// 接線：HC-SR04 Trig → D4、Echo → D3（VCC 接 5V、GND 接 GND）
//       有源蜂鳴器 + → D12（− 接 GND）
//       全彩 LED R → D11、G → D10、B → D9（各經 220 Ω；共用腳接 GND，共陽極接 5V）

const int TRIG_PIN = 4;                // 超音波 Trig
const int ECHO_PIN = 3;                // 超音波 Echo
const int BUZZER_PIN = 12;             // 有源蜂鳴器
const int R_PIN = 11;                  // LED 紅（PWM）
const int G_PIN = 10;                  // LED 綠（PWM）
const int B_PIN = 9;                   // LED 藍（PWM）

const float TRIGGER_CM = 30;           // 小於這個距離：觸發
const float WARN_CM = 60;              // 小於這個距離：接近
const float FAR_CM = 999;              // 沒有回波時當作「很遠」
const unsigned long MEASURE_MS = 70;   // 兩次量測間隔（要 ≥ 60 ms）
const unsigned long PRINT_MS = 300;    // 每隔多久印一行

const bool COMMON_ANODE = false;       // 共陽極 LED 改成 true，共用腳改接 5V
const bool BUZZER_ACTIVE_LOW = false;  // 三腳模組若是低電位觸發改成 true

float history[3] = {FAR_CM, FAR_CM, FAR_CM};  // 最近 3 次量測
int historyIndex = 0;
unsigned long lastPrint = 0;

// 回傳距離（cm）；沒有收到回波時回傳 -1
float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long us = pulseIn(ECHO_PIN, HIGH, 30000UL);  // 最多等 30 ms（約 5 m）
  if (us == 0) return -1;
  return us / 58.0;
}

// 三個數取中間值：偶爾一次量錯也不會影響結果
float median3(float a, float b, float c) {
  float lo = min(a, b);
  float hi = max(a, b);
  return max(lo, min(hi, c));
}

void setColor(int r, int g, int b) {
  if (COMMON_ANODE) { r = 255 - r; g = 255 - g; b = 255 - b; }
  analogWrite(R_PIN, r);
  analogWrite(G_PIN, g);
  analogWrite(B_PIN, b);
}

void buzzer(bool on) {
  digitalWrite(BUZZER_PIN, (on != BUZZER_ACTIVE_LOW) ? HIGH : LOW);
}

void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(R_PIN, OUTPUT);
  pinMode(G_PIN, OUTPUT);
  pinMode(B_PIN, OUTPUT);
  buzzer(false);  // 先關掉，低電位觸發的模組開機才不會響
  setColor(0, 255, 0);
}

void loop() {
  // 量一次，放進最近 3 次的紀錄；-1（沒有回波）當作很遠
  float d = readDistanceCm();
  history[historyIndex] = (d < 0) ? FAR_CM : d;
  historyIndex = (historyIndex + 1) % 3;
  float m = median3(history[0], history[1], history[2]);

  const __FlashStringHelper *status;
  if (m < TRIGGER_CM) {
    setColor(255, 0, 0);
    buzzer(true);
    status = F("觸發");
  } else if (m < WARN_CM) {
    setColor(255, 120, 0);
    buzzer(false);
    status = F("接近");
  } else {
    setColor(0, 255, 0);
    buzzer(false);
    status = F("安全");
  }

  // 用 millis() 控制印出頻率，不要每圈都印
  if (millis() - lastPrint >= PRINT_MS) {
    lastPrint = millis();
    Serial.print(F("距離 "));
    if (m >= FAR_CM) {
      Serial.print(F("—"));
    } else {
      Serial.print(m, 1);
      Serial.print(F(" cm"));
    }
    Serial.print(F("｜"));
    Serial.println(status);
  }

  delay(MEASURE_MS);
}
