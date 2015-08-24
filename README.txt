Synapse
-------

This is my entry for Ludum Dare 33. It is a hacking simulator (You are the monster(!), because hackers are monsters right?) where
you have an imaginary old machine based on an ARMv2 CPU and made up hardware. You have some tapes, and on each tape there is a
secret password, can you find all three?

I had originally intended to implement a BBS style system and have you hack a real server and possibly other people, but that was
way too ambitious for the 48 hours. It's probably extremely hard, with a high barrier to entry, but if you like low level stuff,
old computers and ARM, then it might just be for you :)

Installation
------------

Right now you need python, pygame, pyelftools, cython and an arm toolchain (arm-none-eabi-) installed into your path to build it.
I'm going to work on packaging it up for various platforms tomorrow so it's probably easist if you don't play this yet until
it's packaged up for the system of your choice

Help
----
To get started you'll want to load a tape. You can type load and enter and it will try to load a tape, but at bootup there is
no tape in the drive.

  * Press escape to halt execution and switch controll to the debugger. You'll see the bottom right text switch from "RUNNING"
    to stopped
  * Press tab until the tape selector is highlighted
  * Use the arrow keys to choose the tape you want
  * Press enter or space to load it
  * Resume execution either by pressing c or escape again. R will reset the machine and Q exit completely at this point so
    be careful!
  * type load and enter to load the tape
  * Enjoy the delights of the Tetralimbic Systems Synapse!


You can add other tapes by dropping files into the tapes directory. These can then either be loaded and run as any other tape,
or played as keyboard input by pressing p

Bugs
----
Sometimes there's a deadlock and it hangs. Not sure why :(
