<?php
header('Content-Type: application/json');
$testUrl = 'https://anslayer.com/anime/public/animes/get-published-animes?json=' . urlencode(json_encode(['list_type' => 'latest_episodes', 'limit' => 1]));
$headers = ['Client-Id: android-app2', 'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd', 'Accept: application/json'];

$ch = curl_init($testUrl);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_SSL_VERIFYPEER => false,
    CURLOPT_SSL_VERIFYHOST => false,
    CURLOPT_TIMEOUT => 15,
    CURLOPT_HTTPHEADER => $headers,
    CURLOPT_HEADER => true,
]);
$res = curl_exec($ch);
$info = curl_getinfo($ch);
$err = curl_error($ch);
curl_close($ch);

echo json_encode([
    'url' => $testUrl,
    'http_code' => $info['http_code'] ?? 0,
    'curl_error' => $err,
    'response_header' => substr($res, 0, 200),
    'response_body' => substr($res, (int)($info['header_size'] ?? 0), 300),
]);
