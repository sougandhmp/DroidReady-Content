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

### 11.7 Deeper dive: OAuth login with PKCE, step by step

PKCE (Proof Key for Code Exchange) stops a stolen authorization code from being useful, because only your app knows the secret verifier.

1. The app creates a random `code_verifier` (43-128 characters) and its SHA-256 hash, the `code_challenge`.
2. It opens the login page in a Custom Tab with `code_challenge` and `code_challenge_method=S256`.
3. The user signs in; the identity provider redirects to your app link (`https://example.com/oauth/callback?code=...`).
4. The app sends the `code` **plus the original `code_verifier`** to the token endpoint.
5. The server hashes the verifier, checks it matches the challenge, and returns access and refresh tokens.

```kotlin
fun newPkce(): Pair<String, String> {
    val bytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
    val verifier = Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
    val digest = MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray())
    val challenge = Base64.encodeToString(digest, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
    return verifier to challenge
}
```

Use the AppAuth library in production rather than writing this yourself. Also send a random `state` value and check it on return to prevent CSRF.

### 11.8 Deeper dive: certificate pinning configured

```xml
<!-- res/xml/network_security_config.xml -->
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <domain-config>
        <domain includeSubdomains="true">api.example.com</domain>
        <pin-set expiration="2027-06-30">
            <pin digest="SHA-256">7HIpactkIAq2Y49orFOOQKurWxmmSFZhBCoQYcRhJ3Y=</pin>  <!-- current intermediate -->
            <pin digest="SHA-256">fwza0LRMXouZHRC8Ei+4PyuldPDcf3UKgO/04cDM1oE=</pin>  <!-- backup key -->
        </pin-set>
    </domain-config>
    <debug-overrides><trust-anchors><certificates src="user" /></trust-anchors></debug-overrides>
</network-security-config>
```

(The pin values above are placeholders.) The `expiration` date makes pinning switch off automatically if you forget to update an old app version, which avoids locking users out. `debug-overrides` lets debug builds use a proxy such as Charles for inspection.

### 11.9 Deeper dive: a key that needs the user's fingerprint

```kotlin
val spec = KeyGenParameterSpec.Builder("vault_key", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
    .setUserAuthenticationRequired(true)
    .setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)   // every use needs a biometric
    .setInvalidatedByBiometricEnrollment(true)                                  // new fingerprint added -> key dies
    .build()

val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, iv)) }

BiometricPrompt(activity, executor, object : BiometricPrompt.AuthenticationCallback() {
    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
        val plain = result.cryptoObject!!.cipher!!.doFinal(encrypted)   // only works after a real biometric match
    }
}).authenticate(promptInfo, BiometricPrompt.CryptoObject(cipher))
```

Why this matters: a plain `if (biometricSucceeded) showSecrets()` can be bypassed with a hooking tool. Binding the key to authentication means the data cannot be decrypted without the secure hardware confirming the user.

### 11.10 Deeper dive: validating a deep link

```kotlin
// Incoming: https://example.com/reset?token=abc&redirect=https://evil.com
fun handleDeepLink(uri: Uri) {
    if (uri.scheme != "https" || uri.host != "example.com") return            // only our verified domain
    when (uri.path) {
        "/reset" -> {
            val token = uri.getQueryParameter("token")?.takeIf { it.matches(Regex("[A-Za-z0-9_-]{16,128}")) } ?: return
            navigateToReset(token)                                             // never auto-perform the action
        }
        "/article" -> uri.getQueryParameter("id")?.toLongOrNull()?.let { openArticle(it) }
    }
    // Ignore 'redirect' entirely: never follow an arbitrary URL from a link (open redirect)
}
```

Rules: allow-list hosts and paths, validate every parameter's type and format, never perform a sensitive action (payments, deletions, changing email) straight from a link without a confirmation screen, and do not load link-supplied URLs into a WebView.

### Interview questions

1. **How would you protect an API key used by the app?** You cannot fully. Move the call behind your backend, use per-user tokens, restrict the key (package name + SHA-1 on Google APIs), and add Play Integrity checks. {Medium}
2. **What does certificate pinning protect against, and what is the risk?** It stops interception by a trusted-but-wrong CA or a user-installed proxy cert. The risk is outages when certificates rotate; pin to the public key (SPKI) of intermediate + backup, and allow remote disable. {Hard}
3. **Is data in Room secure?** It is private to the app sandbox, but readable on rooted devices or via backups. Encrypt it (SQLCipher) if it is sensitive, and exclude it from backup. {Medium}
