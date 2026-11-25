---
name: kmp-kotlin
description: "Kotlin rules for multiplatform code: null handling, sealed interfaces, data classes, coroutines, dispatchers, JVM-only APIs in commonMain. Load when writing or reviewing Kotlin in a multiplatform module, or a build fails on a java import."
applyTo: '**/*.kt'
tags: [kmp, mobile, standards]
---

# Kotlin Rules for Multiplatform Code

## Nulls and types

- Write no `!!`. Use `?.`, `?:`, `requireNotNull(x) { "why" }` or `checkNotNull` so a failure names its cause.
- Model a closed set of outcomes as a `sealed interface` or an `enum class`. A `when` over it takes no `else` branch, so a new case fails compilation at every use.
- Declare models as `data class` with `val` properties. Change one with `copy`.
- Expose `List`, `Set` and `Map`. Keep `MutableList` and `MutableStateFlow` private to the class that owns them.
- Mark a declaration `internal` or `private` unless another module reads it. Only the app entry points and the Swift-facing functions in `iosMain` stay public.
- Wrap a primitive that carries meaning in a `@JvmInline value class` when two of them could be swapped by mistake, such as two ids of type `String`.

## Errors

- Catch the narrowest type that the call throws. For network and storage that is `IOException` from `kotlinx.io`, Ktor `ResponseException` and `SerializationException`.
- Never catch `Exception` or `Throwable`. Both swallow `CancellationException`, and a swallowed cancellation leaves a coroutine running after its screen closed.
- When a broad catch is unavoidable at a boundary, rethrow cancellation first:

```kotlin
try {
    block()
} catch (e: CancellationException) {
    throw e
} catch (e: IllegalStateException) {
    report(e)
}
```

- Use `runCatching` only on code that never suspends.
- Return an expected failure as a value, such as an enum or a sealed result. Throw only for a programming error.

## Coroutines

- Launch from a scope that has an owner: `viewModelScope` in a view model, a scope passed in by the constructor elsewhere. `GlobalScope` and a scope built inline have no owner.
- Take `CoroutineDispatcher` as a constructor parameter in any class that switches dispatcher. Tests then pass a test dispatcher.
- Use `Dispatchers.IO` through `kotlinx.coroutines.IO` for blocking work. It exists on every target.
- Mark a function `suspend` for one result and return `Flow` for a stream. A function does one or the other.
- Collect a flow in the UI with `collectAsStateWithLifecycle()`.

## Common code boundaries

`commonMain` compiles for the JVM, Android and iOS, so it sees only the Kotlin standard library and multiplatform libraries.

| Need | Use in `commonMain` | Keep out of `commonMain` |
|---|---|---|
| Time | `kotlin.time.Clock`, `kotlin.time.Instant` | `java.time`, `System.currentTimeMillis` |
| Files and bytes | `kotlinx.io` | `java.io.File`, `okio` added by hand |
| Ids | `kotlin.uuid.Uuid` with `@OptIn(ExperimentalUuidApi::class)` | `java.util.UUID` |
| JSON | `kotlinx.serialization` | Gson, Moshi, `org.json` |
| Concurrency | coroutines, `Mutex`, `kotlin.concurrent.atomics` | `synchronized`, `java.util.concurrent` |
| Logging | one logger port, see {{ skill_link("kmp-platform") }} | `android.util.Log`, `println` |
| Formatting | Compose resources with arguments | `String.format` |

An unresolved reference to `java.*` or `android.*` in `commonMain` means the line belongs behind a port, never that the source set needs a new dependency.

## Global state

- Hold no mutable state in a top-level `val` or an `object`. State lives in a view model, a repository or the database, and dependency injection gives it a lifetime.
- An `object` holds constants and pure functions only.

## Closing check

```bash
./gradlew detekt ktlintCheck
```

Exit 0 closes the step. Fix a finding in code. Suppress one only with `@Suppress("RuleName")` on the smallest declaration, and state the reason in the change summary.
