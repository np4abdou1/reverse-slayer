<?php
header('Content-Type: application/json');
$base = 'https://anslayer.com/anime/public/';
$headers = [
    'Client-Id: android-app2',
    'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd',
    'Accept: application/json, application/*+json',
];
$json = json_encode(["list_type" => "latest_episodes", "limit" => 3]);
$url = $base . 'animes/get-published-animes?json=' . urlencode($json);
$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_SSL_VERIFYPEER => false,
    CURLOPT_SSL_VERIFYHOST => false,
    CURLOPT_TIMEOUT => 15,
    CURLOPT_HTTPHEADER => $headers,
]);
$res = curl_exec($ch);
$info = curl_getinfo($ch);
$err = curl_error($ch);
curl_close($ch);
echo json_encode([
    'url' => $url,
    'code' => $info['http_code'],
    'error' => $err,
    'resp_len' => strlen($res),
    'resp' => substr($res, 0, 200),
]);
