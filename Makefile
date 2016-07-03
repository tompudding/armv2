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

all: armtest armv2.so boot.rom ${TAPES_BIN}

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

os: src/os.c src/common.c src/synapse.h
	arm-none-eabi-gcc ${ARMCFLAGS} -Wl,-Ttext=0x1000 -nostartfiles -o $@ src/os.c src/common.c

${TAPES_DIR}/%.tape: tape_loader.bin ${BUILD_DIR}/% | ${BUILD_DIR} ${TAPES_DIR}
	python create.py -o $@ $^

${BUILD_DIR}/%: src/tapes/%.c | ${BUILD_DIR}
	arm-none-eabi-gcc ${ARMCFLAGS} -I.. -o $@ $< src/common.c

${BUILD_DIR}: 
	mkdir -p $@

${TAPES_DIR}:
	mkdir -p ${TAPES_DIR}

clean:
	rm -f armv2 os tapes/*.tape boot.rom armtest step.o instructions.o init.o armv2.c armv2.so *~ libarmv2.a boot.bin boot.o mmu.o hw_manager.o *.pyc
	rm -f ${TAPES_DIR}/*
	rm -df ${TAPES_DIR}
	rm -rf ${BUILD_DIR}/temp*
	rm -f ${BUILD_DIR}/*
	rm -df ${BUILD_DIR}
	python setup.py clean
