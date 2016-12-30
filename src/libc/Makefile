ARMCFLAGS  =-std=gnu99 -nostdlib -march=armv2a -static -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -Isrc

build/libc.a: build/%.o | build
	ar rcs $@ $^

build/%.o: %.c | build
	arm-none-eabi-gcc ${ARMCFLAGS} -c -o $@ $<

build:
	mkdir -p $@

clean:
	rm -rf build
