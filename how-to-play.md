# How to play Ghostbusters (ZX Spectrum, 1984)

Everything known about playing the game, in one place. The port plays the same way;
where it differs, it says so.
Where a fact comes from reading the code rather than from playing, it says so, with the
address of the original's code.

## The aim
Make more money than the bank gave you, catching ghosts around the city, before the
Keymaster and the Gatekeeper reach Zuul. Then get two of your men past the Marshmallow Man
into Zuul to close the portal. If you made a profit you get a new account number, which
starts the next game with more money.

## Keys
| Key | What it does |
|---|---|
| Q / A / O / P | up / down / left / right (or a Sinclair, Kempston or cursor joystick, picked on the controller menu; the port reads the keys, the arrow keys and a joystick or gamepad whatever you pick) |
| Z | fire: drive to a building, fire the beams, drop the trap, work the ghost vacuum on the drive |
| B | drop ghost bait on the city map |
| SPACE | the status line (on the city map, the drive and at a building): backpack power, empty traps, men left |
| 1-3, E | in the equipment shop: more pages, and E to finish (once you have a trap) |
| H | pause (not listed in the game, found in the code; not in the port) |
| ENTER + SYMBOL SHIFT | back to the menu (not listed; in the port ENTER + Ctrl, after the ending only) |
| ENTER + CAPS SHIFT | back to the car shop, with the money you started with and no equipment (not listed; not in the port) |
| Esc | quits the port |

## Starting out
1. Type your name, then say whether you have an account. A new franchise gets $10000.
2. Buy a car. The shop reads a typed line, so press the keys one after another, not together,
   and finish with ENTER: SPACE, 4, ENTER shows car 4's picture, cargo, speed and price; 3,
   ENTER buys car 3. You can view another car straight from a car's page (checked in the
   simulator).
3. Buy equipment: Q/A move the forklift between the rows (only while it carries nothing), Z
   picks an item up, P carries it to the car and Z there buys it (the car has only so many
   cargo spaces). O takes it back to its row, and Z in a row puts it down. 1-3 change page.
   E leaves once you have at least one trap; without the money for a trap you can never
   leave. Bait comes as 5 baits.
4. A slip in the car shop: with exactly $9900-$9999 you can buy the $15000 car, and are left
   with $0.
5. The song's words light up a word at a time; ENTER stops the song. Rubbing out while typing
   a line lifts the 20-character limit (a bug), but only the first 20 are kept (and see the
   car shop trick under Cheats).

## The cars
| Car | Price | Cargo | Top speed | Drive speed (code) |
|---|---|---|---|---|
| 1. Compact | $2000 | 5 | 75 mph | $75 (the slowest) |
| 2. 1963 Hearse | $4800 | 9 | 90 mph | $90 |
| 3. Station Wagon | $6000 | 11 | 110 mph | $B0 |
| 4. High-Performance | $15000 | 7 | 160 mph | $FF (more than twice the Compact) |

The speed only matters on the drive to a building (below): a faster car gets there sooner,
so the city wastes less time while you drive.

## The equipment
Prices from the shop's table (`$9A09`), what each does from the code (`$99F4` lists the items
and their bits in `$D966`). Every item takes one of the car's cargo spaces; when they are all
used: "YOUR CAR IS LOADED TO CAPACITY". You can't leave the shop (E) without at least one trap.

| Item | Price | What it does |
|---|---|---|
| PK energy detector | $400 | On the map, stirring buildings next to the logo turn magenta, so you can see which are about to be haunted and get there first. |
| Image intensifier | $800 | At the building, the ghost is always shown. Without it the ghost is often not drawn (it flickers), which makes herding it over the trap much harder. |
| Marshmallow sensor | $800 | During a Marshmallow warning, the building next to the logo turns white. (The code doesn't check which building he will pick.) |
| Ghost bait | $400 | 5 lots of bait; buying it again sets it back to 5. B drops one on the map during an alert: the Marshmallow Man forms at the bait instead, and the mayor pays you $2000 (seen). |
| Trap | $600 | One ghost each. You can buy several (each takes a cargo space); they sit stacked on the car's roof. A full trap is emptied at GHQ. |
| Ghost vacuum | $500 | On the drive, holding Z sucks in a roaming ghost you touched on the map when it is just right of the car. A caught one goes back to its starting place after the building, far from Zuul, so it takes longer to reach Zuul and add its 100 PK. One that floats past stays where it was on the map, still roaming. It pays nothing. |
| Portable laser confinement system | $8000 | Caught ghosts go into it instead of using up a trap: room for 16 at the start of the city, and 10 again after each GHQ visit. You still need one empty trap to drive to a building. So with it you can catch many ghosts without going back to GHQ. |

## The city map
- The logo is your car. It moves along the roads, 2 pixels at a time.
- Buildings go quiet → stirring → haunted (flashing red). "Stirring" is a made-up name for the
  middle state: it looks just like a quiet building (only the PK energy detector shows it,
  magenta), and driving to one makes it haunted 1 time in 4. The game starts with building 15
  stirring and building 7 haunted. A haunted building that isn't dealt
  with in time goes quiet again, and city PK goes up by 300 (the ghost got away).
- Four roaming ghosts drift towards Zuul. Each one that gets there adds 100 to PK and starts
  again. Run the logo into one to stop it: you will meet it again on the drive.
- Z beside a building (the one above you; hold A for the one below) drives there. It says why
  not if you have too few men, no backpack power or no empty traps. Zuul only lets you in once
  the Keymaster and the Gatekeeper have both arrived, and then nowhere else does.
- Which building Z picks: you must be on a horizontal road, between two crossroads (on a
  vertical road nothing is beside you). Z alone picks the building above the road; hold A (down)
  with Z for the one below. Up does nothing extra, since above is already the default.
- GHQ (building 17) is where you go to empty traps and recharge. It is on the bottom row,
  below the bottom road, second block from the left: stop on the bottom road between the
  second and third vertical roads, hold A and press Z.

## City PK energy
PK goes up by 1 on every tick. The ticks start about 0.8 s apart and get faster as PK rises
(about 0.1 s apart near 9000, and every pass during a Marshmallow alert). On top of that, it
goes up 100 for every roaming ghost that reaches Zuul and 300 for every haunting that runs out.
PK stops at 9999. As it rises:
- new hauntings come more often;
- from about 4700 the Marshmallow warnings and alerts start (below);
- from 5000 the Keymaster and the Gatekeeper can go into Zuul when they pass it;
- from 9500 they head straight for Zuul.

## The Marshmallow Man
- When PK's hundreds are 7, 8 or 9 (4700-4999, 5700-5999 and so on) a warning starts. At the
  next 000 (5000, 6000...) it becomes "--MARSHMALLOW ALERT--": a building is picked and the
  roaming ghosts head there to form him.
- **Tip: drop bait (B) during the alert.** The pieces walk to the bait, and the mayor pays
  you $2000. (Seen in play and in the simulator.)
- With no bait, when all four ghosts arrive he stomps for about 5 seconds, does $4000 of
  damage (taken off your money, down to $0), and that building stays stomped for the rest of
  the game.
- The alert can come round again at the next thousand.

## The drive to a building
- How long it lasts depends on how far the logo moved on the map since your last drive
  (each logo step counts 2, up to 255; read from the code), and on your car. Roughly, each
  second of moving on the map is about 5½ seconds of driving in the Compact, 4½ in the Hearse,
  3½ in the Station Wagon and 2½ in the High-Performance; the longest drive is about 31
  seconds in the Compact and 14 in the High-Performance. A short pull at the end takes about
  2 more seconds. So pressing Z close to where you last were is quick.
- O and P steer left and right.
- The roaming ghosts you ran into on the map appear on the road at the same distance from the
  building as where you touched them, and float down past the car.
- **Ghost vacuum**: hold Z with a ghost just to the right of the car (up to 32 pixels) and it
  is pulled in. Read from the code: a caught ghost gives no money or PK, but goes back to its
  starting place after the building; one you miss carries on roaming.
- PK still goes up while you drive.

## Catching a ghost at the building
(Read from the code and tried in the simulator.)
1. The first man walks in carrying the trap. **Walk him up the pavement first** (Q), then
   press Z to put the trap down in front of him. If he drops it while at the very bottom of the
   pavement, the men can't reach it afterwards and the scene never ends.
2. Press Z again and the second man walks in from the right; move him with the keys.
3. Press Z and let go: the beams start. They go up and out the way each man faces; O or P
   steps a man the way he faces. The beams push the ghost sideways, so herd it over the trap.
   Don't let the ends of the beams meet ("YOU CROSSED THE STREAMERS!!!": the backpacks short
   out, go back to GHQ). The beams use up backpack power.
4. Press Z to open the trap when the ghost is low and over it: the stream rises and catches it
   if it gets close. "Ghostbusters!", the men pick up the trap and walk off.
5. Pay: the building's haunted timer × 16 dollars, about $990 for a fresh haunting and less the
   longer it has been haunted. The timer only counts down on the city map (about 17 seconds
   from haunted to escaped, roughly $90 a second); the drive and the catch don't count, so
   what matters is pressing Z at a haunted building soon after it starts flashing.
   While you drive and catch, the map is frozen: only PK keeps rising. If a new haunting
   lands on a building that is already haunted, its timer starts again from $99. A catch uses a trap, or the laser
   confinement system if you have it (room for 16 at first, 10 after each GHQ visit).
6. Miss, and the ghost slimes one of the men ("He slimed me!"): one man fewer, and the
   ghost gets away. (If it was high up, it flies off the top and comes back up from the bottom
   of the screen to reach him: a quirk in the code.)
- Without the image intensifier the ghost flickers and is hard to see; with it, it is always
  shown.
- At a building that isn't haunted, Z just walks the man back to the car.
- **GHQ**: the three men walk out, and you get back 3 men, all traps empty, full backpack power
  and room for 10 in the laser confinement system. Go there when traps, men or power run low.

## Zuul and the ending
- When the Keymaster and the Gatekeeper have both arrived: if you have less money than you
  started with, the bank forecloses and the game is over. Otherwise go to Zuul.
- At Zuul you always get 3 men, however many you had left. Each walks in from the right by
  himself, then you walk him (Q/A/O/P) up into the doorway.
- Step into the doorway just as the Marshmallow Man reaches the top of his bob (found in play).
  He bobs once about every 1.8 seconds and is high enough for only about 0.17 seconds of it
  (read from the code); at any other moment the man is squashed. Two men must get in. It is
  easiest to stand just below the doorway and step up as he reaches the top.
- Two in: the portal closes and the city pays $5000. Fewer: "Good try...", Zuul takes over the
  city. Either way you get a raised credit limit and a new account number.
- The account number (8 digits) holds your money, rounded down to $100, and a check worked out
  from your name. Type the same name and the number at the start of the next game to begin
  with that money. With a different name it is an "INVALID ACCOUNT NUMBER".
- After the ending, ENTER + SYMBOL SHIFT starts a new game (seen in the simulator; ENTER + Ctrl
  in the port). The song plays again, without its words.
- In the port, `--city` skips the start, so there is no name to type: `--name` gives the name
  the account number is made for (GHOSTBUSTERS if you leave it out).

## The port's trainer
The port starts with a setup screen the original doesn't have. Pick a line with up/down (Q/A
or the arrow keys) and turn it on or off with SPACE or Z (or press its number), then press ENTER
to play. A joystick works too. The choice is kept for next time. With every cheat off, it is
the original game.

| Key | Cheat | What it does |
|---|---|---|
| 1 | Infinite money | money never goes down: cars, equipment and the Marshmallow Man's damage cost nothing (you still need the money to buy) |
| 2 | Infinite men | a man slimed at a building, or squashed at Zuul, is not lost |
| 3 | Infinite power | the backpacks never run down, and crossing the streams doesn't empty them |
| 4 | Infinite traps | a caught ghost doesn't fill a trap (or the laser confinement system) |

`--no-setup` skips the screen (with the cheats from last time), and `--trainer NAME` turns one
on (`infinite_money`, `infinite_men`, `infinite_power`, `infinite_traps`).

## Cheats
- `python tools/account_number.py NAME MONEY` makes an account number for any name and money
  (up to $999900). At the start, type that name, Y to "DO YOU HAVE AN ACCOUNT?", then the
  number. Tried: VENKMAN and 46325231 start with $999900.
- In the original only (the port has no ENTER + CAPS SHIFT), a bug lets the car shop's line set
  the money you started with. In the car shop type `1`, SHIFT (rub it out), `1`, 28 letters,
  `YY`, ENTER. Play on to the city map and press ENTER + CAPS SHIFT: back in the car shop you
  have $595900. But at Zuul the bank then wants at least $595900. (Seen in the simulator.)
