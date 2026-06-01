<?php $baseUrl = ''; ?>
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Anime Slayer Web</title><link rel="stylesheet" href="style.css"></head>
<body>
<header>
<div class="container">
<h1>Anime<span>Slayer</span></h1>
<form onsubmit="search(event)">
<input type="text" id="q" placeholder="Search anime..." value="<?=htmlspecialchars($_GET['q']??'')?>">
<button type="submit">Search</button>
</form>
</div>
</header>
<div class="container">
<div class="categories" id="categories"></div>
<div id="results" class="section"></div>
<div id="pagination" class="pagination"></div>
</div>
<footer>Anime Slayer Web Interface</footer>
<script>
let currentType = 'latest_episodes', currentQuery = '', currentPage = 0;

const cats = [
    {id:'latest_episodes',name:'Latest'},{id:'currently_airing',name:'Airing'},
    {id:'top_anime',name:'Top'},{id:'featured',name:'Featured'},
    {id:'top_tv',name:'Top TV'},{id:'top_movie',name:'Movies'},
    {id:'schedule',name:'Schedule'}
];

function loadCategories(){
    const el = document.getElementById('categories');
    el.innerHTML = cats.map(c =>
        `<a href="#" class="${c.id===currentType?'active':''}" onclick="loadAnime('${c.id}');return false">${c.name}</a>`
    ).join('') + `<a href="#" onclick="loadAnime('favorites');return false">Favorites</a>`;
}

function search(e){e.preventDefault();currentQuery=document.getElementById('q').value;currentPage=0;loadAnime('all');}

function loadAnime(type){
    currentType = type;
    const el = document.getElementById('results');
    el.innerHTML = '<div class="loading">Loading...</div>';
    document.querySelectorAll('.categories a').forEach(a=>a.classList.remove('active'));
    const q = currentQuery;
    let params = new URLSearchParams({action:'search',type,limit:25,offset:currentPage*25});
    if(q)params.set('q',q);
    fetch(`api?${params}`).then(r=>r.json()).then(({data})=>{
        if(!data||!data.response||!data.response.data){
            el.innerHTML='<div class="error">No results found</div>';return;
        }
        const list = data.response.data;
        el.innerHTML = `<h2>${q ? 'Search: ' + q : cats.find(c=>c.id===type)?.name||'Anime'}</h2>
        <div class="anime-grid">${list.map(a=>`
            <a href="anime?id=${a.anime_id}" class="anime-card">
                <img src="${a.anime_cover_image_url||''}" alt="${a.anime_name}" loading="lazy" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22300%22><rect fill=%22%231a1a2e%22 width=%22200%22 height=%22300%22/></svg>'">
                <div class="info">
                    <h3>${a.anime_name}</h3>
                    <div class="meta"><span>${a.anime_type||''}</span><span class="rating">★${a.anime_rating||'?'}</span></div>
                </div>
            </a>
        `).join('')}</div>`;
    }).catch(()=>el.innerHTML='<div class="error">Failed to load</div>');
    loadCategories();
}

loadCategories();
loadAnime(currentType);
</script>
</body>
</html>
