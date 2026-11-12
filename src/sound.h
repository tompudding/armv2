#ifndef __SOUND_H__
#define __SOUND_H__

#include <stdint.h>

/* The sound chip is three voices and a filter, laid out like the Commodore 64's SID. To play a note, set a
   voice's frequency, envelope and the master volume, then write a waveform with SOUND_GATE to its control
   register. Writing the waveform without SOUND_GATE releases the note. */

struct sound_voice {
    volatile uint8_t freq_lo;
    volatile uint8_t freq_hi;
    volatile uint8_t pulse_lo;        /* The pulse width is 12 bits, and 0x800 is a square wave */
    volatile uint8_t pulse_hi;
    volatile uint8_t control;         /* enum sound_control */
    volatile uint8_t attack_decay;    /* SOUND_ENVELOPE(attack, decay) */
    volatile uint8_t sustain_release; /* SOUND_ENVELOPE(sustain, release) */
};

struct sound_chip {
    struct sound_voice voice[3];
    volatile uint8_t   cutoff_lo;     /* The filter cutoff is 11 bits, with the low 3 here */
    volatile uint8_t   cutoff_hi;
    volatile uint8_t   resonance;     /* SOUND_RESONANCE(resonance, voices to filter) */
    volatile uint8_t   mode_volume;   /* enum sound_mode, with the volume in the low nibble */
    volatile uint8_t   unused[2];
    volatile uint8_t   osc3;          /* Read only: the top 8 bits of voice 3's waveform */
    volatile uint8_t   env3;          /* Read only: voice 3's envelope */
};

enum sound_control {
    SOUND_GATE     = 0x01,
    SOUND_SYNC     = 0x02, /* Restart this voice's waveform whenever the previous voice's does */
    SOUND_RING     = 0x04, /* Ring modulate the triangle with the previous voice */
    SOUND_TEST     = 0x08, /* Hold the waveform at its start */
    SOUND_TRIANGLE = 0x10,
    SOUND_SAWTOOTH = 0x20,
    SOUND_PULSE    = 0x40,
    SOUND_NOISE    = 0x80,
};

enum sound_mode {
    SOUND_LOW_PASS   = 0x10,
    SOUND_BAND_PASS  = 0x20,
    SOUND_HIGH_PASS  = 0x40,
    SOUND_VOICE3_OFF = 0x80,
    SOUND_MAX_VOLUME = 0x0f,
};

#define SOUND                            ((struct sound_chip *)0x01006000)
#define SOUND_NUM_VOICES                 3
#define SOUND_ENVELOPE(high, low)        ((((high) & 0xf) << 4) | ((low) & 0xf))
#define SOUND_RESONANCE(amount, voices)  SOUND_ENVELOPE(amount, voices)
/* The frequency register value for a pitch in Hz, which is the pitch * 2^24 / 985248 */
#define SOUND_HZ(hz)                     ((uint16_t)(((uint32_t)(hz) * 17028) / 1000))
/* Notes count semitones up from C0, so middle C is SOUND_NOTE(4, 0) and concert A is SOUND_NOTE(4, 9) */
#define SOUND_NOTE(octave, semitone)     ((octave) * 12 + (semitone))

/* The register values for the 12 notes of octave 7, which halve for each octave below that. The last one is
   too high for the register, so the highest note is A#7 */
static const uint32_t sound_top_octave[12] = {
    35641, 37760, 40005, 42384, 44904, 47574, 50403, 53401, 56576, 59940, 63504, 67280
};

static inline void sound_set_frequency(int voice, uint16_t value) {
    SOUND->voice[voice].freq_lo = value & 0xff;
    SOUND->voice[voice].freq_hi = value >> 8;
}

static inline void sound_set_note(int voice, int note) {
    int octave = note / 12;
    if(octave > 7) {
        octave = 7;
    }
    uint32_t value = sound_top_octave[note % 12] >> (7 - octave);
    sound_set_frequency(voice, value > 0xffff ? 0xffff : value);
}

static inline void sound_set_pulse_width(int voice, uint16_t value) {
    SOUND->voice[voice].pulse_lo = value & 0xff;
    SOUND->voice[voice].pulse_hi = (value >> 8) & 0xf;
}

static inline void sound_set_cutoff(uint16_t value) {
    SOUND->cutoff_lo = value & 7;
    SOUND->cutoff_hi = (value >> 3) & 0xff;
}

#endif
