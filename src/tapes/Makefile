BUILD_DIR  = build
TAPE_NAMES = guessing adventure trivia one_letter_werewolf
.PRECIOUS: build/% #Don't delete our intermediate object files, they're useful for debugging

${TAPE_NAMES}:
	make -C $@

${TAPES_DIR}/%.tape: build/tape_loader.bin build/% | build ${TAPES_DIR}
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
