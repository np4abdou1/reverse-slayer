<?php $id = (int)($_GET['id'] ?? 0); if (!$id) { header('Location: /'); exit; } ?>
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loading Anime...</title><link rel="stylesheet" href="style.css"></head>
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
<a href="/" class="back-link">← Back</a>
<div id="content"><div class="loading">Loading anime details...</div></div>
</div>
<footer>Anime Slayer Web Interface</footer>
<script>
const id = <?=$id?>;
fetch(`api?action=detail&id=${id}`).then(r=>r.json()).then(({data})=>{
    if(!data||!data.response){document.getElementById('content').innerHTML='<div class="error">Anime not found</div>';return;}
    const a = data.response;
    const eps = a.episodes?.data || [];
    const el = document.getElementById('content');
    el.innerHTML = `
    <div class="anime-detail">
        <div class="poster"><img src="${a.anime_cover_image_url||''}" alt="${a.anime_name}" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22400%22><rect fill=%22%231a1a2e%22 width=%22300%22 height=%22400%22/></svg>'"></div>
        <div class="info">
            <h1>${a.anime_name}</h1>
            <div style="color:#888;font-size:14px">${a.anime_english_title||''}</div>
            <div class="tags">
                <span>${a.anime_type||'?'}</span>
                <span>${a.anime_status||'?'}</span>
                <span>${a.anime_season||''} ${a.anime_release_year||''}</span>
                <span>★ ${a.anime_rating||'?'} (${(a.anime_rating_user_count||'0')})</span>
                ${a.anime_age_rating ? `<span>${a.anime_age_rating}</span>` : ''}
            </div>
            <div class="tags">${(a.anime_genres||'').split(',').filter(Boolean).map(g=>`<span>${g.trim()}</span>`).join('')}</div>
            <div class="desc">${a.anime_description||'No description available.'}</div>
        </div>
    </div>
    <div class="section">
        <h2>Episodes (${eps.length})</h2>
        <div class="episode-list">${eps.length?eps.map(e=>`
            <a href="watch?id=${id}&ep=${e.episode_id}&name=${encodeURIComponent(e.episode_name)}" class="episode-card">
                <div class="num">${e.episode_number||'?'}</div>
                <div class="name">${e.episode_name||''}</div>
                <div class="rating">★ ${e.episode_rating||'?'}</div>
            </a>
        `).join(''):'<div style="color:#666">No episodes available yet.</div>'}</div>
    </div>`;
}).catch(()=>document.getElementById('content').innerHTML='<div class="error">Failed to load anime</div>');
</script>
</body>
</html>
