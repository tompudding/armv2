ARMCFLAGS  =-std=gnu99 -nostdlib -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -I.. -I. -Os
.PRECIOUS: build/%.o #Don't delete our intermediate object files, they're useful for debugging

C_SOURCE  = $(wildcard *.c)
C_TARGETS = $(patsubst %.c,build/%.o,${C_SOURCE})

S_SOURCE  = $(wildcard *.S)
S_TARGETS = $(patsubst %.S,build/%.o,${S_SOURCE})

build/libc.a: ${C_TARGETS} ${S_TARGETS} | build
	arm-none-eabi-ar ar rcs $@ $^
	arm-none-eabi-ranlib $@

${C_TARGETS}: ${C_SOURCE} | build
	arm-none-eabi-gcc ${ARMCFLAGS} -c -o $@ $(patsubst build/%.o, %.c, $@)

${S_TARGETS}: ${S_SOURCE} | build
	arm-none-eabi-gcc ${ARMCFLAGS} -c -o $@ $(patsubst build/%.o, %.S, $@)

build:
	mkdir -p $@

clean:
	rm -rf build
