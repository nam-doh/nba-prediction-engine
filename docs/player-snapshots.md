# Player-data snapshot contract

Player-data adapters write immutable JSON envelopes below a caller-selected
snapshot root. The refresh commands default to
`data/snapshots/player_data`, which is runtime state and must not be committed.
Tests use temporary directories.

Each path is partitioned as
`provider/dataset/YYYY/MM/DD/<UTC timestamp>_<content hash>.json`. The envelope
contains schema version, provider, dataset, request parameters, a credential-
redacted source URL, UTC retrieval time, optional source-as-of time, normalized
records, the raw provider payload, record count, and a SHA-256 content hash.
Writes use a temporary file followed by a same-filesystem hard link, so an
existing file is never replaced. Identical content at the same microsecond is
idempotent; different content cannot overwrite it.

`SnapshotStore.latest()` can select the newest verified snapshot for an exact
request. Reads recompute the content hash and reject corrupt or unsupported
documents. Provider and dataset path components reject traversal and unusual
characters. Query values named `api_key`, `apikey`, `key`, `token`,
`access_token`, `api-key`, `x-api-key`, or `subscription-key` are stored as
`REDACTED`; adapters must still avoid putting secrets in request metadata or
normalized records.

Snapshots establish when this project retrieved data. They do not prove that
the provider published every field by that time. Adapters must use a genuine
provider publication timestamp as `source_as_of` when one exists and keep it
separate from `retrieved_at`. Historical features may only use a snapshot and
source record that were available strictly before the predicted game.
