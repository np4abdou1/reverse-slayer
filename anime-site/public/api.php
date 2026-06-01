<?php
header('Content-Type: application/json');
$action = $_GET['action'] ?? '';
$base = 'https://anslayer.com/anime/public/';

function acurl($url) {
    $headers = [
        'Client-Id: android-app2',
        'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd',
        'Accept: application/json, application/*+json',
    ];
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_SSL_VERIFYHOST => false,
        CURLOPT_TIMEOUT => 15,
        CURLOPT_HTTPHEADER => $headers,
    ]);
    $res = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return [$code, json_decode($res, true) ?? $res];
}

function apost($url, $data) {
    $headers = [
        'Client-Id: android-app2',
        'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd',
        'Accept: application/json, application/*+json',
        'Content-Type: application/x-www-form-urlencoded',
    ];
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_SSL_VERIFYHOST => false,
        CURLOPT_TIMEOUT => 15,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => http_build_query($data),
        CURLOPT_HTTPHEADER => $headers,
    ]);
    $res = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return [$code, json_decode($res, true) ?? $res];
}

try {
    switch ($action) {
        case 'search':
            $type = $_GET['type'] ?? 'anime_list';
            $limit = min((int)($_GET['limit'] ?? 25), 50);
            $q = $_GET['q'] ?? '';
            if ($q) {
                $p = ['list_type' => 'filter', 'anime_name' => $q, 'limit' => $limit];
            } else {
                if ($type === 'all') $type = 'anime_list';
                $p = ['list_type' => $type, 'limit' => $limit];
            }
            [$c, $d] = acurl($base . 'animes/get-published-animes?json=' . urlencode(json_encode($p)));
            echo json_encode(['code' => $c, 'data' => $d]);
            break;
        case 'detail':
            $id = (int)($_GET['id'] ?? 0);
            if (!$id) { echo json_encode(['error' => 'no id']); break; }
            [$c, $d] = acurl($base . "anime/get-anime-details?anime_id={$id}&fetch_episodes=true&more_info=true");
            echo json_encode(['code' => $c, 'data' => $d]);
            break;
        case 'episodes':
            $id = (int)($_GET['id'] ?? 0);
            $limit = min((int)($_GET['limit'] ?? 50), 200);
            if (!$id) { echo json_encode(['error' => 'no id']); break; }
            [$c, $d] = acurl($base . 'episodes/get-episodes?json=' . urlencode(json_encode(['anime_id' => $id, 'limit' => $limit])));
            echo json_encode(['code' => $c, 'data' => $d]);
            break;
        case 'servers':
            $eid = (int)($_GET['episode_id'] ?? 0);
            $aid = (int)($_GET['anime_id'] ?? 0);
            if (!$eid) { echo json_encode(['error' => 'no ep']); break; }
            $urls = [];
            [$c, $d] = apost($base . 'episodes/get-episodes-new', ['inf' => $_SERVER['REMOTE_ADDR'] ?? '', 'json' => json_encode(['anime_id' => $aid, 'episode_ids' => [$eid], 'limit' => 1])]);
            if ($c == 200 && isset($d['response']['data'][0]['episode_urls'])) $urls = $d['response']['data'][0]['episode_urls'];
            if (!$urls) {
                [$c2, $d2] = acurl($base . 'episodes/get-episodes?json=' . urlencode(json_encode(['anime_id' => $aid, 'limit' => 200])));
                if ($c2 == 200 && isset($d2['response']['data']))
                    foreach ($d2['response']['data'] as $e)
                        if ((int)$e['episode_id'] == $eid && isset($e['episode_urls'])) { $urls = $e['episode_urls']; break; }
            }
            if ($urls) {
                $urls = array_values(array_filter($urls, function($u) {
                    return !str_contains($u['episode_url'], 'v-qs.php');
                }));
                // Try resolving muilt URLs immediately to individual servers
                $newUrls = [];
                $serverMap = [
                    'vinovo' => ['name' => 'سيرفر : VVO', 'label' => 'VVO'],
                    'streamtape' => ['name' => 'سيرفر : ST', 'label' => 'ST'],
                    'goodstream' => ['name' => 'سيرفر : GDS (للمشاهدة)', 'label' => 'GDS'],
                    'mediafire' => ['name' => 'سيرفر احتاطي', 'label' => 'ANS'],
                    'ok.ru' => ['name' => 'سيرفر : OU', 'label' => 'OU'],
                    'filemoon' => ['name' => 'سيرفر : FMS', 'label' => 'FMS'],
                    'pixeldrain' => ['name' => 'سيرفر : PXD (للمشاهدة)', 'label' => 'PXD'],
                    'lulustream' => ['name' => 'سيرفر : llS (للمشاهدة)', 'label' => 'llS'],
                    'roberteachfinal' => ['name' => 'سيرفر : VOE (للمشاهدة)', 'label' => 'VOE'],
                    'mixdrop' => ['name' => 'سيرفر : MP', 'label' => 'MP'],
                    'mp4upload' => ['name' => 'سيرفر : MD', 'label' => 'MD'],
                    'fembed' => ['name' => 'سيرفر : FD', 'label' => 'FD'],
                    'uptostream' => ['name' => 'سيرفر : US', 'label' => 'US'],
                    'vidmoly' => ['name' => 'سيرفر : VM', 'label' => 'VM'],
                    'doodstream' => ['name' => 'سيرفر : DS', 'label' => 'DS'],
                    'qiwi' => ['name' => 'سيرفر : QW', 'label' => 'QW'],
                ];
                
                foreach ($urls as $u) {
                    if (str_contains($u['episode_server_name'], 'muilt')) {
                        [$mc, $md] = acurl($u['episode_url']);
                        $j = is_string($md) ? json_decode($md, true) : $md;
                        if (is_array($j)) {
                            foreach ($j as $idx => $directUrl) {
                                $matched = false;
                                foreach ($serverMap as $k => $v) {
                                    if (str_contains($directUrl, $k)) {
                                        $quality = '';
                                        if ($k === 'mediafire') {
                                            if (preg_match('/_(uhd|1080p|hh)\.mp4/i', $directUrl)) $quality = ' : عالية جدا 1080p';
                                            elseif (preg_match('/_(h|720p)\.mp4/i', $directUrl)) $quality = ' : عالية 720p';
                                            elseif (preg_match('/_(s|480p)\.mp4/i', $directUrl)) $quality = ' : متوسطة 480p';
                                            elseif (preg_match('/_(m|360p)\.mp4/i', $directUrl)) $quality = ' : منخفضة 360p';
                                        }
                                        $newUrls[] = [
                                            'episode_url_id' => $u['episode_url_id'] . '_' . $idx,
                                            'episode_server_id' => $v['label'],
                                            'episode_server_name' => $v['name'] . $quality,
                                            'episode_url' => $directUrl
                                        ];
                                        $matched = true;
                                        break;
                                    }
                                }
                                if (!$matched) {
                                    $host = parse_url($directUrl, PHP_URL_HOST);
                                    $newUrls[] = [
                                        'episode_url_id' => $u['episode_url_id'] . '_' . $idx,
                                        'episode_server_id' => 'LINK',
                                        'episode_server_name' => $host ? str_replace('www.', '', $host) : 'direct',
                                        'episode_url' => $directUrl
                                    ];
                                }
                            }
                        } else {
                           $newUrls[] = $u; 
                        }
                    } else {
                        $newUrls[] = $u;
                    }
                }
                
                // Now apply extractor logic to ALL URLs so we don't need a separate resolve step
                $finalUrls = [];
                foreach ($newUrls as $u) {
                    $url = $u['episode_url'];
                    $extractedUrl = $url;
                    
                    // Already a direct media link — return as-is
                    if (preg_match('/\.(mp4|webm|m3u8)([\/?]|$)/i', $url)) {
                        $extractedUrl = $url;
                    // MediaFire: direct .mp4 downloads are blocked by CORS in browsers.
                    // Keep the page URL so the client shows a "Open MediaFire" fallback.
                    } elseif (str_contains($url, 'mediafire')) {
                        $extractedUrl = $url;
                    } elseif (str_contains($url, 'goodstream') || str_contains($url, 'lulustream') || str_contains($url, 'streamtape') || str_contains($url, 'filemoon') || str_contains($url, 'mixdrop')) {
                        $ch = curl_init($url);
                        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_SSL_VERIFYPEER => false, CURLOPT_FOLLOWLOCATION => true, CURLOPT_TIMEOUT => 5, CURLOPT_USERAGENT => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36']);
                        $res = curl_exec($ch);
                        curl_close($ch);
                        
                        $found = false;
                        if (str_contains($url, 'goodstream') || str_contains($url, 'lulustream')) {
                            if (preg_match('/file:\s*"([^"]+)"/', $res, $m)) {
                                $extractedUrl = $m[1]; $found = true;
                            } elseif (preg_match('/file:\s*\'([^\']+)\'/', $res, $m)) {
                                $extractedUrl = $m[1]; $found = true;
                            } elseif (preg_match('/sources:\s*\[\{\s*file:\s*"([^"]+)"/', $res, $m)) {
                                $extractedUrl = $m[1]; $found = true;
                            }
                        } elseif (str_contains($url, 'streamtape')) {
                            if (preg_match('/document\.getElementById\(\'norobotlink\'\)\.innerHTML = (.*);/', $res, $m)) {
                                if (preg_match('/token=([^&\']+)/', $m[1], $tm)) {
                                    if (preg_match('/<div id="ideoooolink" style="display:none;">(.*)<\/div>/', $res, $fm)) {
                                        $host = parse_url($url, PHP_URL_HOST);
                                        $finalUrl = explode($host, $fm[1])[1];
                                        $extractedUrl = 'https://' . $host . $finalUrl . '&token=' . $tm[1] . '&dl=1';
                                        $found = true;
                                    }
                                }
                            }
                        } elseif (str_contains($url, 'filemoon')) {
                            if (preg_match('/file:\s*"([^"]+)"/', $res, $m)) {
                                $extractedUrl = $m[1]; $found = true;
                            } elseif (preg_match('/<source\s+src="([^"]+)"/', $res, $m)) {
                                $extractedUrl = $m[1]; $found = true;
                            }
                        } elseif (str_contains($url, 'mixdrop')) {
                            if (preg_match('/location\s*=\s*"([^"]+)"/', $res, $m)) {
                                $extractedUrl = $m[1]; $found = true;
                            }
                        }
                        // If scraping failed but it's an embed URL, keep as-is for iframe fallback
                        if (!$found && preg_match('/\/e\/|\/embed\/|videoembed|\/player\.php/i', $url)) {
                            $extractedUrl = $url;
                        }
                    }
                    $u['episode_url'] = $extractedUrl;
                    $finalUrls[] = $u;
                }
                $urls = $finalUrls;
            }
            echo json_encode(['episode_urls' => $urls]);
            break;
        default:
            echo json_encode(['error' => 'unknown action', 'action' => $action]);
    }
} catch (Exception $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
