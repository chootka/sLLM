<template>
<div class="content">
<h2>The system hosted on a Raspberry Pi</h2>
<div class="chart"><svg viewBox="0 0 880 400" class="fig diag" role="img" aria-label="System diagram: the dish is sensed by electrodes and a climate sensor, a Raspberry Pi records and decides, actuators act back on the dish, and a web layer serves the livestream, graphs, admin panel, archive and the audiovisual piece">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--axis)"/></marker></defs>
<rect x="8" y="40" width="176" height="106" rx="3" fill="var(--panel)" stroke="var(--accent)" stroke-width="1.6"/>
<text x="22" y="62" class="bt">THE DISH</text>
<text x="22" y="82" class="bl">Physarum plasmodium</text>
<text x="22" y="98" class="bl">4 agar islands</text>
<text x="22" y="114" class="bl">3 electrodes + ref</text>
<rect x="238" y="40" width="176" height="106" rx="3" fill="var(--panel)" stroke="var(--rule)" stroke-width="1"/>
<text x="252" y="62" class="bt">SENSE</text>
<text x="252" y="82" class="bl">electrodes, 1 Hz</text>
<text x="252" y="98" class="bl">temp / humidity</text>
<text x="252" y="114" class="bl">camera, timelapse</text>
<rect x="468" y="22" width="176" height="142" rx="3" fill="var(--panel)" stroke="var(--accent)" stroke-width="1.6"/>
<text x="482" y="44" class="bt">RASPBERRY PI</text>
<text x="482" y="64" class="bl">records to CSV</text>
<text x="482" y="80" class="bl">reduction layer</text>
<text x="482" y="96" class="bl">local language model</text>
<text x="482" y="112" class="bl">one action: light</text>
<rect x="698" y="40" width="174" height="106" rx="3" fill="var(--panel)" stroke="var(--rule)" stroke-width="1"/>
<text x="712" y="62" class="bt">ACT</text>
<text x="712" y="82" class="bl">LED matrix, 9 zones</text>
<text x="712" y="98" class="bl">fan + relay</text>
<text x="712" y="114" class="bl"></text>
<line x1="186" y1="93" x2="236" y2="93" stroke="var(--axis)" stroke-width="1.5" marker-end="url(#ah)"/>
<line x1="416" y1="93" x2="466" y2="93" stroke="var(--axis)" stroke-width="1.5" marker-end="url(#ah)"/>
<line x1="646" y1="93" x2="696" y2="93" stroke="var(--axis)" stroke-width="1.5" marker-end="url(#ah)"/>
<path d="M785,148 L785,196 L96,196 L96,148" fill="none" stroke="var(--axis)" stroke-width="1.5" marker-end="url(#ah)"/>
<text x="440" y="189" class="al" text-anchor="middle">blue light on the chamber — the only thing the model can change</text>
<rect x="238" y="236" width="406" height="90" rx="3" fill="var(--panel)" stroke="var(--rule)" stroke-width="1"/>
<text x="252" y="258" class="bt">WEB, ON THE PI</text>
<text x="252" y="278" class="bl">livestream · raw electrode graphs · reduced signal</text>
<text x="252" y="294" class="bl">model log · admin panel · run archive</text>
<rect x="698" y="236" width="174" height="90" rx="3" fill="var(--panel)" stroke="var(--accent)" stroke-width="1.6"/>
<text x="712" y="258" class="bt">/drift</text>
<text x="712" y="278" class="bl">the A/V piece</text>
<text x="712" y="294" class="bl">window + playback rate</text>
<line x1="556" y1="166" x2="556" y2="234" stroke="var(--axis)" stroke-width="1.5" marker-end="url(#ah)"/>
<line x1="646" y1="281" x2="696" y2="281" stroke="var(--axis)" stroke-width="1.5" marker-end="url(#ah)"/>

<text x="8" y="378" class="al">Everything above sits on three files: the electrode record, the climate record, the images.</text>
</svg></div>
<p class="note">Everything sits on three files: the electrode record, the climate
record, the images. None of the rest is required in order to record.</p></div><figure class="media"><img src="/deck-media/the-dish-before-inoculation-four-electrodes.jpg" alt="The dish before inoculation: four electrodes, agar islands and oat flakes"></figure>
</template>

<script>
export default {
  name: '06_the_system_hosted_on',
  meta: {
    classes: 'split media-first content-wide',
    section: 'What was built',
    reg: 0.48, fx: 50, fy: 50
  }
}
</script>
