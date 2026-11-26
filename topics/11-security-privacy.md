# Security and privacy

Assume the device and the APK are in the attacker's hands. The client can make attacks harder; the **server** must enforce anything that matters.

### 11.1 Storing secrets and data

- **Never** ship API secrets in the APK (strings, `BuildConfig`, NDK). They can be extracted in minutes. Use a backend proxy or short-lived tokens.
- Store keys in the **Android Keystore** (hardware-backed, StrongBox where available); keys never leave secure hardware.
- Encrypt sensitive local data with a Keystore-held AES-GCM key (e.g. with Tink). Note that Jetpack `security-crypto` (`EncryptedSharedPreferences`) has been deprecated; know it, but prefer Tink + DataStore for new code.
- App-specific storage (`filesDir`) is private to your UID; external/shared storage is not.
- Exclude secrets from cloud backups (`android:dataExtractionRules` / `fullBackupContent`).

```kotlin
val keyGen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
keyGen.init(
    KeyGenParameterSpec.Builder("token_key", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
        .setUserAuthenticationRequired(false)
        .build()
)
val key = keyGen.generateKey()
```

### 11.2 Network security

- HTTPS only; cleartext is blocked by default since Android 9. Configure exceptions in `network_security_config.xml`.
- **Certificate pinning** (OkHttp `CertificatePinner` or network security config `<pin-set>`) defends against compromised CAs and MITM proxies. Always pin backup keys and have a remote kill switch, or a rotation can brick your app.
- Don't log tokens or PII; strip logs in release with R8 rules or a logging wrapper.

### 11.3 Authentication

- OAuth 2.0 / OIDC with **Authorization Code + PKCE**, using Custom Tabs (never an embedded WebView for third-party login).
- **Credential Manager** unifies passwords, passkeys and Sign in with Google.
- Short-lived access token + refresh token; refresh tokens stored encrypted.
- Biometrics with `BiometricPrompt`, ideally bound to a Keystore key (`setUserAuthenticationRequired(true)`) so a bypass cannot unlock data.

### 11.4 Component and IPC safety

- Set `android:exported="false"` unless another app must start the component.
- Validate all intent extras and deep-link parameters (a deep link is untrusted input).
- Use `FLAG_IMMUTABLE` PendingIntents; use explicit intents for internal communication.
- WebView: disable JavaScript unless needed, never `addJavascriptInterface` on untrusted content, restrict file access, validate URLs.
- Use `FileProvider` with `content://` URIs instead of `file://`.

### 11.5 App integrity and tampering

- **Play Integrity API:** the server verifies that requests come from your genuine app on a genuine device.
- R8 obfuscation raises the cost of reverse engineering; root/hook detection only raises the bar.

### 11.6 Privacy

- Request the minimum permissions, at the moment they are needed; use the Photo Picker instead of storage permissions; approximate location when precise is not needed.
- Fill in the Play **Data safety** form accurately (it includes SDKs' data collection).
- Handle consent (GDPR, Australian Privacy Act), data deletion requests and account deletion (required by Play).

### Interview questions

1. **How would you protect an API key used by the app?** You cannot fully. Move the call behind your backend, use per-user tokens, restrict the key (package name + SHA-1 on Google APIs), and add Play Integrity checks. {Medium}
2. **What does certificate pinning protect against, and what is the risk?** It stops interception by a trusted-but-wrong CA or a user-installed proxy cert. The risk is outages when certificates rotate; pin to the public key (SPKI) of intermediate + backup, and allow remote disable. {Hard}
3. **Is data in Room secure?** It is private to the app sandbox, but readable on rooted devices or via backups. Encrypt it (SQLCipher) if it is sensitive, and exclude it from backup. {Medium}
