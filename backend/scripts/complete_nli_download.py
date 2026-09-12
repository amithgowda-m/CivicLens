import os
import sys
import glob
import time
from pathlib import Path

# Ensure UTF-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def clean_stale_locks():
    print("[*] Checking and clearing stale Hugging Face locks...")
    lock_dir = os.path.expanduser("~/.cache/huggingface/hub/.locks/models--cross-encoder--nli-deberta-v3-base")
    if os.path.exists(lock_dir):
        for f in glob.glob(os.path.join(lock_dir, "*")):
            try:
                os.remove(f)
                print(f"  Removed stale lock: {os.path.basename(f)}")
            except Exception as e:
                print(f"  Warning: could not remove lock {f}: {e}")

    # Remove zero-byte incomplete files
    blobs_dir = os.path.expanduser("~/.cache/huggingface/hub/models--cross-encoder--nli-deberta-v3-base/blobs")
    if os.path.exists(blobs_dir):
        for inc in glob.glob(os.path.join(blobs_dir, "*.incomplete")):
            try:
                if os.path.getsize(inc) == 0:
                    os.remove(inc)
                    print(f"  Cleaned empty partial file: {os.path.basename(inc)}")
            except Exception:
                pass

def download_complete_model():
    print("\n[*] Starting reliable multi-attempt download for 'cross-encoder/nli-deberta-v3-base'...")
    from huggingface_hub import snapshot_download

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[*] Download attempt {attempt}/{max_retries}...")
            path = snapshot_download(
                repo_id="cross-encoder/nli-deberta-v3-base",
                resume_download=True,
                max_workers=4
            )
            print(f"\n[+] SUCCESS! Model downloaded and verified at: {path}")
            break
        except Exception as err:
            print(f"[-] Attempt {attempt} encountered network hiccup: {err}")
            clean_stale_locks()
            if attempt < max_retries:
                print("  Retrying in 3 seconds...")
                time.sleep(3)
            else:
                print("[-] All retries exhausted. Check internet connection.")
                sys.exit(1)

    print("\n[*] Verifying CrossEncoder loads into memory...")
    from sentence_transformers import CrossEncoder
    ce = CrossEncoder("cross-encoder/nli-deberta-v3-base")
    scores = ce.predict([("The municipal corporation revised property taxes.", "Taxes were updated.")])
    print(f"[+] CrossEncoder test inference passed! Verification score: {scores}")
    print("[+] DeBERTa NLI model is 100% READY and CACHED locally.")

if __name__ == "__main__":
    clean_stale_locks()
    download_complete_model()
