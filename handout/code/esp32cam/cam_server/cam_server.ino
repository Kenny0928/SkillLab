// 範例 3：串流與拍照網址（微專題 02 的 Python 從這裡拿畫面）
// 開發板選「AI Thinker ESP32-CAM」，序列埠監控視窗的速率選 115200
// 燒錄前先改 WIFI_SSID、WIFI_PASS；只能連 2.4 GHz 的 Wi-Fi
// 開機後序列埠會印出板子的 IP，例如 192.168.1.23：
//   http://192.168.1.23/           瀏覽器看即時畫面
//   http://192.168.1.23/capture    拍一張 JPEG（Python 用這個）
//   http://192.168.1.23:81/stream  連續畫面（同時只能一個人看）
// 這些網址沒有密碼，連到同一個 Wi-Fi 的人都打得開

#include "esp_camera.h"
#include "esp_http_server.h"
#include <WiFi.h>

const char *WIFI_SSID = "你的 Wi-Fi 名稱";
const char *WIFI_PASS = "你的 Wi-Fi 密碼";

const framesize_t FRAME_SIZE = FRAMESIZE_VGA;  // 640×480；要更順可以改 FRAMESIZE_QVGA（320×240）
const int JPEG_QUALITY = 12;                   // 10–63，數字越小畫質越好、檔案越大
const int RED_LED = 33;                        // 背面紅色 LED，LOW 亮：亮著代表沒連上 Wi-Fi
const int FLASH_LED = 4;                       // 閃光燈，這個範例不用，保持關閉

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

#define BOUNDARY "frame"

// 首頁：一張圖，來源是 81 埠的串流
const char INDEX_HTML[] = R"html(<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>ESP32-CAM</title>
<style>body{margin:0;background:#111;color:#eee;font-family:sans-serif;text-align:center}img{max-width:100%}a{color:#f9a}</style>
</head><body><img id="v" alt="即時畫面"><p><a href="/capture">拍一張</a></p>
<script>document.getElementById("v").src = "http://" + location.hostname + ":81/stream";</script>
</body></html>)html";

httpd_handle_t webServer = NULL;     // 80 埠：首頁、拍照
httpd_handle_t streamServer = NULL;  // 81 埠：串流

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
  c.pixel_format = PIXFORMAT_JPEG;     // 相機直接輸出 JPEG
  c.frame_size = FRAME_SIZE;
  c.jpeg_quality = JPEG_QUALITY;
  c.fb_count = 2;                      // 兩個畫面緩衝區，放在 PSRAM
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;    // 永遠拿最新的畫面
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("相機啟動失敗：0x%x（排線沒插好，或開發板選錯）\n", err);
    return false;
  }
  return true;
}

// http://IP/
esp_err_t indexHandler(httpd_req_t *req) {
  httpd_resp_set_type(req, "text/html; charset=utf-8");
  return httpd_resp_send(req, INDEX_HTML, HTTPD_RESP_USE_STRLEN);
}

// http://IP/capture：回傳一張 JPEG
esp_err_t captureHandler(httpd_req_t *req) {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

// http://IP:81/stream：一張接一張送 JPEG，直到對方關掉
esp_err_t streamHandler(httpd_req_t *req) {
  httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=" BOUNDARY);
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  char head[80];
  while (true) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) return ESP_FAIL;
    int n = snprintf(head, sizeof(head),
                     "\r\n--" BOUNDARY "\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
    esp_err_t res = httpd_resp_send_chunk(req, head, n);
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
    esp_camera_fb_return(fb);
    if (res != ESP_OK) return res;  // 瀏覽器或 Python 關掉了
  }
}

void startServers() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  httpd_uri_t indexUri = {.uri = "/", .method = HTTP_GET, .handler = indexHandler, .user_ctx = NULL};
  httpd_uri_t captureUri = {.uri = "/capture", .method = HTTP_GET, .handler = captureHandler, .user_ctx = NULL};
  httpd_uri_t streamUri = {.uri = "/stream", .method = HTTP_GET, .handler = streamHandler, .user_ctx = NULL};

  if (httpd_start(&webServer, &config) == ESP_OK) {
    httpd_register_uri_handler(webServer, &indexUri);
    httpd_register_uri_handler(webServer, &captureUri);
  }
  // 串流會一直佔著伺服器，所以另外開一個在 81 埠
  config.server_port += 1;
  config.ctrl_port += 1;
  if (httpd_start(&streamServer, &config) == ESP_OK) {
    httpd_register_uri_handler(streamServer, &streamUri);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(RED_LED, OUTPUT);
  digitalWrite(RED_LED, LOW);
  pinMode(FLASH_LED, OUTPUT);
  digitalWrite(FLASH_LED, LOW);

  if (!initCamera()) {
    while (true) delay(1000);  // 相機壞了就停在這裡，紅燈一直亮
  }

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // 關掉 Wi-Fi 省電模式，畫面延遲比較小
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("連線 Wi-Fi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > 20000) {
      Serial.println("\n連不上 Wi-Fi：檢查名稱、密碼，以及是不是 2.4 GHz。5 秒後重新開機");
      delay(5000);
      ESP.restart();
    }
    delay(500);
    Serial.print(".");
  }
  digitalWrite(RED_LED, HIGH);

  startServers();
  String ip = WiFi.localIP().toString();
  Serial.println();
  Serial.println("即時畫面：http://" + ip + "/");
  Serial.println("拍一張：  http://" + ip + "/capture");
  Serial.println("串流：    http://" + ip + ":81/stream");
}

void loop() {
  // 網頁伺服器在背景執行，這裡只顯示 Wi-Fi 狀態
  static bool wasConnected = true;
  bool connected = WiFi.status() == WL_CONNECTED;
  if (connected != wasConnected) {
    if (connected) {
      Serial.println("Wi-Fi 重新連上了，IP：" + WiFi.localIP().toString());  // IP 可能和之前不同
    } else {
      Serial.println("Wi-Fi 斷線，自動重連中");
    }
    digitalWrite(RED_LED, connected ? HIGH : LOW);
    wasConnected = connected;
  }
  delay(1000);
}
