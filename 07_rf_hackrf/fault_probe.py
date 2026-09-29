"""RP2040-Zero instruction fault probe with a USB serial command channel.

RUN checks eight identical ADDs; TRACE records weighted ADD results, inverses
and indexes; DENSE checks weighted ADDs in a tight native loop and retains the
first anomaly. Signatures are compatible with skips, not proof of their cause.
"""

import micropython
import sys
import time
import os
import machine
import json
import array
import binascii


@micropython.asm_thumb
def count_bad(r0):
    mov(r3, r0)
    mov(r2, 0)
    cmp(r3, 0)
    beq(done)
    label(loop)
    mov(r0, 0)
    mov(r1, 1)
    add(r0, r0, r1)
    add(r0, r0, r1)
    add(r0, r0, r1)
    add(r0, r0, r1)
    add(r0, r0, r1)
    add(r0, r0, r1)
    add(r0, r0, r1)
    add(r0, r0, r1)
    cmp(r0, 8)
    beq(correct)
    add(r2, 1)
    label(correct)
    sub(r3, 1)
    bne(loop)
    label(done)
    mov(r0, r2)


@micropython.asm_thumb
def capture(r0, r1):
    # r0 is count; r1 points to 3*count uint32 words.
    mov(r4, 0)
    cmp(r0, 0)
    beq(captured)
    label(sample)
    mov(r2, 0)
    add(r2, 1)
    add(r2, 2)
    add(r2, 4)
    add(r2, 8)
    add(r2, 16)
    add(r2, 32)
    add(r2, 64)
    add(r2, 128)
    str(r2, [r1, 0])
    mov(r3, r2)
    mvn(r3, r3)
    str(r3, [r1, 4])
    str(r4, [r1, 8])
    add(r1, 12)
    add(r4, 1)
    sub(r0, 1)
    bne(sample)
    label(captured)
    mov(r0, r4)


@micropython.asm_thumb
def dense(r0, r1):
    mov(r3, 0)
    mov(r4, 0)
    mov(r5, 0)
    mov(r6, 0)
    cmp(r0, 0)
    beq(finish)
    label(sample)
    mov(r2, 0)
    add(r2, 1)
    add(r2, 2)
    add(r2, 4)
    add(r2, 8)
    add(r2, 16)
    add(r2, 32)
    add(r2, 64)
    add(r2, 128)
    cmp(r2, 255)
    beq(ok)
    add(r3, 1)
    cmp(r3, 1)
    bne(ok)
    mov(r5, r2)
    mov(r6, r4)
    label(ok)
    add(r4, 1)
    sub(r0, 1)
    bne(sample)
    label(finish)
    str(r3, [r1, 0])
    str(r4, [r1, 4])
    str(r5, [r1, 8])
    str(r6, [r1, 12])
    mvn(r2, r5)
    str(r2, [r1, 16])
    mov(r0, r3)


SESSION = binascii.hexlify(os.urandom(8)).decode()


def frame(kind, obj):
    payload = json.dumps(obj)
    checksum = binascii.crc32(payload.encode()) & 0xffffffff
    print('{},{}:{:08x}'.format(kind, payload, checksum))


def trace(iterations, sequence):
    buf = array.array('I', [0] * (3 * 1024))
    bad = integrity = completed = 0
    signatures = [0] * 8
    examples = []
    started = time.ticks_us()
    while completed < iterations:
        n = min(1024, iterations - completed)
        # Poison memory before each capture, so omitted stores are detectable.
        for i in range(n * 3):
            buf[i] = 0xdeadbeef
        returned = capture(n, buf)
        if returned != n:
            integrity += 1
        for i in range(n):
            value, inverse, index = buf[i*3], buf[i*3+1], buf[i*3+2]
            corrupt = (value ^ inverse) != 0xffffffff or index != i
            if corrupt:
                integrity += 1
            if value != 255:
                bad += 1
                delta = 255 - value
                if not corrupt and delta in (1, 2, 4, 8, 16, 32, 64, 128):
                    signatures[(1, 2, 4, 8, 16, 32, 64, 128).index(delta)] += 1
            if (value != 255 or corrupt) and len(examples) < 16:
                examples.append([completed+i, value, inverse, index])
        completed += n
    frame('DIAG', dict(session=SESSION, sequence=sequence, iterations=iterations,
          completed=completed, bad=bad, integrity=integrity, signatures=signatures,
          examples=examples, elapsed_us=time.ticks_diff(time.ticks_us(), started)))


def serve():
    sequence = 0
    total = 0
    print("READY,RP2040-ZERO,PROBE2," + SESSION)
    while True:
        line = sys.stdin.readline()
        if not line:
            continue
        fields = line.strip().split()
        if fields == ["PING"]:
            print("PONG,RP2040-ZERO,PROBE2," + SESSION)
            continue
        if fields == ['INFO']:
            frame('INFO', dict(session=SESSION, implementation=str(sys.implementation),
                  freq=machine.freq(), reset_cause=machine.reset_cause(), ticks_ms=time.ticks_ms()))
            continue
        if len(fields) != 2 or fields[0] not in ("RUN", "TRACE", "DENSE"):
            print("ERR,COMMAND")
            continue
        try:
            iterations = int(fields[1])
        except ValueError:
            print("ERR,COUNT")
            continue
        if not 1 <= iterations <= 1000000:
            print("ERR,RANGE")
            continue
        if fields[0] == 'DENSE':
            sequence += 1
            buf = array.array('I', [0xdeadbeef] * 5)
            print('BEGIN,{},{},{}'.format(SESSION, sequence, iterations))
            started = time.ticks_us()
            returned = dense(iterations, buf)
            elapsed = time.ticks_diff(time.ticks_us(), started)
            bad, completed, first_value, first_index, inverse = buf
            valid = returned == bad and completed == iterations and (first_value ^ inverse) == 0xffffffff
            delta = 255 - first_value
            signature = None
            if bad and valid and delta in (1, 2, 4, 8, 16, 32, 64, 128):
                signature = (1, 2, 4, 8, 16, 32, 64, 128).index(delta) + 1
            frame('DENSE', dict(session=SESSION, sequence=sequence, iterations=iterations,
                  completed=completed, bad=bad, integrity=int(not valid), first_value=first_value,
                  first_index=first_index, inverse=inverse, signature=signature,
                  started_ticks_us=started, elapsed_us=elapsed))
            continue
        if fields[0] == 'TRACE':
            sequence += 1
            print('BEGIN,{},{},{}'.format(SESSION, sequence, iterations))
            trace(iterations, sequence)
            continue
        started = time.ticks_us()
        errors = count_bad(iterations)
        elapsed_us = time.ticks_diff(time.ticks_us(), started)
        sequence += 1
        total += errors
        print("RESULT,{},{},{},{},{}".format(sequence, iterations, errors, total, elapsed_us))


if __name__ == "__main__":
    serve()
