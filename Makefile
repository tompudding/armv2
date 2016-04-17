CC=gcc
AR=ar
CFLAGS=-std=c99 -pedantic -Wall -Wshadow -Wpointer-arith -Wcast-qual -Wstrict-prototypes -Wmissing-prototypes -O3 -fPIC
AS=arm-none-eabi-as
COPY=arm-none-eabi-objcopy

all: armtest armv2.so boot.rom rijndael tapes/1_guessing.bin tapes/2_trivia.bin tapes/3_adventure.bin

run: armv2.so boot.rom emulate.py debugger.py
	python emulate.py

armv2.so: libarmv2.a armv2.pyx carmv2.pxd
	python setup.py build_ext --inplace

armtest: armtest.c libarmv2.a
	${CC} ${CFLAGS} -o $@ $^

libarmv2.a: step.o instructions.o init.o armv2.h mmu.o hw_manager.o
	${AR} rcs $@ step.o instructions.o init.o mmu.o hw_manager.o

boot.rom: boot.S os
	${AS} -march=armv2a -mapcs-26 -o boot.o $<
	${COPY} -O binary boot.o boot.bin
	python create.py boot.bin os $@

tape_loader.bin: tape_loader.S
	${AS} -march=armv2a -mapcs-26 -o tape_loader.o $<
	${COPY} -O binary tape_loader.o $@

os: os.c common.c synapse.h
	arm-none-eabi-gcc -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -o $@ os.c common.c

tapes/1lw.bin: one_letter_werewolf tape_loader.bin
	#arm-none-eabi-gcc -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -o $@ $< common.c
	python create_tape.py $@ $^

one_letter_werewolf: one_letter_werewolf.c common.c synapse.h
	arm-none-eabi-gcc -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -o $@ one_letter_werewolf.c common.c

tapes/1_guessing.bin: guessing tape_loader.bin
	python create_tape.py $@ $^

guessing: guessing.c common.c synapse.h
	arm-none-eabi-gcc -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -o $@ guessing.c common.c

tapes/2_trivia.bin: trivia tape_loader.bin
	python create_tape.py $@ $^

trivia: trivia.c common.c synapse.h
	arm-none-eabi-gcc -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -o $@ trivia.c common.c

tapes/3_adventure.bin: adventure tape_loader.bin
	python create_tape.py $@ $^

adventure: adventure.c common.c synapse.h
	arm-none-eabi-gcc -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -o $@ adventure.c common.c

clean:
	rm -f armv2 os tapes/3_adventure.bin adventure tapes/2_trivia.bin trivia tapes/1_guessing.bin guessing boot.rom armtest step.o instructions.o init.o armv2.c armv2.so *~ libarmv2.a boot.bin boot.o mmu.o hw_manager.o *.pyc
	python setup.py clean
