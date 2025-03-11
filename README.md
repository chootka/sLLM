# sLLM (slime Large Language Model)

## PROJECT OVERVIEW
sLLM, or "slime Large Language Model," is an experimental interactive art installation that creates a communication bridge between humans and Physarum polycephalum (common slime mold). Through a custom-built chat interface, humans can send messages that are translated into environmental stimuli for the slime mold. The slime mold's electrical responses are then captured, interpreted, and translated back into natural language.

This project explores whether meaningful patterns of communication can emerge between radically different forms of intelligence. By mapping electrical responses from a non-human living organism to a computational language model, sLLM questions our understanding of communication, intelligence, and the boundaries between biological and artificial systems.

## ARTIST'S STATEMENT
Slime molds occupy a fascinating biological niche - despite being single-celled organisms, they exhibit surprisingly complex behaviors including problem-solving capabilities and environmental adaptation. Scientists study them for their prototypical neuron-like behaviors, drawing parallels to much more complex nervous systems.

Meanwhile, Large Language Models attempt to simulate human-like reasoning and communication through computational means. Both systems represent different approaches to "intelligence" - one evolved through billions of years of biological processes, the other engineered through mathematical models and trained on human-created data.

sLLM began conceptually as a playful response to the widespread cultural fascination with artificial intelligence. The initial idea was simply to place a live-streamed slime mold beside a chat interface, creating a humorous juxtaposition between cutting-edge AI chat experiences and the slow, alien intelligence of a simple organism.

However, this evolved into a more substantive exploration of cross-species communication. The project doesn't claim to achieve "true" communication with slime molds, but instead examines what happens when we create systems that translate between fundamentally different modes of being. By exposing the slime mold to various controlled stimuli (changes in temperature, humidity, light frequency, and chemical environment) in response to human text input, we can observe whether consistent patterns emerge in the organism's electrical activity.

This isn't traditional scientific research but rather an artistic experiment that prompts us to question our assumptions about communication, consciousness, and the increasingly blurry line between biological and artificial intelligence. Like using a car to carry water instead of people, we might discover unexpected capabilities and connections through this deliberate misuse of both biological systems and language models.

## TECHNICAL COMPONENTS

### 1: Enclosure Fabrication
- Modular compartmented enclosure with stackable boxes and sliding trays
- Separate sections for camera/lighting, slime mold habitat, and electronics
- Sealed ports with rubber stoppers for:
  - Power connections
  - Ethernet cable
  - Electrode wires
  - Additional sensors
- Climate-controlled environment to maintain optimal conditions for the slime mold

### 2: Hardware and Sensors
- Raspberry Pi 5 as the central computing unit
- Ag/Cl electrodes for detecting electrical activity in the slime mold
- Environmental monitoring:
  - Humidity sensor
  - Temperature sensor
  - Light sensors
- Automated oat feeder (repurposed fish feeder)
- High-resolution macro web camera
- Adjustable ring light for consistent imaging
- Climate control system (temperature and humidity regulators)
- Powered USB hub for multiple peripheral connections

### 3: Software Architecture

#### LLM Component
- Self-hosted large language model
- API endpoints:
  - Receive text input from web interface
  - Process responses through encoder
  - Return generated text to interface
- Web-based chat interface for human interaction

#### Live Stream Component
- Video streaming application
- API endpoints:
  - Stream access
  - Lighting control
- Web interface displaying the live slime mold feed

#### Environment Control Component
- Serial communication with sensors and controllers
- API endpoints:
  - Monitor temperature, humidity, and electrode readings
  - Control environmental stimuli (feeding, temperature, humidity, light)
- Web dashboard for environmental statistics, graphs, and electrical response data

#### Encoder/Decoder Component
- Translation layer between natural language and environmental stimuli
- API endpoints:
  - Convert text input to stimuli patterns
  - Transform electrical readings into data compatible with the LLM
  - Generate natural language responses based on slime mold activity

## CURRENT ROLES
- LLM development: @pimtournaye, @k0a1a
- Enclosure Design & Fabrication: @k0a1a
- Full-Stack Web Development: @chootka
- Embedded Systems Engineering: @chootka
- Biological Systems: TBD

### COLLABORATION OPPORTUNITIES

TBD - some of these tasks are already underway, but there may be need for future colllaborators for the following tasks:

1. **LLM Implementation**: Setting up and fine-tuning a self-hosted language model, developing the translation algorithms between electrical signals and language.
   
2. **Enclosure Design & Fabrication**: Creating a modular, functional enclosure that maintains optimal conditions while allowing for observation and interaction.

3. **Full-Stack Web Development**: Building the interactive chat interface, live stream display, and data visualization dashboard.

4. **Embedded Systems Engineering**: Implementing sensor arrays, environmental controls, and reliable data collection from the slime mold.

5. **Biological Systems**: Advising on optimal conditions for slime mold health and activity, helping interpret biological responses.

## TIMELINE & (rrrrrough) MILESTONES

### Phase 1: Infrastructure Development (2 months)
- Complete enclosure fabrication
- Set up environmental monitoring and control
- Establish basic LLM integration
- Develop core APIs and web interfaces
- Configure web server and hosting

### Phase 2: Pattern Recognition (1-2 months)
- Cultivate slime molds
- Calibrate electrode sensitivity
- Begin systematic testing of stimuli
- Document and analyze electrical response patterns
- Refine sensor data collection

### Phase 3: Integration & Refinement (2 months)
- Implement pattern-to-language mapping
- Tune response algorithms
- Test end-to-end communication flow
- Optimize real-time performance
- Prepare for public release (?)

## RESOURCES & MATERIALS

Resources on hand:
- GitHub repository: https://github.com/chootka/sLLM/
- Raspberry Pi 5
- Basic sensors (temperature, humidity)
- Web development expertise
- Custom enclosure materials
- High-resolution macro camera
- Ring lighting system
- Hosting for self-deployed LLM

Resources needed:
- Ag/Cl electrodes
- Additional sensors and electronics TBD

## ADDITIONAL NOTES

This project is a mix of biological art, interactive installation, and speculative design. While the scientific validity of "communicating" with slime molds is questionable, the artistic value lies in the attempt and what it reveals about our desire to connect with non-human intelligence.

The installation could be exhibited in various contexts including galleries, science museums, or your local forest.

---

*Last updated: March 11, 2025*

*Contact: com@chootka.com*
