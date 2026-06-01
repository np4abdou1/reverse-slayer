<?php
$url = $_GET['url'] ?? '';
if (!$url) { http_response_code(400); exit; }

$headers = [
    'Client-Id: android-app2',
    'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd',
    'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
];

$ch = curl_init();
curl_setopt_array($ch, [
    CURLOPT_URL => $url,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_SSL_VERIFYPEER => false,
    CURLOPT_SSL_VERIFYHOST => false,
    CURLOPT_TIMEOUT => 30,
    CURLOPT_HTTPHEADER => $headers,
]);

// Pass through content type
$res = curl_exec($ch);
$info = curl_getinfo($ch);
$contentType = $info['content_type'] ?? 'application/octet-stream';
$httpCode = $info['http_code'] ?? 500;
curl_close($ch);

if ($httpCode >= 400) {
    http_response_code($httpCode);
    echo "Proxy error: $httpCode";
    exit;
}

header("Content-Type: $contentType");
header("Content-Length: " . strlen($res));
echo $res;
