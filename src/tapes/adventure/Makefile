#	$NetBSD: Makefile,v 1.3 1995/03/21 12:04:53 cgd Exp $
#	@(#)Makefile	8.1 (Berkeley) 6/12/93

PROG=	adventure
SRCS=	main.c init.c done.c subr.c vocab.c wizard.c io.c data.c crc.c #save.c
MAN=	adventure.6
ARMCC=arm-none-eabi-gcc
ARMCFLAGS  =-std=gnu99 -nostdlib -march=armv2a -Wa,-mapcs-26 -mno-thumb-interwork -marm -Wl,--omagic -I../.. -I../../libc

HIDEGAME=hidegame
CLEANFILES+=setup data.c adventure data.pre

all: adventure.so adventure

adventure.so: ${SRCS}
	${ARMCC} -o $@ -fno-stack-protector -shared ${ARMCFLAGS} -T ../linking.txt $^

adventure: ${SRCS}
	${ARMCC} -o $@ -fno-stack-protector -static ${ARMCFLAGS} $^ ../../../build/synapse.o ../../../build/libc.a

data.c: data.pre
	python create_data.py $@ $<

data.pre: glorkz setup
	./setup glorkz > data.pre

setup: setup.c hdr.h
	${CC} -o setup setup.c



clean:
	rm -f ${CLEANFILES} adventure.so
