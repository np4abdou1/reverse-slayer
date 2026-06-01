<?php
$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$publicDir = __DIR__ . '/public';
$file = $publicDir . $uri;
if ($uri === '/' || $uri === '/index.php') {
    require $publicDir . '/index.php';
    return true;
}
if ($uri === '/anime') {
    require $publicDir . '/anime.php';
    return true;
}
if ($uri === '/watch') {
    require $publicDir . '/watch.php';
    return true;
}
if ($uri === '/api') {
    require $publicDir . '/api.php';
    return true;
}
if ($uri === '/proxy') {
    require $publicDir . '/proxy.php';
    return true;
}
$ext = pathinfo($file, PATHINFO_EXTENSION);
if (in_array($ext, ['css', 'js', 'png', 'jpg', 'svg', 'ico'])) {
    if (file_exists($file)) {
        $mime = ['css' => 'text/css', 'js' => 'application/javascript', 'png' => 'image/png', 'jpg' => 'image/jpeg', 'svg' => 'image/svg+xml', 'ico' => 'image/x-icon'];
        header('Content-Type: ' . ($mime[$ext] ?? 'application/octet-stream'));
        readfile($file);
        return true;
    }
}
http_response_code(404);
echo "<h1>404 Not Found</h1>";
return true;
