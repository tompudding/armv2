import sys, pygame, glob, os

from pygame.locals import *
import pygame.mixer

pygame.mixer.init()

class Sounds(object):
    def __init__(self):
        self.talking = []
        self.player_damage = []
        self.wee_sounds = []

        for filename in glob.glob(os.path.join('resource','*.bogg')):
            print('LOAD',filename)
            sound = pygame.mixer.Sound(filename)
            sound.set_volume(0.6)
            name = os.path.basename(filename)
            name = os.path.splitext(name)[0]
            setattr(self,name,sound)
