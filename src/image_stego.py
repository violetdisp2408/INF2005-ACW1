import numpy as np
from PIL import Image

def bytes_to_bits(data_bytes: bytes) -> str:
    """Converts a byte string into a binary bit string ('0's and '1's)."""
    return ''.join(f'{b:08b}' for b in data_bytes)

def bits_to_bytes(bit_string: str) -> bytes:
    """Converts a binary bit string back into raw bytes."""
    # Truncate bit string to nearest multiple of 8
    length = (len(bit_string) // 8) * 8
    byte_list = []
    for i in range(0, length, 8):
        byte_list.append(int(bit_string[i:i+8], 2))
    return bytes(byte_list)

# ==========================================
# 1. IMAGE LSB EMBEDDING
# ==========================================

def embed_payload_in_image(
    cover_image_path: str,
    payload_bytes: bytes,
    output_stego_path: str,
    bits_per_channel: int = 1,
    start_pixel_offset: int = 0
) -> str:
    """
    Embeds raw payload bytes into a PNG image using LSB replacement.
    
    :param cover_image_path: Path to original PNG.
    :param payload_bytes: Complete signed byte package from crypto_engine.py.
    :param output_stego_path: Path to save the stego PNG.
    :param bits_per_channel: Number of LSBs to use per color channel (1 to 8).
    :param start_pixel_offset: Starting pixel index for embedding.
    :return: Output stego image path.
    """
    if not (1 <= bits_per_channel <= 8):
        raise ValueError("bits_per_channel must be between 1 and 8.")
    
    # Load PNG image and convert to RGB
    img = Image.open(cover_image_path).convert('RGB')
    img_array = np.array(img, dtype=np.uint8)
    shape = img_array.shape # (height, width, 3)
    
    # Flatten array to 1D channel values for easier bit-level indexing
    flat_pixels = img_array.flatten()
    
    # Convert payload into a stream of bit characters ('0' / '1')
    bit_stream = bytes_to_bits(payload_bytes)
    
    # Add a 32-bit header at the start indicating total payload byte length
    payload_len_bits = f"{len(payload_bytes):032b}"
    full_bit_stream = payload_len_bits + bit_stream
    
    # Capacity Check
    start_channel_index = start_pixel_offset * 3
    available_capacity_bits = (len(flat_pixels) - start_channel_index) * bits_per_channel
    
    if len(full_bit_stream) > available_capacity_bits:
        raise ValueError(
            f"Payload size ({len(full_bit_stream)} bits) exceeds "
            f"cover image capacity ({available_capacity_bits} bits)!"
        )
    
    # Embed bits into LSBs
    bit_index = 0
    total_bits = len(full_bit_stream)
    channel_index = start_channel_index
    
    # Bitmask to clear the lowest 'bits_per_channel' bits
    mask = ~((1 << bits_per_channel) - 1) & 0xFF
    
    while bit_index < total_bits:
        # Extract next chunk of bits to embed in this color channel
        chunk = full_bit_stream[bit_index : bit_index + bits_per_channel]
        chunk_val = int(chunk, 2)
        
        # Clear LSBs of current pixel channel and write new payload bits
        flat_pixels[channel_index] = (flat_pixels[channel_index] & mask) | chunk_val
        
        bit_index += len(chunk)
        channel_index += 1
    
    # Reshape flattened array back to image dimensions and save as uncompressed PNG
    stego_array = flat_pixels.reshape(shape)
    stego_img = Image.fromarray(stego_array, mode='RGB')
    stego_img.save(output_stego_path, format='PNG')
    
    return output_stego_path


# ==========================================
# 2. IMAGE LSB EXTRACTION
# ==========================================

def extract_payload_from_image(
    stego_image_path: str,
    bits_per_channel: int = 1,
    start_pixel_offset: int = 0
) -> bytes:
    """
    Extracts embedded payload bytes from a stego PNG file.
    
    :param stego_image_path: Path to stego PNG.
    :param bits_per_channel: Number of LSBs used per color channel (1 to 8).
    :param start_pixel_offset: Starting pixel index used during embedding.
    :return: Raw payload bytes (ready for unpacking by crypto_engine.py).
    """
    img = Image.open(stego_image_path).convert('RGB')
    flat_pixels = np.array(img, dtype=np.uint8).flatten()
    
    channel_index = start_pixel_offset * 3
    bit_mask = (1 << bits_per_channel) - 1
    
    # 1. Read the first 32 bits to determine payload length
    header_bits = ""
    while len(header_bits) < 32:
        val = flat_pixels[channel_index] & bit_mask
        bits = f"{val:0{bits_per_channel}b}"
        header_bits += bits
        channel_index += 1
        
    payload_length_bytes = int(header_bits[:32], 2)
    total_payload_bits = payload_length_bytes * 8
    
    # 2. Extract remaining payload bits
    payload_bits = header_bits[32:]  # Keep leftover bits from header reading
    
    while len(payload_bits) < total_payload_bits:
        val = flat_pixels[channel_index] & bit_mask
        bits = f"{val:0{bits_per_channel}b}"
        payload_bits += bits
        channel_index += 1
        
    # Truncate to exact required length and convert back to bytes
    payload_bits = payload_bits[:total_payload_bits]
    return bits_to_bytes(payload_bits)

# ==========================================
# LOCAL INTEGRATION TEST
# ==========================================
if __name__ == "__main__":
    from crypto_engine import (
        generate_key_pair, 
        create_payload_dict, 
        sign_payload, 
        unpack_payload_package, 
        verify_signature
    )
    
    print("--- STARTING TEST ---")
    
    # 1. Setup keys and payload
    private_key, public_key = generate_key_pair()
    mock_payload = {
        "media_id": "PNG_DEMO_001",
        "timestamp": 1700000000,
        "file_hash": "a1b2c3d4e5f67890",
        "nonce": "12345678",
        "metadata": "INF2005 Test Case"
    }
    
    # 2. Sign payload using crypto_engine
    signed_bytes = sign_payload(mock_payload, private_key)
    print(f"[Crypto] Signed Package Size: {len(signed_bytes)} bytes")
    
    # 3. Embed into PNG starting at pixel 500 using 2 LSBs
    try:
        embed_payload_in_image(
            cover_image_path="sample.png",
            payload_bytes=signed_bytes,
            output_stego_path="stego_sample.png",
            bits_per_channel=2,
            start_pixel_offset=500
        )
        print("[Stego] Successfully embedded payload -> Saved to 'stego_sample.png'")
        
        # 4. Extract from PNG using matching parameters
        extracted_bytes = extract_payload_from_image(
            stego_image_path="stego_sample.png",
            bits_per_channel=2,
            start_pixel_offset=500
        )
        print(f"[Stego] Extracted Raw Bytes Size: {len(extracted_bytes)} bytes")
        
        # 5. Unpack and verify with crypto_engine
        extracted_dict, sig = unpack_payload_package(extracted_bytes)
        is_authentic = verify_signature(extracted_dict, sig, public_key)
        
        print("\n================ VERIFICATION RESULT ================")
        print(f"Extracted Media ID : {extracted_dict['media_id']}")
        print(f"Extracted Nonce    : {extracted_dict['nonce']}")
        print(f"Signature Status   : {'AUTHENTIC PASS' if is_authentic else 'TAMPERED FAIL'}")
        print("=====================================================")
        
    except FileNotFoundError:
        print("\n[!] ERROR: 'sample.png' not found!")
        print("Please drop a standard PNG image named 'sample.png' into your project folder to run this test.")