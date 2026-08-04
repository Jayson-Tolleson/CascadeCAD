import"./modulepreload-polyfill-B5Qt9EMX.js";const e=document.querySelector("#site-app")??document.querySelector("#app")??document.body;e.innerHTML=`
  <main class="home">
    <header class="titlebar">
      <h1>LFTR.biz</h1>
    </header>

    <section class="frame watch-frame" aria-label="LFTR watch viewport">
      <iframe src="/watch" title="LFTR Watch" allow="autoplay; fullscreen; picture-in-picture; camera; microphone"></iframe>
    </section>

    <section class="frame globe-frame" aria-label="LFTR marine globe viewport">
      <iframe src="/gfs" title="LFTR Marine Intelligence Globe" allow="fullscreen; geolocation"></iframe>
    </section>

    <section class="frame youtube-frame" aria-label="LFTR YouTube playlist">
      <iframe
        src="https://www.youtube.com/embed/videoseries?list=PLVIftPRSOIthwubkq9WzCSk7B-mqaJ89B"
        title="LFTR YouTube playlist"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen>
      </iframe>
    </section>
  </main>
`;
