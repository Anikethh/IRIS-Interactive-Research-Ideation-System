/**
 * Secure API Key Management
 * This module provides client-side encryption for API keys stored in localStorage
 * to improve security when the application is deployed.
 */

// Load the encryption script from the server
let encryptionInitialized = false;

// Initialize encryption functions
async function initializeEncryption() {
    if (encryptionInitialized) return;
    
    try {
        const response = await fetch('/api/encryption-script');
        const scriptText = await response.text();
        
        // Execute the script to get encryption functions in a sandboxed context
        const scriptEl = document.createElement('script');
        scriptEl.textContent = scriptText;
        
        // Create a shadow root for isolation if supported
        const container = document.createElement('div');
        if (container.attachShadow) {
            const shadow = container.attachShadow({mode: 'closed'});
            shadow.appendChild(scriptEl);
        } else {
            document.head.appendChild(scriptEl);
        }
        
        encryptionInitialized = true;
        console.log('Encryption initialized successfully');
    } catch (error) {
        console.error('Failed to initialize encryption:', error);
        throw new Error('Encryption initialization failed');
    }
}

// Securely store an API key
async function securelyStoreApiKey(provider, key) {
    await initializeEncryption();
    
    try {
        // Generate a device-specific salt using multiple factors
        const deviceInfo = [
            navigator.userAgent,
            window.screen.width,
            window.screen.height,
            navigator.language,
            Intl.DateTimeFormat().resolvedOptions().timeZone
        ].join('|');
        
        const deviceHash = await createHash(deviceInfo);
        
        // Add entropy from crypto API if available
        let extraEntropy = '';
        if (window.crypto && window.crypto.getRandomValues) {
            const randomBytes = new Uint8Array(16);
            window.crypto.getRandomValues(randomBytes);
            extraEntropy = Array.from(randomBytes).map(b => b.toString(16).padStart(2, '0')).join('');
        }
        
        // Encrypt the API key before storing
        const encryptedKey = typeof encryptData === 'function' 
            ? await encryptData(key, deviceHash.slice(0, 16) + extraEntropy)
            : btoa(key); // Basic fallback if encryption fails
            
        // Store with metadata
        const keyData = {
            provider: provider,
            key: encryptedKey,
            timestamp: Date.now(),
            version: '2.0', // For future migrations
            encrypted: typeof encryptData === 'function'
        };
        
        // Save to localStorage with validity check
        const savedKeys = JSON.parse(localStorage.getItem('secureApiKeys') || '{}');
        savedKeys[provider] = keyData;
        
        // Verify we can write to localStorage
        localStorage.setItem('secureApiKeys', JSON.stringify(savedKeys));
        const verifyRead = localStorage.getItem('secureApiKeys');
        if (!verifyRead) {
            throw new Error('Failed to verify localStorage write');
        }
        
        // Also send to server for session use
        const response = await fetch('/api/set_api_key', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                provider: provider,
                key: key // Server will handle its own encryption
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to store key on server');
        }
        
        return true;
    } catch (error) {
        console.error('Error storing API key:', error);
        return false;
    }
}

// Retrieve an API key securely
async function securelyRetrieveApiKey(provider) {
    await initializeEncryption();
    
    try {
        // Get encrypted key from localStorage
        const savedKeys = JSON.parse(localStorage.getItem('secureApiKeys') || '{}');
        if (!savedKeys[provider]) return null;
        
        const keyData = savedKeys[provider];
        
        // Check if key was stored with encryption
        if (!keyData.encrypted) {
            console.warn('Retrieved key was not stored with encryption');
            return atob(keyData.key);
        }
        
        // Generate device hash for decryption
        const deviceInfo = [
            navigator.userAgent,
            window.screen.width,
            window.screen.height,
            navigator.language,
            Intl.DateTimeFormat().resolvedOptions().timeZone
        ].join('|');
        
        const deviceHash = await createHash(deviceInfo);
        
        // Add entropy from stored timestamp
        const extraEntropy = keyData.timestamp.toString(16);
        
        // Decrypt the key
        const decryptedKey = typeof decryptData === 'function'
            ? await decryptData(keyData.key, deviceHash.slice(0, 16) + extraEntropy)
            : atob(keyData.key); // Basic fallback
            
        if (!decryptedKey) {
            throw new Error('Decryption failed');
        }
        
        return decryptedKey;
    } catch (error) {
        console.error('Error retrieving API key:', error);
        return null;
    }
}

// Delete a stored API key
async function deleteApiKey(provider) {
    try {
        // Remove from localStorage
        const savedKeys = JSON.parse(localStorage.getItem('secureApiKeys') || '{}');
        if (savedKeys[provider]) {
            // Securely overwrite the key data before deletion
            savedKeys[provider].key = '';
            localStorage.setItem('secureApiKeys', JSON.stringify(savedKeys));
            delete savedKeys[provider];
            localStorage.setItem('secureApiKeys', JSON.stringify(savedKeys));
        }
        
        // Remove from server
        const response = await fetch('/api/delete_api_key', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ provider })
        });
        
        return response.ok;
    } catch (error) {
        console.error('Error deleting API key:', error);
        return false;
    }
}

// List saved API key providers without exposing keys
function listSavedKeyProviders() {
    try {
        const savedKeys = JSON.parse(localStorage.getItem('secureApiKeys') || '{}');
        return Object.entries(savedKeys).map(([provider, data]) => ({
            provider,
            timestamp: data.timestamp,
            version: data.version || '1.0',
            encrypted: !!data.encrypted
        }));
    } catch (error) {
        console.error('Error listing saved keys:', error);
        return [];
    }
}

// Create secure hash of text
async function createHash(text) {
    if (window.crypto && window.crypto.subtle) {
        try {
            const data = new TextEncoder().encode(text);
            const hashBuffer = await window.crypto.subtle.digest('SHA-256', data);
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        } catch (error) {
            console.warn('Crypto API hash failed:', error);
        }
    }
    
    // Fallback hash if crypto API fails
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
        const char = text.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(16);
}

// Check if running in secure context
function isSecureContext() {
    return window.isSecureContext === true;
}

// Export the API
window.secureKeyManager = {
    securelyStoreApiKey,
    securelyRetrieveApiKey,
    deleteApiKey,
    listSavedKeyProviders,
    isSecureContext
};