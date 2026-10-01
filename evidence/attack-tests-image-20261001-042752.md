# Attack tests: test-001 (image, 1 LSB, start 568557)

Run 2026-10-01T04:27:52. Untouched file verifies as **Authentic**. 8/8 attacks gave the expected verdict.

| Attack | What was done | Expected | Actual | OK |
|---|---|---|---|---|
| Edit the content | painted a 103×103 magenta square at (82, 95) | Tampered | Tampered | ✅ |
| Invisible edit | flipped the lowest bit of unit 0 (outside the note) | Tampered | Tampered | ✅ |
| Damage the signature | flipped one bit 100 bytes from the end of the note (inside the signature) | Signature Invalid | Signature Invalid | ✅ |
| Wrong key | verified with a freshly generated public key | Signature Invalid | Signature Invalid | ✅ |
| Wrong start position | verified from pixel 571,008 instead of 568,557 | Wrong Start Location / Payload Missing | Wrong Start Location / Payload Missing | ✅ |
| Wrong LSB count | verified with 2 LSBs instead of 1 | Wrong Start Location / Payload Missing | Wrong Start Location / Payload Missing | ✅ |
| Scramble the note | flipped a bit in 3 bytes at the start of the note's text | Cannot Verify | Cannot Verify | ✅ |
| Unprotected file | verified a lossless copy of the original, unprotected file | Wrong Start Location / Payload Missing | Wrong Start Location / Payload Missing | ✅ |

## What happened in each attack

### Edit the content: Tampered

Painted a 103×103 magenta square at (82, 95).

- Settings used: the right key, LSB count and start
- Values changed in the file: 30,793 (0 inside the note, 30,793 outside)
  - pixel (82, 95) G (outside the note): 11111111 → 00000000
  - pixel (83, 95) G (outside the note): 11111111 → 00000000
  - pixel (84, 95) G (outside the note): 11111111 → 00000000
- Length read from the first 32 bits: 540 bytes (fits)
- Read the hidden note: pass: Read 540 bytes at pixel 568,557, 1 LSB: file ID test-001.
- Check the signature: pass: verify_signature() says yes for this public key.
- Check the file wasn't edited: fail: verify_media_integrity() says no: this file's hash is 7719e3929924…, the note has 6b23c83a22c8….
- Why: The note and its signature weren't touched, so the note still reads and the signature still checks out. But the file's hash now differs from the one sealed inside the note, so the hash check fails.

### Invisible edit: Tampered

Flipped the lowest bit of unit 0 (outside the note).

- Settings used: the right key, LSB count and start
- Values changed in the file: 1 (0 inside the note, 1 outside)
  - pixel (0, 0) R (outside the note): 11111111 → 11111110
- Length read from the first 32 bits: 540 bytes (fits)
- Read the hidden note: pass: Read 540 bytes at pixel 568,557, 1 LSB: file ID test-001.
- Check the signature: pass: verify_signature() says yes for this public key.
- Check the file wasn't edited: fail: verify_media_integrity() says no: this file's hash is 40965ec51b14…, the note has 6b23c83a22c8….
- Why: Only one bit changed, which you can't see or hear. SHA-256 still changes completely when a single bit changes, so the hash check fails.

### Damage the signature: Signature Invalid

Flipped one bit 100 bytes from the end of the note (inside the signature).

- Settings used: the right key, LSB count and start
- Values changed in the file: 1 (1 inside the note, 0 outside)
  - pixel (77, 688) R (note: signature, byte 157 of 256): 11111111 → 11111110
- Length read from the first 32 bits: 540 bytes (fits)
- Read the hidden note: pass: Read 540 bytes at pixel 568,557, 1 LSB: file ID test-001.
- Check the signature: fail: verify_signature() says no for this public key.
- Check the file wasn't edited: skipped
- Why: The note still reads, but one bit of the signature is different. RSA-PSS verification fails if even one bit of the signature or the note is wrong, so the signature check fails.

### Wrong key: Signature Invalid

Verified with a freshly generated public key.

- Settings used: Public key (ID) 8184 2a36 23a6 e7f1 (right: 7b5b f44b 110c 23c9)
- File contents: unchanged
- Length read from the first 32 bits: 540 bytes (fits)
- Read the hidden note: pass: Read 540 bytes at pixel 568,557, 1 LSB: file ID test-001.
- Check the signature: fail: verify_signature() says no for this public key.
- Check the file wasn't edited: skipped
- Why: Nothing in the file changed. The signature was made with A's private key, and it only checks out with A's public key. With anyone else's key, the signature check fails, which is what a forged file from an impostor would look like.

### Wrong start position: Wrong Start Location / Payload Missing

Verified from pixel 571,008 instead of 568,557.

- Settings used: Start (pixel) 571,008 (right: 568,557)
- File contents: unchanged
- Length read from the first 32 bits: 864,891,788 bytes (impossible, bigger than the space)
- Read the hidden note: fail: Nothing readable at pixel 571,008, 1 LSB (IndexError: index 2377188 is out of bounds for axis 0 with size 2377188).
- Check the signature: skipped
- Check the file wasn't edited: skipped
- Why: The first 32 bits read from the wrong place are just ordinary pixel/sample bits, so the 'length' they give is nonsense (usually bigger than the whole file). No note can be read.

### Wrong LSB count: Wrong Start Location / Payload Missing

Verified with 2 LSBs instead of 1.

- Settings used: LSB count 2 (right: 1)
- File contents: unchanged
- Length read from the first 32 bits: 142,639,266 bytes (impossible, bigger than the space)
- Read the hidden note: fail: Nothing readable at pixel 568,557, 2 LSBs (IndexError: index 2377188 is out of bounds for axis 0 with size 2377188).
- Check the signature: skipped
- Check the file wasn't edited: skipped
- Why: The right place is read, but the bits are grouped the wrong way, so the 'length' and every byte after it come out scrambled. No note can be read.

### Scramble the note: Cannot Verify

Flipped a bit in 3 bytes at the start of the note's text.

- Settings used: the right key, LSB count and start
- Values changed in the file: 3 (3 inside the note, 0 outside)
  - pixel (570, 686) G (note: text, character 1): 01101000 → 01101001
  - pixel (573, 686) R (note: text, character 2): 01110000 → 01110001
  - pixel (575, 686) B (note: text, character 3): 01010010 → 01010011
- Length read from the first 32 bits: 540 bytes (fits)
- Read the hidden note: fail: Found 540 bytes at pixel 568,557, 1 LSB, but they don't unpack: 'utf-8' codec can't decode byte 0xfb in position 0: invalid start byte.
- Check the signature: skipped
- Check the file wasn't edited: skipped
- Why: The length at the start is still sensible, so something is read, but its first characters are damaged and it no longer parses as a note. Something is there, but it can't be checked.

### Unprotected file: Wrong Start Location / Payload Missing

Verified a lossless copy of the original, unprotected file.

- Settings used: the right key, LSB count and start
- Values changed in the file: 2,233 (2,233 inside the note, 0 outside)
  - pixel (549, 686) R (note: length header): 01100000 → 01100001
  - pixel (550, 686) G (note: length header): 01010010 → 01010011
  - pixel (550, 686) B (note: length header): 01000100 → 01000101
- Length read from the first 32 bits: 2,399,641,783 bytes (impossible, bigger than the space)
- Read the hidden note: fail: Nothing readable at pixel 568,557, 1 LSB (IndexError: index 2377188 is out of bounds for axis 0 with size 2377188).
- Check the signature: skipped
- Check the file wasn't edited: skipped
- Why: This is the original file from before protecting. Nothing was ever hidden in it, so the reader only finds ordinary bits.
