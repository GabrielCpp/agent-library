---
name: kmp-data
description: "Kotlin Multiplatform data layer: Ktor, kotlinx.serialization DTOs, Room, DataStore, repositories, migrations. Load when adding or changing an API call, DTO, entity, DAO, migration, repository or cache, or when a screen must work offline."
applyTo: '**/data/**/*.kt,**/schemas/**'
tags: [kmp, mobile, standards]
---

# Data Layer

The data layer implements the repository ports that the domain declares, as laid out in {{ skill_link("kmp-architecture") }}. It lives in `shared/src/commonMain` under each feature's `data` package.

## Three types per record

| Type | Lives in | Annotated with | Seen by |
|---|---|---|---|
| `NoteDto` | `data` | `@Serializable`, `@SerialName` | the API class |
| `NoteEntity` | `data` | `@Entity`, `@PrimaryKey` | the DAO |
| `Note` | `domain` | nothing | view models and screens |

- Map between them with small private `toDomain()` and `toEntity()` extension functions in the repository file.
- A DTO or an entity never leaves the data package. A server field rename then touches one file.
- Give every DTO field an explicit `@SerialName`, and give a field the server may omit a default value.

## Network

```kotlin
fun createHttpClient(): HttpClient =
    HttpClient {
        expectSuccess = true
        install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
    }
```

- Build one `HttpClient` per app and inject it. `HttpClient { }` with no engine argument picks the engine on the classpath, so common code names none.
- Set `expectSuccess = true`. A 4xx or 5xx then throws `ResponseException` and never reaches the JSON parser.
- Set `ignoreUnknownKeys = true`. A new server field must not crash a shipped app.
- An API class takes the client and the base URL as constructor parameters and returns DTOs. It catches nothing.
- Add a request timeout with the `HttpTimeout` plugin for any call a user waits on.

## Local store

- The database is the source of truth. A screen observes a DAO `Flow`, and a refresh writes the network result into the database. The screen updates because the query emits again.
- A DAO read for a screen returns `Flow<List<Entity>>`. A DAO write is a `suspend` function, and `@Upsert` replaces insert-or-update pairs.
- Declare the database in common code and let each platform supply only the builder, as in {{ skill_link("kmp-platform") }}.

```kotlin
@Database(entities = [NoteEntity::class], version = 1)
@ConstructedBy(AppDatabaseConstructor::class)
abstract class AppDatabase : RoomDatabase() {
    abstract fun noteDao(): NoteDao
}

@Suppress("KotlinNoActualForExpect")
expect object AppDatabaseConstructor : RoomDatabaseConstructor<AppDatabase>

fun RoomDatabase.Builder<AppDatabase>.open(queryDispatcher: CoroutineDispatcher): AppDatabase =
    setDriver(BundledSQLiteDriver())
        .setQueryCoroutineContext(queryDispatcher)
        .build()
```

- Use `BundledSQLiteDriver` on every target. All three platforms then run the same SQLite version.
- Room generates the `actual` constructor. Write none by hand.
- Export the schema with `room { schemaDirectory("$projectDir/schemas") }` and commit the JSON files.
- A version bump ships with a migration: `autoMigrations = [AutoMigration(from = 1, to = 2)]` for an additive change, a written `Migration` otherwise. Never call a destructive fallback in a release build.
- Small key and value settings go in DataStore Preferences with an `okio` path from the platform module. A record with a list or a relation goes in Room.

## Repository

```kotlin
override suspend fun refresh(): RefreshOutcome =
    try {
        dao.upsert(api.fetchNotes().map(NoteDto::toEntity))
        RefreshOutcome.Updated
    } catch (_: IOException) {
        RefreshOutcome.Offline
    } catch (_: ResponseException) {
        RefreshOutcome.ServerError
    } catch (_: SerializationException) {
        RefreshOutcome.ServerError
    }
```

- Catch the named failure types and turn each into a domain result. `IOException` here is `kotlinx.io.IOException`, which Ktor throws on every platform when the network is down.
- Never catch `Exception` or `Throwable`. That swallows `CancellationException` and breaks cancellation.
- A repository function is main-safe. Room and Ktor already move their work off the main thread, so add `withContext` only around blocking code that the app wrote.
- A write made offline is saved locally with a pending flag and sent later. The screen shows the saved value at once.

## Secrets and configuration

- The base URL arrives through `AppConfig` from each host app. Common code holds no URL literal.
- An access token is stored with the platform keystore behind a port: Keystore on Android, Keychain on iOS. It never goes in Room, DataStore or a log line.

## Closing check

A repository test drives the real repository with a Ktor `MockEngine` and a fake DAO, covering success, offline and server error, following {{ skill_link("kmp-testing") }}. `./gradlew :shared:jvmTest` exits 0.
