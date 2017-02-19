ARMCC=arm-none-eabi-gcc
ARMCFLAGS  =-std=gnu99 -nostdlib -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -I.. -I../libc
TAPE_NAMES = guessing trivia one_letter_werewolf
LIBDIR := ../../build

all: $(addprefix build/, ${TAPE_NAMES}) build/adventure

build/%: %.c | build
	${ARMCC} ${ARMCFLAGS} -o $@ $< ${LIBDIR}/synapse.o ${LIBDIR}/libc.a

build/adventure: | build
	make -C adventure
	cp adventure/adventure $@

build:
	mkdir -p $@

clean:
	make -C adventure clean
	rm -f build/*
	rm -df build
