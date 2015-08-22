CC=gcc
AR=ar
CFLAGS=-std=c99 -pedantic -Wall -Wshadow -Wpointer-arith -Wcast-qual -Wstrict-prototypes -Wmissing-prototypes -O3 -fPIC
AS=arm-none-eabi-as
COPY=arm-none-eabi-objcopy

all: armtest armv2.so boot.rom rijndael

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

os: os.c
	arm-none-eabi-gcc -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -o $@ $^

clean:
	rm -f armv2 os boot.rom armtest step.o instructions.o init.o armv2.c armv2.so *~ libarmv2.a boot.bin boot.o mmu.o hw_manager.o *.pyc
	python setup.py clean
