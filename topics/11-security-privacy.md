# Security and privacy

Assume the attacker has your APK and a rooted phone. The client can make attacks harder, but the server must enforce anything that really matters. Interviewers want to hear both halves of that.

### 11.1 Storing secrets and sensitive data

**In one line:** never ship secrets in the app, keep keys in the Android Keystore, and encrypt sensitive local data with a key the Keystore holds.

**Say this in the interview:** "Anything in the APK, including `BuildConfig` fields and native code, can be extracted in minutes, so I don't ship API secrets; sensitive calls go through my backend with short-lived user tokens. Encryption keys live in the Android Keystore, which is hardware-backed on most devices, so the key never leaves secure hardware. I encrypt sensitive data with an AES-GCM key from the Keystore, for example with Tink, and I exclude secrets from cloud backups. Jetpack's `EncryptedSharedPreferences` is deprecated now, so for new code I'd use Tink with DataStore."

**Example:**

```kotlin
val keyGen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
keyGen.init(
    KeyGenParameterSpec.Builder("token_key", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
        .build()
)
val key = keyGen.generateKey()     // stays inside the Keystore; the app gets only a handle
```

**Common mistake:** Hiding an API secret in `BuildConfig`, resources or native code.

**Follow-ups:**

- *How would you protect an API key the app must use?* You can't fully. Move the call to your backend, restrict the key (package name and certificate for Google APIs), and verify requests with Play Integrity.

### 11.2 Network security and certificate pinning

**In one line:** use HTTPS only, and optionally pin your server's public key so a fake or compromised certificate authority can't intercept traffic.

**Say this in the interview:** "Cleartext traffic is blocked by default since Android 9, and I configure exceptions only in the network security config. For high-risk apps, like banking, I pin the public key of my server's certificate chain, so even a trusted-but-wrong certificate authority or a user-installed proxy can't read the traffic. The risk is locking users out when certificates rotate, so I pin a backup key too, set an expiry date on the pin set, and keep a remote way to turn pinning off."

**Example:**

```xml
<network-security-config>
    <domain-config>
        <domain includeSubdomains="true">api.example.com</domain>
        <pin-set expiration="2027-06-30">
            <pin digest="SHA-256">CURRENT_KEY_HASH_PLACEHOLDER=</pin>
            <pin digest="SHA-256">BACKUP_KEY_HASH_PLACEHOLDER=</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

**Common mistake:** Pinning with no backup pin or recovery plan.

**Follow-ups:**

- *What do you pin, and what is the backup for?* Pin public keys. A backup pin lets you change keys without cutting off installed apps.

### 11.3 Authentication

**In one line:** use OAuth 2.0 with PKCE in a Custom Tab for login, short-lived access tokens with refresh tokens, and Credential Manager for passkeys.

**Say this in the interview:** "For third-party or enterprise login I use the OAuth authorization-code flow with PKCE in a Custom Tab, never a WebView, usually through the AppAuth library. PKCE means a stolen authorization code is useless without the secret verifier only my app knows. I keep access tokens short-lived and refresh tokens encrypted. For passwords and passkeys I use Credential Manager, which also supports Sign in with Google."

**Example, the PKCE flow:**

1. The app creates a random `code_verifier` and its SHA-256 hash, the `code_challenge`.
2. It opens the login page in a Custom Tab, sending the challenge.
3. After sign-in, the identity provider redirects back to the app with a `code`.
4. The app sends the `code` plus the original verifier to the token endpoint.
5. The server checks that the verifier matches the challenge and returns tokens.

**Common mistake:** Showing the login page in a WebView, where the app can see what the user types.

**Follow-ups:**

- *Why does a public mobile app need PKCE?* It can't keep a client secret. PKCE stops an intercepted authorization code from being exchanged without the verifier.

### 11.4 Biometrics done properly

**In one line:** bind the biometric prompt to a Keystore key, so data can only be decrypted after a real biometric match.

**Say this in the interview:** "A plain `if (biometricSucceeded) showSecrets()` can be bypassed with a hooking tool on a rooted device. Instead, I create a Keystore key that requires user authentication, pass a `Cipher` using that key to `BiometricPrompt` as a `CryptoObject`, and decrypt only inside the success callback. Then the secure hardware itself confirms the user."

**Example:**

```kotlin
KeyGenParameterSpec.Builder("vault_key", KeyProperties.PURPOSE_DECRYPT or KeyProperties.PURPOSE_ENCRYPT)
    .setUserAuthenticationRequired(true)
    .setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)
    .setInvalidatedByBiometricEnrollment(true)          // adding a new fingerprint invalidates the key
    // ...block mode and padding as above
    .build()
```

**Common mistake:** Trusting the success callback alone, with no key that requires authentication.

**Follow-ups:**

- *What can happen to a Keystore key when biometrics change?* A key set to be invalidated by new enrollment can stop working. Handle that by signing in again and creating a new key.

### 11.5 Safe components, deep links and WebViews

**In one line:** expose as little as possible, and treat every intent, deep link and web page as untrusted input.

**Say this in the interview:** "Components are `exported=false` unless another app really needs them. I validate every intent extra and deep-link parameter: allow-list hosts and paths, check formats, and never perform a sensitive action straight from a link without a confirmation screen. PendingIntents are immutable. In WebViews I turn JavaScript off unless needed, never add a JavaScript interface to untrusted content, and don't load URLs that came from a link. For file sharing I use `FileProvider` with `content://` URIs."

**Example:**

```kotlin
fun handleDeepLink(uri: Uri) {
    if (uri.scheme != "https" || uri.host != "example.com") return                 // only our verified domain
    when (uri.path) {
        "/article" -> uri.getQueryParameter("id")?.toLongOrNull()?.let(::openArticle) // validate type
        "/reset" -> uri.getQueryParameter("token")?.takeIf { it.matches(Regex("[A-Za-z0-9_-]{16,128}")) }?.let(::showResetScreen)
    }
}
```

**Common mistake:** Exporting a component or acting on a deep link without validating the input.

**Follow-ups:**

- *Is a verified App Link safe to trust?* No. Verification shows which app may open the domain, but anyone can create a link, so validate its parameters.

### 11.6 App integrity and privacy

**In one line:** Play Integrity lets your server check that requests come from your genuine app on a genuine device; privacy means collecting the minimum and being honest about it.

**Say this in the interview:** "For sensitive actions I send a Play Integrity token to my server, which verifies the app and device are genuine before trusting the request. Obfuscation with R8 and root detection only raise the bar. On privacy, I request the fewest permissions at the moment they're needed, prefer the Photo Picker and approximate location, fill in Play's Data safety form accurately including SDKs, support account and data deletion, and respect consent rules like GDPR."

**Common mistake:** Checking the integrity result only on the device, where it can be tampered with.

**Follow-ups:**

- *Where should a Play Integrity verdict be checked?* On your server, which then decides whether to allow the action.

### Interview questions

1. **Where do you store a user's auth token securely?** Encrypted with a Keystore-held key (for example Tink with DataStore), in app-private storage, excluded from backups. Never in plain SharedPreferences or logs. {Medium}
2. **How would you protect an API key used by the app?** You can't fully protect it in the APK. Move the call to your backend, use per-user tokens, restrict the key to your package and certificate, and verify requests with Play Integrity. {Medium}
3. **What does certificate pinning protect against, and what is the risk?** Interception by a wrong-but-trusted CA or a user-installed proxy certificate. The risk is outages when certificates change, so pin a backup key, set an expiry and keep a remote switch. {Hard}
4. **Why use PKCE for OAuth on mobile?** A mobile app can't keep a client secret, and another app could intercept the authorization code. PKCE makes the code useless without the verifier that only your app has. {Medium}
5. **How do you implement biometric login securely?** Use a Keystore key that requires biometric authentication and pass a `Cipher` as a `CryptoObject` to `BiometricPrompt`, decrypting only in the success callback, so it can't be bypassed by hooking. {Hard}
6. **How do you handle deep links securely?** Allow-list hosts and paths, validate every parameter's type and format, never perform sensitive actions without confirmation, and never follow redirect URLs from a link. {Medium}
7. **Is data in a Room database secure?** It's private to the app sandbox but readable on a rooted device or through backups. Encrypt sensitive data, for example with SQLCipher, and exclude it from backups. {Medium}
8. **What is Play Integrity used for?** Your server checks a signed verdict that the request comes from your genuine app, installed from Play, on a genuine device, before trusting sensitive actions. {Medium}
