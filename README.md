# INF2005-ACW1
Team Project
# INF2005 Cybersecurity ACW1 - Image & Audio Integrity Verifier

## 1. System Dependencies
* **Python Version:** Python 3.9, 3.10, or 3.11 (Windows / macOS / Linux)
* **Required Libraries:**
  * `Flask` (Web framework for GUI)
  * `cryptography` (RSA 2048 key generation, PSS padding, SHA-256)
  * `numpy` (Pixel array processing)
  * `Pillow` (Image decoding and encoding)

---

## 2. Setup Instructions

1. **Clone Repository & Navigate to Project Root:**
   ```bash
   git clone [https://github.com/violetdisp2408/INF2005-ACW1.git](https://github.com/violetdisp2408/INF2005-ACW1.git)
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

## 3. Key Management & Safe Instructions for Verification

* **Public Key Location:** Generated public keys are automatically saved under `keys/public_key.pem` and `keys/public_key_test.pem`.


* **Private Key Security Notice:** As per assignment requirements, private keys are generated dynamically in memory for local demo purposes only and are never hardcoded or committed to version control.


* **How to Reproduce Signature Verification:**
1. Use the provided public key (`keys/public_key.pem`) in the web interface or CLI.


2. Load the stego file (`stego_sample.png` or `stego_sample.wav`).


3. Ensure the LSB bit setting and start offset match the protection configuration (e.g., LSB=2, Offset=500 for images; LSB=2, Offset=4096 for audio).


4. Execute verification; the system will unpack the RSA-PSS signature and verify it against the public key.





---

## 4. Execution Commands

### A. Web GUI Application (Flask)

* **Windows (PowerShell):**
```powershell
$env:PORT="5050"; py app.py

```


* **macOS / Linux:**
```bash
PORT=5050 python3 app.py

```



> Web Interface: `http://127.0.0.1:5050`

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

## 5. Expected Outputs

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

```

```