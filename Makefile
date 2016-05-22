CC=gcc
AR=ar
CFLAGS=-std=gnu99 -Wall -Wshadow -Wpointer-arith -Wcast-qual -Wstrict-prototypes -Wmissing-prototypes -O3 -fPIC
AS=arm-none-eabi-as
COPY=arm-none-eabi-objcopy
TAPES= guessing adventure trivia one_letter_werewolf
ARMCFLAGS=-std=gnu99 -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic

all: armtest armv2.so boot.rom tapes/1_guessing.bin tapes/2_trivia.bin tapes/3_adventure.bin tapes/1lw.bin

run: armv2.so boot.rom emulate.py debugger.py
	python emulate.py

armv2.so: libarmv2.a armv2.pyx carmv2.pxd
	python setup.py build_ext --inplace

armtest: armtest.c libarmv2.a
	${CC} ${CFLAGS} -o $@ $^

libarmv2.a: step.o instructions.o init.o armv2.h mmu.o hw_manager.o
	${AR} rcs $@ step.o instructions.o init.o mmu.o hw_manager.o

boot.rom: boot.bin os
	python create.py --boot $^ -o $@

boot.bin: boot.o
	${COPY} -O binary $< $@

boot.symbols: boot.o
	python create_symbols $< $@

boot.o: boot.S
	${AS} -march=armv2a -mapcs-26 -o $@ $<

tape_loader.bin: tape_loader.S
	${AS} -march=armv2a -mapcs-26 -o tape_loader.o $<
	${COPY} -O binary tape_loader.o $@

os: os.c common.c synapse.h
	arm-none-eabi-gcc ${ARMCFLAGS} -Wl,-Ttext=0x1000 -nostartfiles -o $@ os.c common.c

tapes/1_guessing.bin: tape_loader.bin guessing 
	python create.py -o $@ $^

guessing: guessing.c common.c synapse.h
	arm-none-eabi-gcc ${ARMCFLAGS} -o $@ guessing.c common.c

tapes/2_trivia.bin: tape_loader.bin trivia 
	python create.py -o $@ $^

trivia: trivia.c common.c synapse.h
	arm-none-eabi-gcc ${ARMCFLAGS} -o $@ trivia.c common.c

tapes/3_adventure.bin: tape_loader.bin adventure 
	python create.py -o $@ $^

adventure: adventure.c common.c synapse.h
	arm-none-eabi-gcc ${ARMCFLAGS} -o $@ adventure.c common.c

tapes/1lw.bin: tape_loader.bin one_letter_werewolf 
	#arm-none-eabi-gcc ${ARMCFLAGS} -o $@ $< common.c
	python create.py -o $@ $^

one_letter_werewolf: one_letter_werewolf.c common.c synapse.h
	arm-none-eabi-gcc ${ARMCFLAGS} -o $@ one_letter_werewolf.c common.c

clean:
	rm -f armv2 os tapes/3_adventure.bin adventure tapes/2_trivia.bin trivia tapes/1_guessing.bin guessing boot.rom armtest step.o instructions.o init.o armv2.c armv2.so *~ libarmv2.a boot.bin boot.o mmu.o hw_manager.o *.pyc
	python setup.py clean
