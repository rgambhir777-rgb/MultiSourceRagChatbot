# Orbit T2 Smart Thermostat — User Handbook

Lumen Home is a fictional company. This handbook is sample data for the MultiSource RAG Chatbot.

The Orbit T2 is a Wi-Fi smart thermostat for homes with central heating, cooling or heat pumps.
It learns your schedule, adjusts itself when nobody is home, and reports energy use in the
Lumen Home app.

## What's in the box

- Orbit T2 display unit
- Wall base plate with a built-in spirit level
- Four wall screws and anchors
- Optional trim plate to cover old paint marks
- Common wire (C-wire) adapter kit
- Wire labels and this quick-start guide

## Installation

Installing the Orbit T2 takes about 30 minutes. You need a Phillips screwdriver and a drill if
your wall needs new anchors.

### Before you start

Turn off power to your heating and cooling system at the breaker. Check that the system is
really off by changing the temperature on your old thermostat: nothing should start. Take a
photo of the old wiring before removing any wire. The photo is the most useful thing you will
have if something goes wrong later.

The Orbit T2 is a low-voltage (24 V) thermostat. It is not compatible with line-voltage (120 V
or 240 V) systems such as electric baseboard heaters. If your old thermostat has thick wires
connected with wire nuts, it is probably line-voltage: stop and contact a professional.

### Wiring the base plate

Attach the wire labels to each wire using the letters printed on the old thermostat terminals.
Remove the old thermostat and its base. Hold the Orbit base plate against the wall, use the
built-in level to make it straight, and mark the screw holes.

Connect each labelled wire to the matching terminal: R or Rh to R, W to W1, Y to Y1, G to G and
C to C. If you have both Rc and Rh wires, use the jumper switch on the base plate to separate
them. Push each wire in until the terminal button pops up.

### Power and the C-wire

The Orbit T2 needs continuous power. Most systems provide it through a common wire (C-wire). If
your system has no C-wire, install the included adapter at the furnace control board following
its own instructions. Running without a C-wire causes error E-114 (low power) and random reboots.

### First start-up

Clip the display onto the base plate and turn the breaker back on. The display shows the Lumen
logo, then asks for your language. The thermostat runs a wiring check that takes about two
minutes. If the check finds a problem, it shows an error code; see the troubleshooting guide.

## Connecting to Wi-Fi

The Orbit T2 supports 2.4 GHz and 5 GHz Wi-Fi networks using WPA2 or WPA3 security. Enterprise
networks that need a username, such as some office networks, are not supported.

To connect, open the Lumen Home app, tap **Add device**, and scan the QR code on the back of the
display. The app sends your Wi-Fi details to the thermostat over Bluetooth. Connection usually
takes under a minute. If it fails, the display shows error E-207.

You can change networks later in **Settings > Network** on the thermostat itself.

## Schedules and Auto-Learn

### Manual schedules

A schedule is a list of target temperatures for each part of the day. Create one in the app
under **Schedule**. You can copy a day's schedule to other days to save time. Each day supports
up to eight temperature changes.

### Auto-Learn

Auto-Learn watches when you adjust the temperature during the first seven days and builds a
schedule for you. After the first week it keeps making small changes based on your habits. You
can turn Auto-Learn off at any time in **Settings > Auto-Learn**. Turning it off keeps the last
learned schedule.

### Away mode

Away mode lowers heating or raises cooling when nobody is home, using your phone's location and
the thermostat's motion sensor. The default Away temperatures are 16 °C for heating and 29 °C
for cooling. Away mode never lets the home drop below the frost-protection limit of 7 °C.

## Energy reports

Every month the app shows how many hours your system ran, compared with the month before and
with similar homes in your area. A green leaf on the display means the current setting saves
energy. Energy reports never include your location or exact address.

## Software updates

The thermostat updates itself automatically at night between 2 a.m. and 4 a.m. local time.
Updates take about five minutes, and heating or cooling keeps working during an update. You can
check the installed version in **Settings > About**.

## Privacy

Temperature history is stored for 24 months, then deleted. You can download or delete your data
at any time from the app under **Account > Privacy**. Lumen Home does not sell personal data.
Motion-sensor data never leaves the device; only the result "home" or "away" is sent to the app.
