<?php
$id = (int)($_GET['id'] ?? 0);
$ep = (int)($_GET['ep'] ?? 0);
$name = htmlspecialchars($_GET['name'] ?? 'Episode');
$animeName = htmlspecialchars($_GET['anime'] ?? '');
if (!$id || !$ep) { header('Location: /'); exit; }
?>
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Watch - <?=$name?></title><link rel="stylesheet" href="style.css">
<script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
</head>
<body>
<header>
<div class="container">
<h1><a href="/" style="color:#fff">Anime<span>Slayer</span></a></h1>
<form action="/" method="get">
<input type="text" name="q" placeholder="Search anime...">
<button type="submit">Search</button>
</form>
</div>
</header>
<div class="container">
<a href="anime?id=<?=$id?>" class="back-link">← Back to Anime</a>
<h2 style="margin:10px 0" id="epTitle"><?=$name?></h2>

<div id="serverTabs" class="server-tabs"></div>

<div id="player" class="watch-container">
    <div class="video-player">
        <div class="video-placeholder">
            <h3>Select a server to start watching</h3>
            <p style="color:#555;margin-top:8px">Choose from the server tabs above</p>
        </div>
    </div>
</div>
</div>
<footer>Anime Slayer Web Interface</footer>

<script>
const animeId = <?=$id?>;
const episodeId = <?=$ep?>;
let currentServer = null;
const PLAYER_HOSTS = {
    'ok.ru': { type: 'embed', getUrl: (url) => {
        const id = url.split('/').pop();
        return `https://ok.ru/videoembed/${id}`;
    }},
    'filemoon.sx': { type: 'embed', getUrl: (url) => url },
    'streamtape': { type: 'embed', getUrl: (url) => url.replace('/v/', '/e/') },
    'mediafire': { type: 'download', getUrl: (url) => url },
    'mystream': { type: 'embed', getUrl: (url) => url },
    'vk.com': { type: 'embed', getUrl: (url) => url },
};

function getEmbedUrl(url) {
    for (const [host, cfg] of Object.entries(PLAYER_HOSTS)) {
        if (url.includes(host)) return cfg.getUrl(url);
    }
    if (url.includes('youtube') || url.includes('youtu.be')) {
        const m = url.match(/(?:v=|youtu\.be\/)([\w-]+)/);
        return m ? `https://www.youtube.com/embed/${m[1]}` : url;
    }
    return url;
}

function getHostLabel(url) {
    try { return new URL(url).hostname.replace('www.', ''); } catch { return 'link'; }
}

function playUrl(url) {
    const embedUrl = getEmbedUrl(url);
    const isM3U8 = url.includes('.m3u8');
    const isDirectVideo = /\.(mp4|webm)([\/?]|$)/i.test(url) && !url.includes('mediafire.com');
    const el = document.getElementById('player');
    
    if (url.includes('mediafire.com')) {
        el.innerHTML = `<div class="video-player"><div class="video-placeholder"><h3>MediaFire Link</h3><p><a href="${url}" target="_blank" class="btn">Download / Open MediaFire</a></p></div></div>`;
    } else if (isM3U8) {
        el.innerHTML = `<div class="video-player"><video id="hls-video" controls autoplay></video></div>`;
        const video = document.getElementById('hls-video');
        if (Hls.isSupported()) {
            const hls = new Hls();
            hls.loadSource(url);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, function() {
                video.play();
            });
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = url;
            video.addEventListener('loadedmetadata', function() {
                video.play();
            });
        }
    } else if (isDirectVideo) {
        el.innerHTML = `<div class="video-player"><video controls autoplay><source src="${url}"></video></div>`;
    } else {
        el.innerHTML = `<div class="video-player"><iframe src="${embedUrl}" allowfullscreen loading="lazy"></iframe></div>`;
    }
}

// Load servers from API
async function loadServers() {
    const tabsEl = document.getElementById('serverTabs');
    tabsEl.innerHTML = '<div class="loading" style="padding:10px">Loading servers...</div>';

    try {
        const r = await fetch(`api?action=servers&anime_id=${animeId}&episode_id=${episodeId}`);
        const data = await r.json();
        const urls = data.episode_urls || [];

        if (!urls.length) {
            tabsEl.innerHTML = '<div style="color:#888;padding:10px">No servers available for this episode.</div>';
            return;
        }

        tabsEl.innerHTML = '';
        urls.forEach((srv, i) => {
            const btn = document.createElement('button');
            btn.className = 'server-tab' + (i === 0 ? ' active' : '');
            btn.innerHTML = `${srv.episode_server_name} <span class="badge">(${srv.episode_server_id})</span>`;
            btn.onclick = () => {
                document.querySelectorAll('.server-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentServer = srv;
                playUrl(srv.episode_url);
            };
            tabsEl.appendChild(btn);
        });

        // Auto-click first server
        tabsEl.firstChild?.click();
    } catch (e) {
        tabsEl.innerHTML = '<div class="error">Failed to load servers</div>';
    }
}

loadServers();
</script>
</body>
</html>
