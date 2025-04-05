import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import json

def generate_key(password, salt=None):
    """Generate a symmetric encryption key from a password using PBKDF2"""
    if salt is None:
        salt = os.urandom(16)
    
    # Use strong key derivation parameters
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,  # Increased iterations for better security
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt

def encrypt_api_key(api_key, password):
    """Encrypt an API key using a password"""
    if not password:
        raise ValueError("Encryption password cannot be empty")
    if not api_key:
        raise ValueError("API key cannot be empty")
        
    key, salt = generate_key(password)
    f = Fernet(key)
    encrypted_key = f.encrypt(api_key.encode())
    
    return {
        'encrypted': base64.urlsafe_b64encode(encrypted_key).decode(),
        'salt': base64.urlsafe_b64encode(salt).decode(),
        'timestamp': int(os.path.getctime(__file__))  # Add creation timestamp
    }

def decrypt_api_key(encrypted_data, password):
    """Decrypt an API key using a password"""
    if not password:
        raise ValueError("Decryption password cannot be empty")
    if not encrypted_data:
        raise ValueError("No encrypted data provided")
        
    try:
        encrypted = base64.urlsafe_b64decode(encrypted_data['encrypted'])
        salt = base64.urlsafe_b64decode(encrypted_data['salt'])
        
        key, _ = generate_key(password, salt)
        f = Fernet(key)
        decrypted = f.decrypt(encrypted)
        
        # Validate the decrypted data is valid UTF-8
        return decrypted.decode('utf-8')
    except Exception as e:
        print(f"Decryption error: {e}")
        return None

def get_client_encryption_script():
    """Returns JavaScript code for client-side encryption"""
    return """
        // Client-side encryption functions
        async function encryptData(data, key) {
            // Convert data and key to bytes
            const dataBytes = new TextEncoder().encode(data);
            const keyBytes = new TextEncoder().encode(key);
            
            // Generate encryption key from password
            const cryptoKey = await window.crypto.subtle.importKey(
                'raw',
                keyBytes,
                { name: 'PBKDF2' },
                false,
                ['deriveBits']
            );
            
            // Generate random IV
            const iv = window.crypto.getRandomValues(new Uint8Array(12));
            
            // Encrypt the data
            const aesKey = await window.crypto.subtle.deriveKey(
                {
                    name: 'PBKDF2',
                    salt: iv,
                    iterations: 100000,
                    hash: 'SHA-256'
                },
                cryptoKey,
                { name: 'AES-GCM', length: 256 },
                false,
                ['encrypt']
            );
            
            const encryptedData = await window.crypto.subtle.encrypt(
                { name: 'AES-GCM', iv: iv },
                aesKey,
                dataBytes
            );
            
            // Combine IV and encrypted data
            const combined = new Uint8Array(iv.length + encryptedData.byteLength);
            combined.set(iv);
            combined.set(new Uint8Array(encryptedData), iv.length);
            
            // Return as base64
            return btoa(String.fromCharCode.apply(null, combined));
        }

        async function decryptData(encryptedBase64, key) {
            try {
                // Convert from base64
                const combined = new Uint8Array(atob(encryptedBase64).split('').map(c => c.charCodeAt(0)));
                
                // Extract IV and encrypted data
                const iv = combined.slice(0, 12);
                const encryptedData = combined.slice(12);
                
                // Generate key from password
                const keyBytes = new TextEncoder().encode(key);
                const cryptoKey = await window.crypto.subtle.importKey(
                    'raw',
                    keyBytes,
                    { name: 'PBKDF2' },
                    false,
                    ['deriveBits']
                );
                
                // Generate AES key
                const aesKey = await window.crypto.subtle.deriveKey(
                    {
                        name: 'PBKDF2',
                        salt: iv,
                        iterations: 100000,
                        hash: 'SHA-256'
                    },
                    cryptoKey,
                    { name: 'AES-GCM', length: 256 },
                    false,
                    ['decrypt']
                );
                
                // Decrypt
                const decryptedBytes = await window.crypto.subtle.decrypt(
                    { name: 'AES-GCM', iv: iv },
                    aesKey,
                    encryptedData
                );
                
                // Convert to string
                return new TextDecoder().decode(decryptedBytes);
            } catch (error) {
                console.error('Decryption failed:', error);
                return null;
            }
        }
    """