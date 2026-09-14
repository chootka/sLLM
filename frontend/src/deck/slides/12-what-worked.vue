<template>
<div class="content">
<h2>What worked</h2>
<p class="lead">Successfully recorded a distinct signal against the noise.</p>
<ul>
<li>An instrument that can tell a signal from its own noise. <b>0.02&ndash;0.10 mV</b>
per sample, down from 0.7&ndash;2.8</li>
<li>A <b>2.2&ndash;2.4 minute</b> oscillation, 0.5&ndash;1.8 mV, on colonized electrodes
only</li>
<li>The threshold that would have called it an artifact was written down <b>before</b>
the control data was read</li>
<li>One unplanned on/off event, with a simultaneous control</li>
</ul>
</div>
<div class="content">
<h2>What didn&rsquo;t</h2>
<p class="lead">Some obstacles to think through.</p>
<ul>
<li>Kept triggering slime mould sporangia, which cuts feedback loops short</li>
<li>This is due to using light as a lever</li>
<li>Need to explore other levers</li>
</ul>
</div>
<div class="content">
<h2>What&rsquo;s next</h2>
<p class="lead">Where the work goes from here.</p>
<ul>
<li>Build a way for the model to reward the slime mould</li>
<li>Create a PCB in order to run parallel experiments</li>
<li>Refine the measurements, prompts, audio/visual output</li>
<li>VST and Eurorack module development</li>
<li>Write all the findings up in a paper, to be published in 2028</li>
</ul>
</div>
</template>

<script>
export default {
  name: '12_what_worked',
  meta: {
    classes: 'split thirds',
    section: 'What worked',
    reg: 0.24, fx: 32, fy: 60
  }
}
</script>
