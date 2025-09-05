
import os
import hashlib
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

KEY_ENV_VAR = "SNAPSHOT_ENCRYPTION_KEY"

def pad(data):
    pad_len = AES.block_size - len(data) % AES.block_size
    return data + bytes([pad_len]) * pad_len

def encrypt_file(input_path, output_path):
    key = os.getenv(KEY_ENV_VAR)
    if not key:
        raise EnvironmentError(f"Missing env var: {KEY_ENV_VAR}")
    key = hashlib.sha256(key.encode()).digest()

    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)

    with open(input_path, 'rb') as f:
        data = f.read()

    encrypted = cipher.encrypt(pad(data))
    with open(output_path, 'wb') as f:
        f.write(iv + encrypted)

    print(f"Encrypted snapshot saved to: {output_path}")
