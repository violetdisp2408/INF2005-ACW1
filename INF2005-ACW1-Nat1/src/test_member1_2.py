import math
import os
import struct
import sys
import wave

# Automatically add project root to python path to prevent "No module named 'src'"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.audio_stego import embed_payload_in_audio, extract_payload_from_audio
from src.crypto_engine import (
	create_payload_dict,
	generate_key_pair,
	load_public_key_from_file,
	save_public_key_to_file,
	sign_payload,
	unpack_payload_package,
	verify_signature,
)


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SAMPLE_WAV = os.path.join(ROOT_DIR, "sample.wav")
STEGO_WAV = os.path.join(ROOT_DIR, "stego_sample.wav")
TAMPERED_STEGO_WAV = os.path.join(ROOT_DIR, "tampered_stego_sample.wav")
PUBLIC_KEY_PATH = os.path.join(ROOT_DIR, "keys", "public_key_test.pem")


def generate_sample_wav(
	output_path: str,
	duration_seconds: float = 3.0,
	sample_rate: int = 44100,
	frequency_hz: float = 440.0,
) -> str:
	"""Creates a deterministic mono 16-bit PCM WAV test file."""
	amplitude = 12000
	total_samples = int(duration_seconds * sample_rate)

	frames = bytearray()
	for i in range(total_samples):
		value = int(amplitude * math.sin(2.0 * math.pi * frequency_hz * i / sample_rate))
		frames.extend(struct.pack("<h", value))

	with wave.open(output_path, "wb") as wav_file:
		wav_file.setnchannels(1)
		wav_file.setsampwidth(2)
		wav_file.setframerate(sample_rate)
		wav_file.writeframes(frames)

	return output_path


def tamper_wav_frame_byte(input_wav_path: str, output_wav_path: str, frame_byte_index: int) -> str:
	"""Flips one LSB in a selected frame byte to simulate tampering."""
	with wave.open(input_wav_path, "rb") as source:
		params = source.getparams()
		frame_bytes = bytearray(source.readframes(source.getnframes()))

	if not (0 <= frame_byte_index < len(frame_bytes)):
		raise ValueError("frame_byte_index is out of range.")

	frame_bytes[frame_byte_index] ^= 0x01

	with wave.open(output_wav_path, "wb") as target:
		target.setparams(params)
		target.writeframes(frame_bytes)

	return output_wav_path


def run_audio_tests():
	print("==================================================")
	print("  RUNNING INF2005 AUDIO STEGANOGRAPHY TEST SUITE ")
	print("==================================================\n")

	print("[1] Preparing WAV sample and keys...")
	generate_sample_wav(SAMPLE_WAV)
	private_key_A, public_key_A = generate_key_pair()
	_, public_key_B = generate_key_pair()
	save_public_key_to_file(public_key_A, PUBLIC_KEY_PATH)
	print(f"    -> Generated WAV sample: {os.path.basename(SAMPLE_WAV)}")
	print(f"    -> Saved public key to: {PUBLIC_KEY_PATH}")

	print("\n[2] Creating and signing payload...")
	payload_dict = create_payload_dict(
		media_id="WAV_TEST_001",
		file_path=SAMPLE_WAV,
		custom_metadata="INF2005 audio verification payload",
	)
	signed_payload_bytes = sign_payload(payload_dict, private_key_A)
	print(f"    -> Signed package size: {len(signed_payload_bytes)} bytes")

	bits_per_byte = 2
	start_byte_offset = 4096

	print("\n[3] Embedding payload into WAV cover object...")
	embed_payload_in_audio(
		cover_audio_path=SAMPLE_WAV,
		payload_bytes=signed_payload_bytes,
		output_stego_path=STEGO_WAV,
		bits_per_byte=bits_per_byte,
		start_byte_offset=start_byte_offset,
	)
	print(f"    -> Created stego WAV: {os.path.basename(STEGO_WAV)}")

	print("\n--------------------------------------------------")
	print(" TEST CASE 1: POSITIVE (CORRECT KEY, SETTINGS)")
	print("--------------------------------------------------")
	extracted_bytes = extract_payload_from_audio(
		stego_audio_path=STEGO_WAV,
		bits_per_byte=bits_per_byte,
		start_byte_offset=start_byte_offset,
	)
	extracted_dict, extracted_signature = unpack_payload_package(extracted_bytes)
	loaded_public_key = load_public_key_from_file(PUBLIC_KEY_PATH)
	case_1_pass = verify_signature(extracted_dict, extracted_signature, loaded_public_key)
	print(f"Media ID : {extracted_dict['media_id']}")
	print(f"Result   : {'[PASS] AUTHENTIC' if case_1_pass else '[FAIL] UNEXPECTED REJECTION'}")

	print("\n--------------------------------------------------")
	print(" TEST CASE 2: NEGATIVE (WRONG PUBLIC KEY)")
	print("--------------------------------------------------")
	case_2_pass = not verify_signature(extracted_dict, extracted_signature, public_key_B)
	print(f"Result   : {'[PASS] SIGNATURE INVALID' if case_2_pass else '[FAIL] INCORRECTLY ACCEPTED'}")

	print("\n--------------------------------------------------")
	print(" TEST CASE 3: NEGATIVE (WRONG START LOCATION)")
	print("--------------------------------------------------")
	case_3_pass = False
	try:
		wrong_start_bytes = extract_payload_from_audio(
			stego_audio_path=STEGO_WAV,
			bits_per_byte=bits_per_byte,
			start_byte_offset=start_byte_offset + 101,
		)
		wrong_payload, wrong_signature = unpack_payload_package(wrong_start_bytes)
		case_3_pass = not verify_signature(wrong_payload, wrong_signature, loaded_public_key)
	except Exception:
		case_3_pass = True
	print(f"Result   : {'[PASS] WRONG START DETECTED' if case_3_pass else '[FAIL] WRONG START NOT DETECTED'}")

	print("\n--------------------------------------------------")
	print(" TEST CASE 4: NEGATIVE (TAMPERED STEGO AUDIO)")
	print("--------------------------------------------------")
	tamper_wav_frame_byte(
		input_wav_path=STEGO_WAV,
		output_wav_path=TAMPERED_STEGO_WAV,
		frame_byte_index=start_byte_offset + 20,
	)

	case_4_pass = False
	try:
		tampered_extracted_bytes = extract_payload_from_audio(
			stego_audio_path=TAMPERED_STEGO_WAV,
			bits_per_byte=bits_per_byte,
			start_byte_offset=start_byte_offset,
		)
		tampered_payload, tampered_signature = unpack_payload_package(tampered_extracted_bytes)
		case_4_pass = not verify_signature(tampered_payload, tampered_signature, loaded_public_key)
	except Exception:
		case_4_pass = True
	print(f"Result   : {'[PASS] TAMPERING DETECTED' if case_4_pass else '[FAIL] TAMPERING NOT DETECTED'}")

	print("\n--------------------------------------------------")
	print(" TEST CASE 5: NEGATIVE (CAPACITY CHECK)")
	print("--------------------------------------------------")
	case_5_pass = False
	try:
		embed_payload_in_audio(
			cover_audio_path=SAMPLE_WAV,
			payload_bytes=b"A" * 500000,
			output_stego_path=os.path.join(ROOT_DIR, "too_big_stego.wav"),
			bits_per_byte=1,
			start_byte_offset=0,
		)
	except ValueError:
		case_5_pass = True
	print(f"Result   : {'[PASS] CAPACITY LIMIT ENFORCED' if case_5_pass else '[FAIL] CAPACITY CHECK FAILED'}")

	print("\n==================================================")
	print(" SUMMARY")
	print("==================================================")

	all_cases = [case_1_pass, case_2_pass, case_3_pass, case_4_pass, case_5_pass]
	for idx, status in enumerate(all_cases, start=1):
		print(f"Case {idx}: {'PASS' if status else 'FAIL'}")

	total_passed = sum(1 for c in all_cases if c)
	print(f"\nFinal Result: {total_passed}/{len(all_cases)} cases passed")


if __name__ == "__main__":
	run_audio_tests()
