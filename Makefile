CC=gcc
AR=ar
CFLAGS=-std=gnu99 -Wall -Wshadow -Wpointer-arith -Wcast-qual -Wstrict-prototypes -Wmissing-prototypes -O3 -fPIC
AS=arm-none-eabi-as
COPY=arm-none-eabi-objcopy
TAPES_DIR  = tapes
BUILD_DIR  = build
TAPE_NAMES = guessing adventure trivia one_letter_werewolf
TAPES_BIN  = $(patsubst %, ${TAPES_DIR}/%.tape, ${TAPE_NAMES})
ARMCFLAGS  =-std=gnu99 -nostdlib -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -Isrc -Isrc/libc
.PRECIOUS: build/% #Don't delete our intermediate object files, they're useful for debugging

all: armv2.so build/boot.rom ${TAPES_BIN}

armv2.so: libarmv2.a armv2.pyx carmv2.pxd
	python setup.py build_ext --inplace

libarmv2.a: step.o instructions.o init.o armv2.h mmu.o hw_manager.o
	${AR} rcs $@ step.o instructions.o init.o mmu.o hw_manager.o

build/boot.rom: build/boot.bin build/os | build
	python create.py --boot $^ -o $@

build/boot.bin: build/boot.o | build
	${COPY} -O binary $< $@

build/boot.symbols: build/boot.o | build
	python create_symbols $< $@

build/boot.o: src/boot.S | build
	${AS} -march=armv2a -mapcs-26 -o $@ $<

build/tape_loader.bin: src/tape_loader.S | build
	${AS} -march=armv2a -mapcs-26 -o tape_loader.o $<
	${COPY} -O binary tape_loader.o $@

build/os: src/os.c build/synapse.o build/libc.a src/synapse.h | build
	arm-none-eabi-gcc ${ARMCFLAGS} -Wl,-Ttext=0x1000 -nostartfiles -o $@ src/os.c build/synapse.o build/libc.a

build/synapse.o: src/synapse.c src/synapse.h
	arm-none-eabi-gcc ${ARMCFLAGS} -c -o $@ $<

build/libc.a: src/libc/*.c src/libc/*.S
	make -C src/libc
	cp src/libc/build/libc.a build/libc.a

${TAPES_DIR}/%.tape: build/tape_loader.bin build/% | build ${TAPES_DIR}
	python create.py -o $@ $^

build/%: src/tapes/%.c | build
	arm-none-eabi-gcc ${ARMCFLAGS} -I.. -o $@ $< build/synapse.o

build:
	mkdir -p $@

${TAPES_DIR}:
	mkdir -p ${TAPES_DIR}

clean:
	rm -f armv2 ${TAPES_DIR}/*.tape boot.rom armtest step.o instructions.o init.o armv2.c armv2.so *~ libarmv2.a boot.bin boot.o mmu.o hw_manager.o *.pyc
	make -C src/libc clean
	rm -rf build/temp*
	rm -f build/*
	rm -df build
	python setup.py clean
