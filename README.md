# INF2005-ACW1
Team Project
---

### **1. System Dependencies**

* **Python Version:** Python 3.9, 3.10, or 3.11 (Windows / macOS / Linux)
* **Required Libraries:**
* `Flask` (Web framework for the web GUI)
* `cryptography` (RSA 2048 key generation, PSS padding, SHA-256 signing)
* `numpy` (Pixel matrix processing for image steganography)
* `Pillow` (PNG image decoding and encoding)



---

### **2. Setup Instructions**

1. **1. Clone Repository & Navigate to Project Root:** Open VS Code integrated terminal.
```bash
git clone https://github.com/violetdisp2408/INF2005-ACW1.git
cd INF2005-ACW1

```


2. **2. Create & Activate Virtual Environment:** Isolated environment for project dependencies.
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


3. **3. Install Dependencies:** Install required Python libraries.
```bash
pip install -r requirements.txt

```

*If `requirements.txt` is not created yet, install directly:*

```bash
pip install flask cryptography numpy pillow

```


---

### **3. Execution Commands**

#### **A. Running the Web Application (Flask GUI)**

* **Windows (PowerShell):**
```powershell
$env:PORT="5050"; py app.py

```


* **Windows (Command Prompt):**
```cmd
set PORT=5050 && py app.py

```


* **macOS / Linux:**
```bash
PORT=5050 python3 app.py

```



> Access the web interface at **`[http://127.0.0.1:5050](http://127.0.0.1:5050)`**.

---

#### **B. Running the Standalone Audio Tkinter GUI**

* **Windows:**
```cmd
py src/audio_gui_simple.py

```


* **macOS / Linux:**
```bash
python3 src/audio_gui_simple.py

```



---

#### **C. Running Image Steganography Tests (`src/image_stego.py`)**

* **Windows:**
```cmd
py -m src.image_stego

```


* **macOS / Linux:**
```bash
python3 -m src.image_stego

```



---

#### **D. Running Audio Steganography Tests (`src/test_member1_2.py`)**

* **Windows:**
```cmd
py src/test_member1_2.py

```


* **macOS / Linux:**
```bash
python3 src/test_member1_2.py

```



---

### **4. Expected Terminal Outputs**

#### **Expected Output for `src/image_stego.py**`

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

---

#### **Expected Output for `src/test_member1_2.py**`

```text
==================================================
  RUNNING INF2005 AUDIO STEGANOGRAPHY TEST SUITE 
==================================================

[1] Preparing WAV sample and keys...
    -> Generated WAV sample: sample.wav
    -> Saved public key to: INF2005-ACW1\keys\public_key_test.pem

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