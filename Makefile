CC=gcc
AR=ar
CFLAGS=-std=gnu99 -Wall -Wshadow -Wpointer-arith -Wcast-qual -Wstrict-prototypes -Wmissing-prototypes -O3 -fPIC
AS=arm-none-eabi-as
COPY=arm-none-eabi-objcopy
BUILD_DIR  = build
TAPE_SRC := $(wildcard src/*.cpp)
OBJ_FILES := $(addprefix obj/,$(notdir $(CPP_FILES:.cpp=.o)))
ARMCFLAGS  =-std=gnu99 -nostdlib -march=armv2a -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -Isrc -Isrc/libc -Os
.PRECIOUS: build/% #Don't delete our intermediate object files, they're useful for debugging

all: armv2.so build/boot.rom

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

build/os: src/os.c build/synapse.o build/libc.a src/synapse.h | build
	arm-none-eabi-gcc -static ${ARMCFLAGS} -Wl,-Ttext=0x1000 -nostartfiles -o $@ src/os.c build/synapse.o -Wl,--whole-archive build/libc.a

build/synapse.o: src/synapse.c src/synapse.h | build
	arm-none-eabi-gcc -static ${ARMCFLAGS} -c -o $@ $<

build/libc.a: src/libc/*.c src/libc/*.S | build
	make -C src/libc
	cp src/libc/build/libc.a build/libc.a

build:
	mkdir -p $@

clean:
	rm -f armv2  boot.rom armtest step.o instructions.o init.o armv2.c popcnt.c armv2*.so popcnt*.so *~ libarmv2.a boot.bin boot.o mmu.o hw_manager.o *.pyc
	make -C src/libc clean
	rm -rf build/temp*
	rm -f build/*
	rm -df build
	python setup.py clean
