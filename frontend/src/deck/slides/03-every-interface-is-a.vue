<template>
<div class="hold">
<h2 class="oneline">Every interface is a reduction</h2>
<div class="xfer">
  <div class="side">
    <p class="k">Organism → model</p>
    <p class="big-n">4</p>
    <p class="cap">numbers, every fifteen minutes: period, amplitude, the phase lag
    between electrodes, baseline drift</p>
  </div>
  <div class="mid" aria-hidden="true"></div>
  <div class="side">
    <p class="k">Model → organism</p>
    <p class="big-n">1</p>
    <p class="cap">action: light one of nine regions. It is never told whether it had
    any effect</p>
  </div>
</div>
<p class="foot-note">Nothing else crosses in either direction. Deciding what those four
numbers are is most of the design work — and so is deciding what the model is told it is holding. Seven prompts, one interface:</p><div class="prompts"><div><span class="pn">BLIND</span><p>The default. The model is given the interface and nothing else, and is never told what it is coupled to.</p></div><div><span class="pn">INFORMED</span><p>The same interface, plus the name of the organism. The difference from BLIND is what the model's priors about Physarum contribute.</p></div><div><span class="pn">CYCLES</span><p>The period is withheld. The model has to estimate it, and every duration it sets is converted using its own estimate.</p></div><div><span class="pn">ADVERSARIAL</span><p>The organism's activity consumes the model's context. Quiet turns cost less, and blue light quiets the organism.</p></div><div><span class="pn">METERED</span><p>The organism's period sets the model's memory budget. Shorter period, more context. What light does to the period is not stated.</p></div><div><span class="pn">MIMIC</span><p>Physarum's architecture rather than its vocabulary. No history, a decaying trail on the surface instead, changes rather than values, no note.</p></div><div><span class="pn">NULL</span><p>BLIND with the task removed. If the notes still claim influence, the claim is coming from the format and not from the data.</p></div></div></div><figure class="dish"><img src="/deck-media/the-organism-massed-around-the-central.jpg" alt="The organism massed around the central island, 6 September"></figure>
</template>

<script>
export default {
  name: '03_every_interface_is_a',
  meta: {
    classes: 'dish-right lay-wide',
    section: 'The question',
    reg: 0.55, fx: 50, fy: 52
  }
}
</script>
