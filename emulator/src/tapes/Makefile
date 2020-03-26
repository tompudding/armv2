ARMCC=arm-none-eabi-gcc
ARMCFLAGS  = -Os -std=gnu99 -nostdlib -march=armv2a -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -I.. -I../libc
TAPE_NAMES = guessing trivia werewolf adventure
LOADING_SCREENS = trivia werewolf adventure
STATIC_TARGETS = $(addprefix build/, ${TAPE_NAMES})
SHARED_TARGETS = $(addsuffix .so, ${STATIC_TARGETS})
_LOADING_TARGETS = ${addprefix build/, ${LOADING_SCREENS}}
LOADING_TARGETS = ${addsuffix _loading.so, ${_LOADING_TARGETS}}
LIBDIR := ../../build

all: ${SHARED_TARGETS} ${LOADING_TARGETS}

build/%_loading.so: %_loading.c loading_common.c | build
	${ARMCC} -shared ${ARMCFLAGS} -T linking_loading.txt -o $@ $^

build/%.so: %.c | build
	${ARMCC} -shared ${ARMCFLAGS} -T linking.txt -o $@ $<

#build/adventure.so: build/adventure
#	cp adventure/adventure.so $@

#build/adventure: | build
#	make -C adventure
#	cp adventure/adventure $@

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
