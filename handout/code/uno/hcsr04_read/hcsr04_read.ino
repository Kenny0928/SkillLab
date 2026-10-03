// 步驟 2：讀取 HC-SR04 距離
// 接線：HC-SR04 Trig → D4、Echo → D3、VCC → 5V、GND → GND

const int TRIG_PIN = 4;       // 超音波 Trig
const int ECHO_PIN = 3;       // 超音波 Echo
const int INTERVAL_MS = 100;  // 兩次量測間隔（要 ≥ 60 ms，避免收到上次的回波）

// 回傳距離（cm）；沒有收到回波時回傳 -1
float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long us = pulseIn(ECHO_PIN, HIGH, 30000UL);  // 最多等 30 ms（約 5 m）
  if (us == 0) return -1;
  return us / 58.0;  // 聲音來回，每 58 µs 約 1 cm
}

void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
}

void loop() {
  float cm = readDistanceCm();
  if (cm < 0) {
    Serial.println(F("距離(cm):沒有回波（太遠、角度不對或接線錯誤）"));
  } else {
    Serial.print(F("距離(cm):"));
    Serial.println(cm, 1);
  }
  delay(INTERVAL_MS);
}
