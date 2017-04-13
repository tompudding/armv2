ARMCC=arm-none-eabi-gcc
ARMCFLAGS  =-std=gnu99 -nostdlib -march=armv2a -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -I.. -I../libc
TAPE_NAMES = guessing trivia one_letter_werewolf
STATIC_TARGETS = $(addprefix build/, ${TAPE_NAMES}) build/adventure
SHARED_TARGETS = $(addsuffix .so, ${STATIC_TARGETS})
LIBDIR := ../../build

all: ${SHARED_TARGETS}

build/%.so: %.c | build
	${ARMCC} -shared ${ARMCFLAGS} -T linking.txt -o $@ $< 

# build/%: %.c | build
# 	${ARMCC} -static -Wl,--omagic ${ARMCFLAGS} -o $@ $< ${LIBDIR}/synapse.o ${LIBDIR}/libc.a

build/adventure.so: build/adventure
	cp adventure/adventure.so $@

build/adventure: | build
	make -C adventure
	cp adventure/adventure $@

tapes/%: build/%
	python ../../create.py -o $@ $^

tapes:
	mkdir -p $@

build:
	mkdir -p $@

clean:
	make -C adventure clean
	rm -f build/*
	rm -df build
