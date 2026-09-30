# INF2005 Cybersecurity ACW1 - Image & Audio Integrity Verifier

## 1. System Dependencies

* **Python Version:** Python 3.9, 3.10, or 3.11 (Windows / macOS / Linux)
* **Required Libraries:**
* `Flask` (Web GUI framework)
* `cryptography` (RSA 2048 key generation, PSS padding with MGF1/SHA-256)
* `numpy` (Pixel array processing)
* `Pillow` (PNG image rendering and channel manipulation)



---

## 2. Setup Instructions

1. **Clone Repository & Navigate to Project Root:**
```bash
git clone https://github.com/violetdisp2408/INF2005-ACW1.git
cd INF2005-ACW1

```


2. **Create & Activate Virtual Environment:**
* **Windows (PowerShell):**
```powershell
py -m venv .venv
\.venv\Scripts\activate

```


* **macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate

```




3. **Install Dependencies:**
```bash
pip install -r requirements.txt

```



---

## 3. Key Management & Safe Instructions for Signature Verification

### Key Management

* **Public Key Storage:** Legitimate public keys are stored as `.pem` files in the `keys/` directory (`keys/public_key.pem`, `keys/public_key_test.pem`, `keys/public_key_gui.pem`).


* **Private Key Handling:** Private keys are generated dynamically in memory during local protection operations and are strictly kept secret. They are never hardcoded, written to unencrypted disk locations, or committed to version control.



### Reproducing Signature Verification Step-by-Step

1. **Sender (Party A):**
* Selects a cover image (`sample.png`) or audio file (`sample.wav`).


* Configures LSB depth ($1 \le \text{bits} \le 8$) and payload start offset.


* Generates a 2048-bit RSA key pair, creates the JSON payload package (Media ID, Timestamp, File Hash, Nonce, Metadata), signs it via RSA-PSS, and embeds it.


* Transmits the output stego file and public key (`keys/public_key.pem`) to Party B.




2. **Receiver (Party B):**
* Downloads `stego_sample.png` (or `stego_sample.wav`) and Party A's public key into a local folder.


* Opens the Web GUI (or Tkinter GUI) and navigates to **2. Verify**.


* Uploads the stego file and imports Party A's `public_key.pem`.


* Enters the agreed LSB depth and start offset parameters.


* Executes verification: The system extracts the payload header, retrieves the signature, re-computes the payload SHA-256 digest, and verifies the RSA-PSS signature against Party A's public key.





---

## 4. Technical Design Specifications

### Selectable LSB Embedding (1 to 8 Bits)

The application allows dynamic configuration of LSB depth from 1 to 8 bits per byte/channel across both image and audio workflows:

* **Image (`src/image_stego.py`):** Modifies the lower $N$ bits across flattened RGB pixel channel arrays.


* **Audio (`src/audio_stego.py`):** Modifies the lower $N$ bits of uncompressed 16-bit PCM WAV frame bytes.


* Both interfaces provide dynamic input selectors (spinboxes/sliders) in the GUI.



### Payload Start Location Design & Security

* **Flexible Start Offsets:** The payload can be embedded starting at any valid byte offset in audio frames (`start_byte_offset`) or pixel offset in images (`start_pixel_offset`).


* **Decoder Identification:** The decoder extracts payload data by applying the identical start offset supplied during the protection phase.


* **Security & Tamper Resistance:**
* **Obscurity & Guessing Resistance:** Without knowing the exact start location and LSB configuration, an unauthorized party extracting bits from offset 0 will extract garbage bytes, causing JSON parsing to fail.


* **Tamper Protection:** The payload contains a 2048-bit RSA-PSS signature over the payload bytes (including the cover file SHA-256 hash and unique nonce). If an attacker attempts to guess, alter, or tamper with bits at any location, `verify_signature()` or `verify_media_integrity()` immediately detects the alteration and rejects the file.





### Supported Payload Sizes & Confidentiality

The system accepts three standardized payload profiles:

1. **Short Message:** Course Learning Objective text snippet.
2. **Large Message:** Entire Project Overview paragraph.
3. **Custom Confidential Payload:** Encrypted or formatted metadata strings containing custom user payloads.



---

## 5. Execution Commands

### A. Web GUI Application (Flask)

```powershell
$env:PORT="5050"; py app.py

```

> Web Interface: `[http://127.0.0.1:5050](http://127.0.0.1:5050)`

### B. Standalone Audio Tkinter GUI

```bash
py src/audio_gui_simple.py

```

### C. Image Steganography Test Suite

```bash
py -m src.image_stego

```

### D. Audio Steganography Test Suite

```bash
py src/test_member1_2.py

```

---

## 6. Required Test Cases & Verification Evidence

The test suite covers **2 positive cases** and **4 negative cases** across image and audio cover objects:

| Test ID | Media Type | Scenario / Test Description | Expected Result | Result |
| --- | --- | --- | --- | --- |
| **IMG-POS-1** | Image (`PNG`) | Valid signature, legitimate public key, correct offset (500), LSB=2

 | `[PASS] AUTHENTIC` | **PASS**<br> |
| **IMG-NEG-1** | Image (`PNG`) | Wrong Public Key verification (Unauthentic sender)

 | `[FAIL] SIGNATURE INVALID` | **PASS**<br> |
| **AUD-POS-1** | Audio (`WAV`) | Valid signature, legitimate public key, offset=4096, LSB=2

 | `[PASS] AUTHENTIC` | **PASS**<br> |
| **AUD-NEG-1** | Audio (`WAV`) | Wrong Public Key verification (Unauthentic sender)

 | `[PASS] SIGNATURE INVALID` | **PASS**<br> |
| **AUD-NEG-2** | Audio (`WAV`) | Wrong Start Location offset extraction

 | `[PASS] WRONG START DETECTED` | **PASS**<br> |
| **AUD-NEG-3** | Audio (`WAV`) | Bit-flip Tampering on stego audio frame byte

 | `[PASS] TAMPERING DETECTED` | **PASS**<br> |
| **CAP-NEG-1** | Audio/Image | Capacity Exceeded (Payload larger than cover capacity)

 | `[PASS] CAPACITY LIMIT ENFORCED` | **PASS**<br> |

---

## 7. Test Execution Terminal Logs (Evidence)

### Image Test Suite Output (`src/image_stego.py`)



```text
==================================================
      RUNNING INF2005 STEGANOGRAPHY TESTS        
==================================================

[1] Generating RSA Key Pairs...
    -> Saved legitimate public key to 'keys/public_key.pem'

[2] Creating and Signing Payload...
    -> Payload signed. Package size: 388 bytes

[3] Embedding Payload into 'sample.png'...
    -> Successfully created 'stego_sample.png'

--------------------------------------------------
 TEST CASE 1: POSITIVE TEST (Valid Public Key)
--------------------------------------------------
Media ID : PNG_TEST_001
Result   : [PASS] AUTHENTIC

--------------------------------------------------
 TEST CASE 2: NEGATIVE TEST (Wrong Public Key)
--------------------------------------------------
Result   : [FAIL] SIGNATURE INVALID (EXPECTED BEHAVIOR)
==================================================

```

### Audio Test Suite Output (`src/test_member1_2.py`)



```text
==================================================
  RUNNING INF2005 AUDIO STEGANOGRAPHY TEST SUITE 
==================================================

[1] Preparing WAV sample and keys...
    -> Generated WAV sample: sample.wav
    -> Saved public key to: keys\public_key_test.pem

[2] Creating and signing payload...
    -> Signed package size: 396 bytes

[3] Embedding payload into WAV cover object...
    -> Created stego WAV: stego_sample.wav

--------------------------------------------------
 TEST CASE 1: POSITIVE (CORRECT KEY, SETTINGS)
--------------------------------------------------
Media ID : WAV_TEST_001
Result   : [PASS] AUTHENTIC

--------------------------------------------------
 TEST CASE 2: NEGATIVE (WRONG PUBLIC KEY)
--------------------------------------------------
Result   : [PASS] SIGNATURE INVALID

--------------------------------------------------
 TEST CASE 3: NEGATIVE (WRONG START LOCATION)
--------------------------------------------------
Result   : [PASS] WRONG START DETECTED

--------------------------------------------------
 TEST CASE 4: NEGATIVE (TAMPERED STEGO AUDIO)
--------------------------------------------------
Result   : [PASS] TAMPERING DETECTED

--------------------------------------------------
 TEST CASE 5: NEGATIVE (CAPACITY CHECK)
--------------------------------------------------
Result   : [PASS] CAPACITY LIMIT ENFORCED

==================================================
 SUMMARY
==================================================
Case 1: PASS
Case 2: PASS
Case 3: PASS
Case 4: PASS
Case 5: PASS

Final Result: 5/5 cases passed

```