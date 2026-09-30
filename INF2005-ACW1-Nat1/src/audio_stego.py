import wave


def bytes_to_bits(data_bytes: bytes) -> str:
    """Converts a byte string into a binary bit string ('0's and '1's)."""
    return "".join(f"{b:08b}" for b in data_bytes)


def bits_to_bytes(bit_string: str) -> bytes:
    """Converts a binary bit string back into raw bytes."""
    length = (len(bit_string) // 8) * 8
    byte_list = [int(bit_string[i : i + 8], 2) for i in range(0, length, 8)]
    return bytes(byte_list)


def _read_wav_frames(audio_path: str):
    with wave.open(audio_path, "rb") as wav_file:
        if wav_file.getcomptype() != "NONE":
            raise ValueError("Only uncompressed WAV/PCM files are supported.")

        params = wav_file.getparams()
        frame_bytes = bytearray(wav_file.readframes(wav_file.getnframes()))
        return params, frame_bytes


def embed_payload_in_audio(
    cover_audio_path: str,
    payload_bytes: bytes,
    output_stego_path: str,
    bits_per_byte: int = 1,
    start_byte_offset: int = 0,
) -> str:
    """
    Embeds payload bytes in WAV/PCM frame bytes using LSB replacement.

    - bits_per_byte: Number of LSBs to replace per frame byte (1 to 8)
    - start_byte_offset: Frame-byte index to start embedding from
    """
    if not (1 <= bits_per_byte <= 8):
        raise ValueError("bits_per_byte must be between 1 and 8.")

    params, frame_bytes = _read_wav_frames(cover_audio_path)

    if not (0 <= start_byte_offset < len(frame_bytes)):
        raise ValueError("start_byte_offset is out of valid range for this audio file.")

    payload_len_bits = f"{len(payload_bytes):032b}"
    full_bit_stream = payload_len_bits + bytes_to_bits(payload_bytes)

    available_capacity_bits = (len(frame_bytes) - start_byte_offset) * bits_per_byte
    if len(full_bit_stream) > available_capacity_bits:
        raise ValueError(
            f"Payload size ({len(full_bit_stream)} bits) exceeds "
            f"cover audio capacity ({available_capacity_bits} bits)!"
        )

    bit_index = 0
    byte_index = start_byte_offset
    total_bits = len(full_bit_stream)

    mask = ~((1 << bits_per_byte) - 1) & 0xFF

    while bit_index < total_bits:
        chunk = full_bit_stream[bit_index : bit_index + bits_per_byte]
        if len(chunk) < bits_per_byte:
            chunk = chunk.ljust(bits_per_byte, "0")

        chunk_val = int(chunk, 2)
        frame_bytes[byte_index] = (frame_bytes[byte_index] & mask) | chunk_val

        bit_index += bits_per_byte
        byte_index += 1

    with wave.open(output_stego_path, "wb") as stego_wav:
        stego_wav.setparams(params)
        stego_wav.writeframes(frame_bytes)

    return output_stego_path


def extract_payload_from_audio(
    stego_audio_path: str,
    bits_per_byte: int = 1,
    start_byte_offset: int = 0,
) -> bytes:
    """
    Extracts payload bytes from WAV/PCM frame bytes using LSB replacement.
    """
    if not (1 <= bits_per_byte <= 8):
        raise ValueError("bits_per_byte must be between 1 and 8.")

    _, frame_bytes = _read_wav_frames(stego_audio_path)

    if not (0 <= start_byte_offset < len(frame_bytes)):
        raise ValueError("start_byte_offset is out of valid range for this audio file.")

    bit_mask = (1 << bits_per_byte) - 1
    extracted_bit_stream = ""
    byte_index = start_byte_offset

    while len(extracted_bit_stream) < 32:
        if byte_index >= len(frame_bytes):
            raise ValueError("Unable to read payload header from the selected start location.")

        val = frame_bytes[byte_index] & bit_mask
        extracted_bit_stream += f"{val:0{bits_per_byte}b}"
        byte_index += 1

    payload_length_bytes = int(extracted_bit_stream[:32], 2)
    total_required_bits = 32 + (payload_length_bytes * 8)

    max_available_bits = (len(frame_bytes) - start_byte_offset) * bits_per_byte
    if total_required_bits > max_available_bits:
        raise ValueError(
            "Extracted payload header is invalid for this file. "
            "Possible causes: wrong start location, wrong LSB setting, or tampering."
        )

    while len(extracted_bit_stream) < total_required_bits:
        val = frame_bytes[byte_index] & bit_mask
        extracted_bit_stream += f"{val:0{bits_per_byte}b}"
        byte_index += 1

    payload_bits = extracted_bit_stream[32:total_required_bits]
    return bits_to_bytes(payload_bits)