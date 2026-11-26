# Build, Gradle, CI/CD, release and observability

Seniors often own build health and the release train. Expect questions on slow builds, safe rollouts and production monitoring.

### 12.1 Gradle essentials

- **Phases:** initialization (which projects) → configuration (build the task graph; must be fast and side-effect free) → execution.
- **Kotlin DSL + version catalog:**

```toml
# gradle/libs.versions.toml
[versions]
kotlin = "2.2.0"
room = "2.7.2"
[libraries]
room-runtime = { module = "androidx.room:room-runtime", version.ref = "room" }
room-compiler = { module = "androidx.room:room-compiler", version.ref = "room" }
[plugins]
ksp = { id = "com.google.devtools.ksp", version = "2.2.0-2.0.2" }
```

(Version numbers are illustrative; check current releases.)

- **Convention plugins** in `build-logic` share `compileSdk`, Kotlin options, lint and test setup across modules.
- **Build variants:** build types (`debug`, `release`) × product flavours (`free`/`paid`, `staging`/`prod`). Use `buildConfigField` or resource values per variant.
- **KSP** over **kapt**: KSP is up to \~2x faster and works with K2; migrate Room, Hilt and Moshi to KSP.

### 12.2 Making builds faster

1. Enable the **configuration cache** and **build cache** (local + remote).
2. Modularise so changes recompile fewer modules; use `implementation` instead of `api`.
3. Use KSP, avoid kapt; enable non-transitive R classes.
4. Run `./gradlew assembleDebug --scan` (Build Scan) or the Build Analyzer to find slow tasks and configuration time.
5. Give Gradle enough heap (`org.gradle.jvmargs`), and keep AGP, Kotlin and Gradle up to date.

### 12.3 CI/CD pipeline

A typical pipeline (GitHub Actions, Bitrise, GitLab CI, Jenkins):

1. On every PR: static analysis (Android Lint, Detekt, ktlint/Spotless), unit tests, screenshot tests, build debug, dependency checks.
2. On merge to main: instrumented tests on Gradle Managed Devices or Firebase Test Lab, build release AAB, upload to an internal track.
3. Release: signed AAB (Play App Signing; upload key kept in CI secrets), versionCode auto-incremented, release notes, Fastlane or Gradle Play Publisher to promote tracks.

### 12.4 Safe releases

- **Staged rollout:** 1% → 5% → 20% → 50% → 100%, gated on crash-free users and ANR rate. Halt the rollout if vitals regress.
- **Feature flags / remote config:** ship dark, enable gradually, kill switch for risky features. Decouple deploy from release.
- **Release trains:** e.g. weekly or bi-weekly cut, code freeze, regression testing, hotfix branch policy.
- **In-app updates API:** flexible or immediate updates; force-update for critical security fixes through a minimum-version check.
- **Backward compatibility:** old app versions stay in use for months, so APIs must stay compatible (versioned endpoints, additive changes).

### 12.5 Observability

- **Crash and ANR reporting:** Firebase Crashlytics, Sentry, Play Console vitals. Upload R8 mapping files.
- **Performance monitoring:** Firebase Performance, custom traces around key journeys, JankStats.
- **Analytics and logging:** structured events, funnels, non-fatal error logging with context (no PII).
- **Alerting:** dashboards per release; alert on crash-free rate dropping below target (e.g. 99.8% users).

### Interview questions

1. **Your clean build takes 12 minutes. What do you do?** Profile with a Build Scan, check configuration time vs execution, enable configuration and remote build caches, replace kapt with KSP, split large modules, parallelise CI, and cache Gradle in CI. {Medium}
2. **A crash appears in 0.5% of users after release. What is your process?** Halt the staged rollout, triage the stack trace (de-obfuscated), check which devices/OS versions, disable via feature flag if possible, hotfix with a test reproducing it, resume the rollout, then run a blameless post-mortem. {Medium}
3. **`api` vs `implementation`?** `api` leaks the dependency to consumers (they recompile when it changes); `implementation` keeps it internal. Default to `implementation`. {Easy}
