// 步驟 5：防盜主程式（步驟 6 Gmail、步驟 7 Discord、步驟 8 儀表板共用）
// 接線：光敏電阻模組 AO → A0（VCC 接 5V、GND 接 GND）
//       旋鈕 中間腳 → A1（兩側腳接 5V 與 GND）
//       HC-SR04 Trig → D4、Echo → D3（VCC 接 5V、GND 接 GND）
//       有源蜂鳴器 + → D12（− 接 GND）
//       全彩 LED R → D11、G → D10、B → D9（各經 220 Ω；共用腳接 GND，共陽極接 5V）
// 序列埠指令（一行一個，結尾換行，不分大小寫）：
//   ARM、DISARM、MUTE、STATUS
//   MODE,TEST   進入測試模式
//   MODE,DETECT 回到偵測模式
//   TEST        測試模式中送出測試事件

const int LDR_PIN = A0;                // 光敏電阻模組 AO
const int KNOB_PIN = A1;               // 旋鈕中間腳
const int TRIG_PIN = 4;                // 超音波 Trig
const int ECHO_PIN = 3;                // 超音波 Echo
const int BUZZER_PIN = 12;             // 有源蜂鳴器
const int R_PIN = 11;                  // LED 紅（PWM）
const int G_PIN = 10;                  // LED 綠（PWM）
const int B_PIN = 9;                   // LED 藍（PWM）

const unsigned long EXIT_MS = 10000;   // 離開倒數
const unsigned long ENTRY_MS = 10000;  // 進入倒數（時間內要用 DISARM 解除）
const int LIGHT_DELTA = 150;           // 亮度和基準差這麼多，就當作盒子被打開（變亮或變暗都算，模組的方向不一定）
const int MIN_CM = 5;                  // 旋鈕最左：觸發距離
const int MAX_CM = 100;                // 旋鈕最右：觸發距離
const unsigned long REPORT_MS = 250;   // 回報間隔
const unsigned long MEASURE_MS = 70;   // 兩次量測間隔（要 ≥ 60 ms）
const float FAR_CM = 999;              // 沒有回波時當作「很遠」

const bool COMMON_ANODE = false;       // 共陽極 LED 改成 true，共用腳改接 5V
const bool BUZZER_ACTIVE_LOW = false;  // 三腳模組若是低電位觸發改成 true

enum State { DISARMED, EXIT, ARMED, ENTRY, ALARM, TEST };

State state = DISARMED;
unsigned long stateStart = 0;          // 進入目前狀態的時間
bool muted = false;                    // ALARM 時是否已靜音
float history[3] = {FAR_CM, FAR_CM, FAR_CM};  // 最近 3 次量測
int historyIndex = 0;
unsigned long lastMeasure = 0;
unsigned long lastReport = 0;
bool newDistance = false;              // 這一圈是否有新的距離
float distanceCm = FAR_CM;             // 中位數距離
int light = 0;                         // 光線 0～1023
int lightBaseline = 0;                 // 開始警戒時的光線
int triggerCm = MAX_CM;                // 旋鈕決定的觸發距離
int nearCount = 0;                     // 連續幾次距離小於觸發距離
int testBaseline = 0;                  // 進入測試模式時的光線
bool testDistSent = false;             // 測試模式：這一次靠近是否已回報
bool testLightSent = false;            // 測試模式：這一次亮光是否已回報
char cmdBuf[16];                       // 指令緩衝（最多 15 字元）
int cmdLen = 0;
bool cmdOverflow = false;

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

const __FlashStringHelper *stateName(State s) {
  switch (s) {
    case DISARMED: return F("DISARMED");
    case EXIT:     return F("EXIT");
    case ARMED:    return F("ARMED");
    case ENTRY:    return F("ENTRY");
    case ALARM:    return F("ALARM");
    case TEST:     return F("TEST");
    default:       return F("?");
  }
}

void printState() {
  Serial.print(F("STATE,"));
  Serial.println(stateName(state));
}

// 換狀態：重設計時、靜音與連續偵測次數，並通知電腦
void setState(State s) {
  state = s;
  stateStart = millis();
  muted = false;
  nearCount = 0;
  printState();
}

// 讀三個感測器；距離每 MEASURE_MS 才量一次
void readSensors() {
  triggerCm = map(analogRead(KNOB_PIN), 0, 1023, MIN_CM, MAX_CM);
  light = analogRead(LDR_PIN);

  newDistance = false;
  if (millis() - lastMeasure >= MEASURE_MS) {
    lastMeasure = millis();
    float d = readDistanceCm();  // 最久等 30 ms，其餘時間都不會卡住
    history[historyIndex] = (d < 0) ? FAR_CM : d;
    historyIndex = (historyIndex + 1) % 3;
    distanceCm = median3(history[0], history[1], history[2]);
    newDistance = true;
  }
}

void handleCommand(const char *cmd) {
  if (strcasecmp(cmd, "ARM") == 0) {
    if (state == DISARMED) setState(EXIT);
  } else if (strcasecmp(cmd, "DISARM") == 0) {
    if (state != DISARMED) setState(DISARMED);
  } else if (strcasecmp(cmd, "MUTE") == 0) {
    if (state == ALARM) muted = true;
  } else if (strcasecmp(cmd, "STATUS") == 0) {
    printState();
  } else if (strcasecmp(cmd, "MODE,TEST") == 0) {
    testBaseline = light;  // 以此刻的亮度當測試基準
    testDistSent = false;
    testLightSent = false;
    setState(TEST);
  } else if (strcasecmp(cmd, "MODE,DETECT") == 0) {
    if (state == TEST) setState(DISARMED);
  } else if (strcasecmp(cmd, "TEST") == 0) {
    if (state == TEST) {
      Serial.print(F("TEST,PING,"));
      Serial.print(distanceCm >= FAR_CM ? -1 : (int)distanceCm);
      Serial.print(',');
      Serial.println(light);
    } else {
      Serial.println(F("ERR,TEST"));
    }
  } else {
    Serial.print(F("ERR,"));
    Serial.println(cmd);
  }
}

// 一次讀一個字元，收到換行才處理整行指令
void readCommands() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') {
      if (cmdLen < 15) cmdBuf[cmdLen++] = c;
      else cmdOverflow = true;
      continue;
    }
    cmdBuf[cmdLen] = '\0';
    if (cmdLen > 0 || cmdOverflow) handleCommand(cmdBuf);
    cmdLen = 0;
    cmdOverflow = false;
  }
}

void updateState() {
  unsigned long elapsed = millis() - stateStart;

  if (state == EXIT && elapsed >= EXIT_MS) {
    lightBaseline = light;  // 以此刻的亮度當基準
    setState(ARMED);
  } else if (state == ARMED) {
    // 距離要連續 2 次（新的中位數）小於觸發距離才算，避免誤報
    if (newDistance) nearCount = (distanceCm < triggerCm) ? nearCount + 1 : 0;
    if (nearCount >= 2) {
      Serial.println(F("DETECT,DIST"));
      setState(ENTRY);
    } else if (abs(light - lightBaseline) > LIGHT_DELTA) {
      Serial.println(F("DETECT,LIGHT"));
      setState(ENTRY);
    }
  } else if (state == ENTRY && elapsed >= ENTRY_MS) {
    setState(ALARM);
  } else if (state == TEST) {
    // 距離：連續 2 次小於觸發距離才回報一次；離開範圍後才會再回報
    if (newDistance) nearCount = (distanceCm < triggerCm) ? nearCount + 1 : 0;
    if (nearCount >= 2 && !testDistSent) {
      testDistSent = true;
      Serial.print(F("TEST,DIST,"));
      Serial.println((int)distanceCm);
    } else if (newDistance && nearCount == 0) {
      testDistSent = false;
    }
    // 光線：和基準差很多就回報一次；回到接近基準才會再回報
    if (!testLightSent && abs(light - testBaseline) > LIGHT_DELTA) {
      testLightSent = true;
      Serial.print(F("TEST,LIGHT,"));
      Serial.println(light);
    } else if (abs(light - testBaseline) < LIGHT_DELTA / 2) {
      testLightSent = false;
    }
  }
}

void updateOutputs() {
  unsigned long elapsed = millis() - stateStart;
  unsigned long t = elapsed % 1000;  // 這一秒內的第幾毫秒

  switch (state) {
    case DISARMED:
      setColor(0, 255, 0);
      buzzer(false);
      break;
    case EXIT:  // 黃燈每 500 ms 閃一次；每秒開頭嗶 100 ms
      if ((elapsed / 500) % 2 == 0) setColor(255, 120, 0);
      else setColor(0, 0, 0);
      buzzer(t < 100);
      break;
    case ARMED:
      setColor(0, 0, 255);
      buzzer(false);
      break;
    case ENTRY:  // 黃燈每 150 ms 閃一次；每秒嗶兩聲（0 ms 與 200 ms 開始，各 80 ms）
      if ((elapsed / 150) % 2 == 0) setColor(255, 120, 0);
      else setColor(0, 0, 0);
      buzzer(t < 80 || (t >= 200 && t < 280));
      break;
    case ALARM:
      setColor(255, 0, 0);
      buzzer(!muted);
      break;
    case TEST:  // 測試模式：紫燈恆亮、蜂鳴器不響
      setColor(160, 0, 255);
      buzzer(false);
      break;
  }
}

// 格式固定，網頁儀表板會解析：READ,距離,光線,觸發距離,狀態
void report() {
  if (millis() - lastReport < REPORT_MS) return;
  lastReport = millis();
  Serial.print(F("READ,"));
  Serial.print(distanceCm >= FAR_CM ? -1 : (int)distanceCm);
  Serial.print(',');
  Serial.print(light);
  Serial.print(',');
  Serial.print(triggerCm);
  Serial.print(',');
  Serial.println(stateName(state));
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
  printState();
}

// 全程不用 delay()，每件事都靠 millis() 計時，所以倒數中也能即時收指令
void loop() {
  readCommands();
  readSensors();
  updateState();
  updateOutputs();
  report();
}
