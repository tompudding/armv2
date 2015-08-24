Synapse
-------

This is my entry for Ludum Dare 33. It is a hacking simulator (You are the monster(!), because hackers are monsters right?) where
you have an imaginary old machine based on an ARMv2 CPU and made up hardware. You have some tapes, and on each tape there is a
secret password, can you find all three?

I had originally intended to implement a BBS style system and have you hack a real server and possibly other people, but that was
way too ambitious for the 48 hours. It's probably extremely hard.

Installation
------------

Right now you need python, pygame, pyelftools, cython an arm toolchain (arm-none-eabi-) installed into your path to build it.
I'm going to work on packaging it up for various platforms tomorrow so it's probably easist if you don't play this yet until
it's packaged up for the system of your choice

Help
----
You can add other tapes by dropping files into the tapes directory. These can then either be loaded and run as any other tape,
or played as keyboard input by pressing p

Bugs
----
Sometimes there's a deadlock and it hangs. Not sure why :(
