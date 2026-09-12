<template>
<div class="hold">
<h2>The web layer, and /drift</h2>
<div class="cols">
  <div><ul class="points"><li><span class="mark">LIVE</span><span>Livestream of the dish</span></li><li><span class="mark">DATA</span><span>Graphs of the <b>raw electrode signal</b> and the reduced slime-mould signal</span></li><li><span class="mark">LOG</span><span>The <b>model's logs</b> — what it asked for, what was applied</span></li><li><span class="mark">ADMIN</span><span>Remote control of the experiment parameters</span></li><li><span class="mark">ARCHIVE</span><span>Every past run, browsable</span></li></ul></div>
  <div class="drift-col">
    <p class="k">/drift — the presentation layer</p>
    <p>Slide a window over the historical record; set the playback rate. Not a convenience
    setting: at real time the link between image and sound is imperceptible, and
    compressed too far the two collapse into simultaneity.</p>
    
  </div>
</div>
<p class="foot-note"><b>What /drift is for:</b> approximating, for a visitor, the feeling
of a vein contracting and expanding. That cycling is found throughout life itself.</p></div><figure class="dish"><img src="/deck-media/the-organism-spread-between-islands-5.jpg" alt="The organism spread between islands, 5 September"></figure>
</template>

<script>
export default {
  name: '07_the_web_layer_and',
  meta: {
    classes: 'dish-right lay-split-offset',
    section: 'What was built',
    reg: 0.62, fx: 44, fy: 58
  }
}
</script>
