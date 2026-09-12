<template>
<div class="content">
<h2>The live dashboard</h2>

  <ul class="points"><li><span class="mark">CAMERA</span>
<span><b>Livestream</b> and <b>timelapse</b> recordings of the dish</span></li><li><span class="mark">DATA</span><span>Graphs of the <b>raw electrode signal</b> and the reduced slime-mould signal</span></li><li><span class="mark">LOG</span><span>The <b>model's logs</b>: what it asked for, what was applied</span></li><li><span class="mark">ADMIN</span><span>Remote control of the experiment parameters</span></li><li><span class="mark">ARCHIVE</span><span>Every past run, browsable</span></li></ul>
<h3>The presentation layer at /drift</h3>
<ul class="points">
<li><span class="mark">from</span><span>A unix timestamp. Without it, /drift follows the live dish.</span></li>
<li><span class="mark">mins</span><span>How long a stretch to play, 1 to 240 minutes.</span></li>
<li><span class="mark">speed</span><span>Playback rate, 1 to 240 times real time.</span></li>
</ul>
</div>
<figure class="media">
<img class="only-light" src="/deck-media/dashboard-light.jpg" alt="The dashboard in light mode: livestream, electrode graphs and the model log">
<img class="only-dark" src="/deck-media/dashboard-dark.jpg" alt="The dashboard in dark mode: livestream, electrode graphs and the model log">
</figure>
</template>

<script>
export default {
  name: '08_the_web_layer_and',
  meta: {
    classes: 'split',
    section: 'What was built',
    reg: 0.62, fx: 44, fy: 58
  }
}
</script>
