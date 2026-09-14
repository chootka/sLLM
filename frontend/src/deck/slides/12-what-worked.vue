<template>
<!-- Three columns, revealed one at a time. The row is always three tracks
     wide; what changes is how far it is pushed right so the revealed columns
     land centred. -->
<div class="reveal-row" :data-step="deck.step">
<div class="content">
<h2>What worked</h2>
<p class="lead">Successfully captured a distinct bio-signal.</p>
<ul>
<li>An instrument that can tell a signal from its own noise. <b>0.02&ndash;0.10 mV</b>
per sample, down from 0.7&ndash;2.8</li>
<li>A <b>2.2&ndash;2.4 minute</b> oscillation, 0.5&ndash;1.8 mV, on colonized electrodes
only</li>
<li>One unplanned on/off event, with a simultaneous control</li>
</ul>
</div>
<div class="content">
<h2>What didn&rsquo;t</h2>
<p class="lead">Environmental challenges.</p>
<ul>
<li>Light as a lever triggered sporangia every time</li>
<li>Slime starved itself, rejecting the oats</li>
<li>Despite maintaining humidity, agar blobs drying up too soon</li>
</ul>
</div>
<div class="content">
<h2>What&rsquo;s next</h2>
<p class="lead">Immediate next steps.</p>
<ul>
<li>Build a way for the model to reward the slime mould</li>
<li>Create a PCB in order to run parallel experiments</li>
<li>Refine the measurements, prompts, audio/visual output</li>
<li>VST and Eurorack module development</li>
<li>Write all the findings up in a paper, to be published in 2028</li>
</ul>
</div>
</div>
</template>

<script>
export default {
  name: '12_what_worked',
  inject: ['deck'],
  meta: {
    classes: 'reveal',
    section: 'What worked',
    steps: 2,
    reg: 0.24, fx: 32, fy: 60
  }
}
</script>
