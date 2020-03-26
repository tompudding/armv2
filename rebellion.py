import emulator

if __name__ == '__main__':
    #from multiprocessing import Process
    #import peripherals,time

    #p = Process(target=peripherals.run) p.start() This is a module, but we also want to be able to call it
    #directly so it needs to be able to import itself
    def main():
        emulator.init(width=960, height=720)
        machine = emulator.Emulator(boot_rom='emulator/build/boot.rom')
        machine.run()

    import cProfile
    cProfile.run('main()','runstats')
    #pygame.display.quit()
    #p.join()
