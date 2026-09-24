import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

if os.name == "nt":
    import winsound


# Allow running this file directly from src/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.audio_stego import embed_payload_in_audio, extract_payload_from_audio
from src.crypto_engine import (
    create_payload_dict,
    generate_key_pair,
    save_public_key_to_file,
    sign_payload,
    unpack_payload_package,
    verify_signature,
)


class AudioStegoGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("INF2005 Audio Steganography (Simple GUI)")
        self.root.geometry("820x560")

        self.private_key, self.public_key = generate_key_pair()
        self.public_key_path = os.path.join("keys", "public_key_gui.pem")
        save_public_key_to_file(self.public_key, self.public_key_path)

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="Audio LSB Embed/Extract", font=("Segoe UI", 14, "bold"))
        title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        ttk.Label(main, text="Cover WAV:").grid(row=1, column=0, sticky="w", pady=4)
        self.cover_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.cover_var, width=70).grid(row=1, column=1, columnspan=2, sticky="we", pady=4)
        ttk.Button(main, text="Browse", command=self.browse_cover).grid(row=1, column=3, padx=4)

        ttk.Label(main, text="Stego WAV:").grid(row=2, column=0, sticky="w", pady=4)
        self.stego_var = tk.StringVar(value="stego_output.wav")
        ttk.Entry(main, textvariable=self.stego_var, width=70).grid(row=2, column=1, columnspan=2, sticky="we", pady=4)
        ttk.Button(main, text="Save As", command=self.browse_stego).grid(row=2, column=3, padx=4)

        ttk.Label(main, text="Media ID:").grid(row=3, column=0, sticky="w", pady=4)
        self.media_id_var = tk.StringVar(value="WAV_GUI_001")
        ttk.Entry(main, textvariable=self.media_id_var, width=26).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(main, text="Metadata:").grid(row=3, column=2, sticky="e", pady=4)
        self.meta_var = tk.StringVar(value="GUI demo payload")
        ttk.Entry(main, textvariable=self.meta_var, width=24).grid(row=3, column=3, sticky="we", pady=4)

        ttk.Label(main, text="LSB bits (1-8):").grid(row=4, column=0, sticky="w", pady=4)
        self.bits_var = tk.StringVar(value="2")
        ttk.Spinbox(main, from_=1, to=8, textvariable=self.bits_var, width=8).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Label(main, text="Start byte:").grid(row=4, column=2, sticky="e", pady=4)
        self.start_var = tk.StringVar(value="4096")
        ttk.Entry(main, textvariable=self.start_var, width=10).grid(row=4, column=3, sticky="w", pady=4)

        ttk.Label(main, text="Payload message (optional):").grid(row=5, column=0, sticky="nw", pady=4)
        self.payload_text = tk.Text(main, width=78, height=6)
        self.payload_text.grid(row=5, column=1, columnspan=3, sticky="we", pady=4)

        button_row = ttk.Frame(main)
        button_row.grid(row=6, column=0, columnspan=4, sticky="we", pady=(10, 6))

        ttk.Button(button_row, text="Embed", command=self.embed).pack(side="left", padx=4)
        ttk.Button(button_row, text="Extract + Verify", command=self.extract_verify).pack(side="left", padx=4)
        ttk.Button(button_row, text="Play Cover", command=self.play_cover).pack(side="left", padx=4)
        ttk.Button(button_row, text="Play Stego", command=self.play_stego).pack(side="left", padx=4)

        ttk.Label(main, text="Output Log:").grid(row=7, column=0, sticky="nw", pady=4)
        self.log_text = tk.Text(main, width=78, height=13, state="disabled")
        self.log_text.grid(row=7, column=1, columnspan=3, sticky="nsew", pady=4)

        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=1)
        main.rowconfigure(7, weight=1)

        self.log(f"Public key for this session: {self.public_key_path}")

    def log(self, text: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def browse_cover(self):
        path = filedialog.askopenfilename(
            title="Select cover WAV",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")],
        )
        if path:
            self.cover_var.set(path)
            if not self.stego_var.get() or self.stego_var.get() == "stego_output.wav":
                base, _ = os.path.splitext(path)
                self.stego_var.set(base + "_stego.wav")

    def browse_stego(self):
        path = filedialog.asksaveasfilename(
            title="Save stego WAV",
            defaultextension=".wav",
            filetypes=[("WAV files", "*.wav")],
        )
        if path:
            self.stego_var.set(path)

    def _read_params(self):
        cover = self.cover_var.get().strip()
        stego = self.stego_var.get().strip()
        if not cover:
            raise ValueError("Please choose a cover WAV file.")
        if not stego:
            raise ValueError("Please choose an output stego WAV file.")

        bits = int(self.bits_var.get())
        start = int(self.start_var.get())
        if not (1 <= bits <= 8):
            raise ValueError("LSB bits must be between 1 and 8.")
        if start < 0:
            raise ValueError("Start byte must be >= 0.")
        return cover, stego, bits, start

    def embed(self):
        try:
            cover, stego, bits, start = self._read_params()
            custom_message = self.payload_text.get("1.0", "end").strip()

            payload = create_payload_dict(
                media_id=self.media_id_var.get().strip() or "WAV_GUI",
                file_path=cover,
                custom_metadata=(self.meta_var.get().strip() + " | " + custom_message).strip(" |"),
            )
            signed_payload = sign_payload(payload, self.private_key)

            embed_payload_in_audio(
                cover_audio_path=cover,
                payload_bytes=signed_payload,
                output_stego_path=stego,
                bits_per_byte=bits,
                start_byte_offset=start,
            )

            self.log(f"[EMBED] Success -> {stego}")
            self.log(f"[EMBED] media_id={payload['media_id']} bits={bits} start={start}")
            messagebox.showinfo("Embed Complete", f"Stego WAV created:\n{stego}")
        except Exception as exc:
            self.log(f"[EMBED] Error: {exc}")
            messagebox.showerror("Embed Error", str(exc))

    def extract_verify(self):
        try:
            stego = self.stego_var.get().strip()
            if not stego:
                raise ValueError("Please select a stego WAV path.")

            bits = int(self.bits_var.get())
            start = int(self.start_var.get())

            extracted_bytes = extract_payload_from_audio(
                stego_audio_path=stego,
                bits_per_byte=bits,
                start_byte_offset=start,
            )
            payload_dict, signature = unpack_payload_package(extracted_bytes)
            is_valid = verify_signature(payload_dict, signature, self.public_key)
            verdict = "AUTHENTIC" if is_valid else "SIGNATURE INVALID"

            self.log(f"[EXTRACT] Verdict: {verdict}")
            self.log(f"[EXTRACT] media_id={payload_dict.get('media_id', '')}")
            self.log(f"[EXTRACT] payload={json.dumps(payload_dict, indent=2)}")
            messagebox.showinfo("Verification Result", verdict)
        except Exception as exc:
            self.log(f"[EXTRACT] Error: {exc}")
            messagebox.showerror("Extract Error", str(exc))

    def _play_wav(self, path: str):
        if os.name != "nt":
            messagebox.showwarning("Playback", "Audio playback helper is only configured for Windows.")
            return
        if not path or not os.path.exists(path):
            messagebox.showwarning("Playback", "WAV file not found.")
            return
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)

    def play_cover(self):
        self._play_wav(self.cover_var.get().strip())

    def play_stego(self):
        self._play_wav(self.stego_var.get().strip())


def main():
    root = tk.Tk()
    app = AudioStegoGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
