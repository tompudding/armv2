import sys
import pygame
import glob
import os

from pygame.locals import *
import pygame.mixer

pygame.mixer.init()


class Sounds:
    def __init__(self):
        self.talking = []
        self.player_damage = []
        self.wee_sounds = []

        for filename in glob.glob(os.path.join(os.path.dirname(__file__), "resource", "*.ogg")):
            sound = pygame.mixer.Sound(filename)
            sound.set_volume(0.6)
            name = os.path.basename(filename)
            name = os.path.splitext(name)[0]
            setattr(self, name, sound)
