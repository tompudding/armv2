CC=gcc
AR=ar
CFLAGS=-std=gnu99 -Wall -Wshadow -Wpointer-arith -Wcast-qual -Wstrict-prototypes -Wmissing-prototypes -O3 -fPIC
AS=arm-none-eabi-as
COPY=arm-none-eabi-objcopy
TAPES_DIR  = tapes
BUILD_DIR  = build
TAPE_NAMES = guessing adventure trivia one_letter_werewolf
TAPES_BIN  = $(patsubst %, ${TAPES_DIR}/%.tape, ${TAPE_NAMES})
ARMCFLAGS  =-std=gnu99 -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -Isrc

$(warning ${TAPES_BIN})

all: armtest armv2.so build/boot.rom ${TAPES_BIN}

run: armv2.so boot.rom emulate.py debugger.py
	python emulate.py

armv2.so: libarmv2.a armv2.pyx carmv2.pxd
	python setup.py build_ext --inplace

armtest: armtest.c libarmv2.a
	${CC} ${CFLAGS} -o $@ $^

libarmv2.a: step.o instructions.o init.o armv2.h mmu.o hw_manager.o
	${AR} rcs $@ step.o instructions.o init.o mmu.o hw_manager.o

build/boot.rom: build/boot.bin build/os
	python create.py --boot $^ -o $@

build/boot.bin: build/boot.o
	${COPY} -O binary $< $@

build/boot.symbols: build/boot.o
	python create_symbols $< $@

build/boot.o: src/boot.S
	${AS} -march=armv2a -mapcs-26 -o $@ $<

build/tape_loader.bin: src/tape_loader.S
	${AS} -march=armv2a -mapcs-26 -o tape_loader.o $<
	${COPY} -O binary tape_loader.o $@

build/os: src/os.c src/common.c src/synapse.h
	arm-none-eabi-gcc ${ARMCFLAGS} -Wl,-Ttext=0x1000 -nostartfiles -o $@ src/os.c src/common.c

${TAPES_DIR}/%.tape: tape_loader.bin build/% | build ${TAPES_DIR}
	python create.py -o $@ $^

build/%: src/tapes/%.c | build
	arm-none-eabi-gcc ${ARMCFLAGS} -I.. -o $@ $< src/common.c

build: 
	mkdir -p $@

${TAPES_DIR}:
	mkdir -p ${TAPES_DIR}

clean:
	rm -f armv2 ${TAPES_DIR}/*.tape boot.rom armtest step.o instructions.o init.o armv2.c armv2.so *~ libarmv2.a boot.bin boot.o mmu.o hw_manager.o *.pyc
	rm -rf build/temp*
	rm -f build/*
	rm -df build
	python setup.py clean
