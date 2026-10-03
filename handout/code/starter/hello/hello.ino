// 環境驗收：每秒送出一行 hello 和次數
// Uno、ESP32 都能用；序列埠監控視窗的速率選 9600（預設值）

unsigned long count = 0;

void setup() {
  Serial.begin(9600);
}

void loop() {
  Serial.print("hello ");
  Serial.println(count);
  count++;
  delay(1000);
}
