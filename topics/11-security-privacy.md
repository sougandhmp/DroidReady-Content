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

### 11.2 Network security, SSL pinning and alternatives

**In one line:** enforce HTTPS, understand both declarative and programmatic SSL pinning with backup keys, and know when Certificate Transparency or mTLS is a better fit.

**Say this in the interview:** "Cleartext traffic is blocked by default since Android 9, and I allow exceptions only for local debugging in `network_security_config.xml`. For high-risk apps like banking, I pin the **SubjectPublicKeyInfo (SPKI)** hash rather than the leaf certificate so routine renewals with the same keypair don't break clients. I can configure pinning declaratively in `network_security_config.xml` (which covers OkHttp, `HttpURLConnection` and WebView) or programmatically via OkHttp's `CertificatePinner` (which makes remote pin updates and kill switches easier). Because static pinning risks locking users out if certificates rotate unexpectedly, I always include a backup pin, set an expiration date, and consider **Certificate Transparency (CT)** to catch misissued certificates without lockout risk—or **mutual TLS (mTLS)** with a Keystore-backed client certificate when the server must authenticate the device itself."

**Example:**

```xml
<!-- res/xml/network_security_config.xml: declarative SPKI pinning -->
<network-security-config>
    <domain-config>
        <domain includeSubdomains="true">api.example.com</domain>
        <pin-set expiration="2027-06-30">
            <pin digest="SHA-256">CURRENT_SPKI_HASH_PLACEHOLDER=</pin>
            <pin digest="SHA-256">BACKUP_SPKI_HASH_PLACEHOLDER=</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

```kotlin
// Programmatic OkHttp pinning (easier to pair with remote config / kill switch)
val pinner = CertificatePinner.Builder()
    .add("api.example.com", "sha256/CURRENT_SPKI_HASH_PLACEHOLDER=")
    .add("api.example.com", "sha256/BACKUP_SPKI_HASH_PLACEHOLDER=")
    .build()
val client = OkHttpClient.Builder().certificatePinner(pinner).build()
```

| Option | What it protects against | Operational risk & trade-offs |
| --- | --- | --- |
| `network_security_config.xml` | Rogue CAs, user-installed proxies across all stacks | Pin rotation requires an app release unless expired |
| OkHttp `CertificatePinner` | Rogue CAs, proxies on OkHttp calls | Easier to toggle remotely; doesn't cover WebView |
| Certificate Transparency (CT) | Misissued certs from compromised CAs | Zero lockout risk on rotation; requires CT logs/verifier |
| Mutual TLS (mTLS) | Unauthorized clients & MITM | Strongest device auth, but adds client-cert provisioning/renewal |

**Common mistake:** Pinning a single leaf certificate with no backup pin, expiration, or remote recovery plan.

**Follow-ups:**

- *Why pin the public key (SPKI) instead of the leaf certificate?* If the server renews its certificate using the same keypair, the SPKI pin keeps working.
- *Can SSL pinning stop a user on a rooted device?* No. Tools like Frida can hook `TrustManager` or `CertificatePinner` at runtime, so pair pinning with server-side Play Integrity checks.

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

**Example, checking a purchase with a standard Play Integrity request:**

1. Early on, the app prepares an integrity token provider, so later requests are quick.
2. When the user buys, the app hashes the request details and asks for a token with that `requestHash`.
3. The app sends the token and the purchase request to your server.
4. The server has Google Play decrypt and verify the token.
5. The server checks that the package name and request hash match, then reads the verdicts.
6. The server decides: allow, ask for another check, or refuse.

**Common mistake:** Checking the integrity result only on the device, where it can be tampered with.

**Follow-ups:**

- *Where should a Play Integrity verdict be checked?* On your server, which then decides whether to allow the action.

### 11.7 Tapjacking, screen capture and secure coding hygiene

**In one line:** protect sensitive UI from overlay attacks and screenshots, scrub sensitive logs and clipboard entries, and treat client-side tamper checks as defense in depth.

**Say this in the interview:** "Beyond storage and networking, I harden the UI and runtime surface. For tapjacking—where a malicious overlay tricks the user into tapping a hidden button—I set `filterTouchesWhenObscured = true` on sensitive views and `window.setHideOverlayWindows(true)` on Android 12+ for payment or permission flows. For banking or password screens, `FLAG_SECURE` blocks screenshots, screen recording, and the recent-apps thumbnail. In release builds I strip `Log.d`/`Log.v` with R8 `-assumenosideeffects` so tokens never leak to logcat, and I mark copied secrets with `ClipDescription.EXTRA_IS_SENSITIVE` on Android 13+ so the clipboard preview hides them. Client-side root or Frida checks only raise the bar; real enforcement stays on the server with Play Integrity."

**Example:**

```kotlin
// Protect sensitive screen from screenshots, recents preview, and non-system overlays
window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
    window.setHideOverlayWindows(true)
}
```

**Common mistake:** Leaving debug `Log` statements or sensitive screen thumbnails visible in release builds.

**Follow-ups:**

- *What does `FLAG_SECURE` prevent?* Screenshots, screen sharing/recording, and the system showing the screen's snapshot in the Recents overview.

### Interview questions

1. **Where do you store a user's auth token securely?** Encrypted with a Keystore-held key (for example Tink with DataStore), in app-private storage, excluded from backups. Never in plain SharedPreferences or logs. {Medium}
2. **How would you protect an API key used by the app?** You can't fully protect it in the APK. Move the call to your backend, use per-user tokens, restrict the key to your package and certificate, and verify requests with Play Integrity. {Medium}
3. **What does certificate pinning protect against, and what is the risk?** Interception by a wrong-but-trusted CA or a user-installed proxy certificate. The risk is outages when certificates change, so pin a backup key, set an expiry and keep a remote switch. {Hard}
4. **Why use PKCE for OAuth on mobile?** A mobile app can't keep a client secret, and another app could intercept the authorization code. PKCE makes the code useless without the verifier that only your app has. {Medium}
5. **How do you implement biometric login securely?** Use a Keystore key that requires biometric authentication and pass a `Cipher` as a `CryptoObject` to `BiometricPrompt`, decrypting only in the success callback, so it can't be bypassed by hooking. {Hard}
6. **How do you handle deep links securely?** Allow-list hosts and paths, validate every parameter's type and format, never perform sensitive actions without confirmation, and never follow redirect URLs from a link. {Medium}
7. **Is data in a Room database secure?** It's private to the app sandbox but readable on a rooted device or through backups. Encrypt sensitive data, for example with SQLCipher, and exclude it from backups. {Medium}
8. **What is Play Integrity used for?** Your server checks a signed verdict that the request comes from your genuine app, installed from Play, on a genuine device, before trusting sensitive actions. {Medium}
9. **When should you choose Certificate Transparency or mTLS instead of static SSL pinning?** Use Certificate Transparency to detect misissued certificates without risking client lockouts on key rotation; use mTLS when the server also needs cryptographic proof of the client's identity via a Keystore-backed certificate. {Hard}
10. **How do you protect sensitive screens from tapjacking and screen-capture leaks?** Use `FLAG_SECURE` to block screenshots and recents thumbnails, `filterTouchesWhenObscured` or `setHideOverlayWindows(true)` (API 31+) against overlays, and `EXTRA_IS_SENSITIVE` for copied secrets. {Medium}
